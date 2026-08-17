# -*- coding: utf-8 -*-
#
# filterpanel.py -- the reusable inner editor for ONE filter.
#
# It edits exactly the parts a filter has: a name, a comment, the logical
# operator (+ invert, via OperatorWidget), and a list of rules. Adding or
# editing a rule opens the forked RuleEditor as a popup; the result comes back
# as our rule dict {class, values, filter_refs} and lands in the list.
#
# It is used in TWO places with the SAME code:
#   * pinned at the top of the builder for the MAIN filter, and
#   * inside a small popup when creating/editing a HELPER filter.
#
# Deliberately engine-free: the panel does NOT know FilterEngine. The OUTER
# builder dialog owns the engine, reads get_fields() and calls engine.create /
# engine.update itself. That keeps this block testable on its own.
#
# Contract:
#   load_filter(flt_dict)   fill the fields from a stored filter dict (or {} )
#   get_fields() -> dict    {"name","comment","op","invert","rules"}
#
# English is the source language; Danish arrives via .po/.mo at the very end.

from gi.repository import Gtk, GObject, GLib

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import WindowActiveError
try:
    _trans = glocale.get_addon_translator(__file__)
except (ValueError, AttributeError):
    _trans = glocale.translation
_ = _trans.gettext

from operatorwidget import OperatorWidget
from ruleeditor import RuleEditor


class FilterPanel(Gtk.Box):
    """Edit one filter's name, comment, operator and rule list.

    Parameters
    ----------
    dbstate, uistate, track :
        Standard Gramps GUI context -- needed to open the RuleEditor popup.
    main_items, helper_items : iterable of (id, name)
        The two filter lists, passed straight through to RuleEditor so that a
        rule with a filter argument can pick from them.
    exclude_id : str | None
        Id of the filter being edited, so it can't reference itself.
    describe_rule : callable(rule_dict) -> str | None
        How a rule is shown in the list. If None, a plain built-in description
        is used (class name + values, with filter ids shown as their names).
    compact_count : bool
        If True (helper editor), the live "Matches: N" count is placed on the
        invert-explanation row instead of a row of its own, so it doesn't crowd
        the OK/Cancel buttons below. The main builder leaves this False.
    """

    def __init__(self, dbstate, uistate, track,
                 main_items, helper_items,
                 exclude_id=None,
                 describe_rule=None, describe_ref=None, count_cb=None,
                 compact_count=False, test_rule_cb=None, filter_col_width=None,
                 live_count_cb=None):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(8)

        self._dbstate = dbstate
        self._uistate = uistate
        self._track = track
        self._main_items = list(main_items)
        self._helper_items = list(helper_items)
        self._exclude_id = exclude_id
        self._describe_rule = describe_rule or self._default_describe
        self._describe_ref = describe_ref or (lambda _r: "")
        self._count_cb = count_cb        # count_cb(rules, op, invert) -> int|None
        # Main builder only: push the live count to the builder so it can render
        # ONE unified status line (build-count vs. what's shown) instead of a
        # second "Matches: N" competing with the applied-status line.
        self._live_count_cb = live_count_cb
        self._test_rule_cb = test_rule_cb   # main builder only: test one rule
        self._count_timer = None
        self._rule_editor = None         # the one open RuleEditor, if any

        # --- name + comment ---
        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(6)
        self._name = Gtk.Entry()
        self._name.set_hexpand(True)
        self._comment = Gtk.Entry()
        self._comment.set_hexpand(True)
        grid.attach(self._rlabel(_("Name:")), 0, 0, 1, 1)
        grid.attach(self._name, 1, 0, 1, 1)
        grid.attach(self._rlabel(_("Comment:")), 0, 1, 1, 1)
        grid.attach(self._comment, 1, 1, 1, 1)
        self.pack_start(grid, False, False, 0)

        self.pack_start(self._hsep(), False, False, 0)

        # --- rules (Gramps-like: list with the 3 buttons on the RIGHT) ------
        rlab = Gtk.Label(label=_("Rules:"))
        rlab.set_halign(Gtk.Align.START)
        self.pack_start(rlab, False, False, 0)

        # model: (filter text, description text, rule dict). The Description
        # mirrors the helper list: for a rule that references another Easy
        # Filter Builder filter, it shows THAT filter's comment.
        self._store = Gtk.ListStore(GObject.TYPE_STRING,
                                    GObject.TYPE_STRING,
                                    GObject.TYPE_PYOBJECT)
        self._tree = Gtk.TreeView(model=self._store)
        self._tree.set_headers_visible(True)
        col_f = Gtk.TreeViewColumn(_("Filter"), Gtk.CellRendererText(), text=0)
        # FIXED sizing so a user-dragged width STICKS (and can be restored from
        # ui.json). GROW_ONLY/AUTOSIZE would ignore a saved fixed_width. min_width
        # is still a floor; Description gets the remaining space.
        col_f.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        col_f.set_min_width(160)
        try:
            w = int(filter_col_width) if filter_col_width else 160
        except (TypeError, ValueError):
            w = 160
        col_f.set_fixed_width(max(w, 160))
        col_f.set_resizable(True)
        self._col_f = col_f
        self._tree.append_column(col_f)
        col_d = Gtk.TreeViewColumn(_("Description"),
                                   Gtk.CellRendererText(), text=1)
        col_d.set_resizable(True)
        self._tree.append_column(col_d)
        self._tree.connect("row-activated", self._on_row_activated)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(150)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.add(self._tree)

        rules_row = Gtk.Box()
        rules_row.set_orientation(Gtk.Orientation.HORIZONTAL)
        rules_row.set_spacing(6)
        rules_row.pack_start(scroller, True, True, 0)

        vbtns = Gtk.Box()
        vbtns.set_orientation(Gtk.Orientation.VERTICAL)
        vbtns.set_spacing(6)
        vbtns.set_valign(Gtk.Align.START)
        for label, handler in ((_("New …"), self._on_new),
                               (_("Edit …"), self._on_edit),
                               (_("Remove"), self._on_remove)):
            b = Gtk.Button(label=label)
            b.connect("clicked", handler)
            vbtns.pack_start(b, False, False, 0)
        # Main builder only: afproev JUST the selected rule against the person
        # view (spejler hjaelpe-listens "Afprøv valgt filter", men paa regel-
        # niveau). Hjaelpe-editoren giver ikke test_rule_cb -> ingen knap dér.
        if self._test_rule_cb is not None:
            trb = Gtk.Button(label=_("Test selected rule"))
            trb.set_margin_top(12)
            trb.set_tooltip_text(
                _("Show the people matched by the selected rule alone"))
            trb.connect("clicked",
                        lambda *_a: self._test_rule_cb(self.selected_rule()))
            vbtns.pack_start(trb, False, False, 0)
        rules_row.pack_start(vbtns, False, False, 0)
        self.pack_start(rules_row, True, True, 0)

        # --- operator (+ invert) BELOW the rules, Gramps-style --------------
        self._op = OperatorWidget(on_change=self._schedule_count)
        self.pack_start(self._op, False, False, 0)

        # --- live match count (bottom) --------------------------------------
        self._store.connect("row-inserted", self._schedule_count)
        self._store.connect("row-deleted", self._schedule_count)
        self._store.connect("row-changed", self._schedule_count)
        self._count_label = Gtk.Label()
        self._count_label.set_xalign(1.0)
        # count_row always exists so attach_applied() has a home in every mode,
        # but where the count itself is shown depends on compact_count.
        self._count_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                  spacing=6)
        if compact_count:
            # Helper editor: keep dim "Matches: N" up on the invert-explanation
            # line so it doesn't sit right on top of the OK/Cancel buttons below.
            self._count_label.get_style_context().add_class("dim-label")
            self._op.invert_desc_row.pack_end(self._count_label, False, False, 0)
        else:
            # Main builder: ONE bold, non-dim count on the RIGHT of the status
            # row; the builder drops the dim description into the LEFT via
            # attach_applied(). Bold is applied per-update via markup.
            self._count_row.pack_end(self._count_label, False, False, 0)
            self.pack_start(self._count_row, False, False, 0)
        self._schedule_count()           # initial (usually empty)

    # ------------------------------------------------------------------
    # small construction helpers
    # ------------------------------------------------------------------
    def _rlabel(self, text):
        lab = Gtk.Label(label=text)
        lab.set_halign(Gtk.Align.END)
        return lab

    def _hsep(self):
        return Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

    # ------------------------------------------------------------------
    # load / read  (the panel's contract)
    # ------------------------------------------------------------------
    def load_filter(self, flt):
        flt = flt or {}
        self._name.set_text(flt.get("name", "") or "")
        self._comment.set_text(flt.get("comment", "") or "")
        self._op.set_op(flt.get("op", "and") or "and")
        self._op.set_invert(bool(flt.get("invert", False)))
        self._store.clear()
        for rule in flt.get("rules", []) or []:
            self._append_rule(dict(rule))     # copy, so we don't alias caller's

    def set_filter_lists(self, main_items, helper_items):
        """Refresh the main/helper lists (e.g. after a helper is created), so a
        RuleEditor opened next sees the current filters. Also re-describes the
        existing rows in case a referenced filter was renamed."""
        self._main_items = list(main_items)
        self._helper_items = list(helper_items)
        for row in self._store:
            row[0] = self._describe_rule(row[2])
            row[1] = self._describe_ref(row[2])

    # ------------------------------------------------------------------
    # optional injection points -- used by the MAIN builder (not the helper
    # editor): drop the action buttons + status labels into the operator/count
    # rows so they sit WITH the main filter.
    # ------------------------------------------------------------------
    def attach_action_row(self, widget):
        self._op.combo_row.pack_end(widget, False, False, 0)

    def attach_saved_status(self, widget):
        self._op.desc_row.pack_end(widget, False, False, 0)

    def attach_applied(self, widget):
        self._count_row.pack_start(widget, False, False, 0)

    def get_fields(self):
        return {
            "name": self._name.get_text().strip(),
            "comment": self._comment.get_text().strip(),
            "op": self._op.get_op(),
            "invert": self._op.get_invert(),
            "rules": [row[2] for row in self._store],
        }

    # ------------------------------------------------------------------
    # live match count
    # ------------------------------------------------------------------
    def _schedule_count(self, *args):
        """Debounce: coalesce a burst of changes into one recount."""
        if self._count_cb is None:
            return
        if self._count_timer is not None:
            GLib.source_remove(self._count_timer)
        self._count_timer = GLib.timeout_add(250, self._count_timeout)

    def _count_timeout(self):
        self._count_timer = None
        self.refresh_count()
        return False                     # one-shot

    def refresh_count(self):
        """Ask count_cb for the current build's match count and show it."""
        if self._count_cb is None:
            return
        f = self.get_fields()
        try:
            n = self._count_cb(f["rules"], f["op"], f["invert"])
        except Exception:
            n = None
        if self._live_count_cb is not None:
            # Main builder: let the builder render the unified status line.
            self._live_count_cb(n)
        elif n is None:
            self._count_label.set_text("")
        else:
            self._count_label.set_text(_("Matches: %d") % n)

    def set_count_display(self, n):
        """Main builder: the single count on the right of the status line, as
        ``Matches: N`` with the number in bold. Shows an em-dash when the build
        can't be counted (e.g. an active-person rule) -- reads as 'unknown',
        never a false 0."""
        val = str(n) if n is not None else "\u2014"
        self._count_label.set_markup(
            "%s <b>%s</b>" % (GLib.markup_escape_text(_("Matches:")), val))

    def cancel_pending_count(self):
        """Drop any debounced live-count refresh that is still queued. The
        builder calls this when it puts a TEST result on screen, so a timer
        armed by a just-before edit can't fire afterwards and overwrite the
        test with the live build count."""
        if self._count_timer is not None:
            GLib.source_remove(self._count_timer)
            self._count_timer = None

    # ------------------------------------------------------------------
    # rule list
    # ------------------------------------------------------------------
    def _append_rule(self, rule):
        self._store.append(
            [self._describe_rule(rule), self._describe_ref(rule), rule])

    def _default_describe(self, rule):
        """Plain fallback: class name + values, filter ids shown as names."""
        namemap = dict(self._main_items + self._helper_items)
        shown = [namemap.get(v, v) for v in rule.get("values", []) if v != ""]
        base = rule.get("class", "?")
        if shown:
            return "%s: %s" % (base, ", ".join(str(s) for s in shown))
        return base

    def _selected(self):
        model, it = self._tree.get_selection().get_selected()
        if it is None:
            return None, None
        return it, model[it][2]

    def selected_rule(self):
        """The rule dict currently selected in the rule list, or None."""
        _it, rule = self._selected()
        return rule

    def filter_col_width(self):
        """Current pixel width of the 'Filter' column (for ui.json persistence)."""
        try:
            return int(self._col_f.get_width())
        except Exception:
            return 0

    def set_exclude_id(self, fid):
        """Exclude a filter-id from the reference pickers so a filter can't
        reference ITSELF. Needed after the main filter's FIRST Save: it only
        gets an id then, and without this the freshly-saved filter would be
        offered as a choice inside its own rules (self-reference)."""
        self._exclude_id = fid

    # ------------------------------------------------------------------
    # RuleEditor popup wiring
    # ------------------------------------------------------------------
    def _open_editor(self, val, title):
        # Only ONE rule editor at a time. RuleEditor is a ManagedWindow keyed on
        # its class, so a second one collides (WindowActiveError) -- and opening
        # it for a *different* rule can even take Gramps down. So if one is
        # already open, just bring it forward instead of building a second.
        if self._rule_editor is not None:
            try:
                self._rule_editor.window.present()
                return
            except Exception:
                self._rule_editor = None      # stale ref -> fall through to open
        try:
            editor = RuleEditor(
                "Person", self._dbstate, self._uistate, self._track,
                val, title, self._on_rule_committed,
                self._main_items, self._helper_items,
                exclude_id=self._exclude_id)
        except WindowActiveError:
            return                            # one is already open (safety net)
        self._rule_editor = editor
        try:                                  # forget it once its window closes
            editor.window.connect("destroy", self._on_rule_editor_closed)
        except Exception:
            pass

    def _on_rule_editor_closed(self, *_a):
        self._rule_editor = None

    def _on_new(self, _btn):
        self._open_editor(None, _("Add rule"))

    def _on_edit(self, _btn):
        _it, rule = self._selected()
        if rule is not None:
            self._open_editor(rule, _("Edit rule"))

    def _on_row_activated(self, _tree, _path, _col):
        self._on_edit(None)

    def _on_remove(self, _btn):
        it, _rule = self._selected()
        if it is not None:
            self._store.remove(it)

    def _on_rule_committed(self, old, new):
        """RuleEditor's callback. old is None (add) or the edited dict."""
        if old is None:
            self._append_rule(new)
            return
        for row in self._store:          # replace the row holding 'old'
            if row[2] is old:
                row[0] = self._describe_rule(new)
                row[1] = self._describe_ref(new)
                row[2] = new
                return
        self._append_rule(new)           # not found -> treat as add
