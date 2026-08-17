# -*- coding: utf-8 -*-
#
# ruleeditor.py -- a self-contained fork of Gramps' EditRule.
#
# It hosts the full Person rule palette exactly like Gramps' "Add Rule" dialog
# (all 79 rules, grouped by category, with a live search box), but changes the
# two seams we care about:
#
#   * SEAM 1 (input): when a rule takes a "Filter name:" argument, we show OUR
#     two-box FilterRefWidget (main + helper filters, id under the hood) instead
#     of Gramps' single MyFilters combo.
#
#   * SEAM 2 (output): on OK we emit OUR rule dict
#         {"class": <name>, "values": [...], "filter_refs": [...]}
#     to a callback -- we never build a Gramps GenericFilter rule and never
#     touch custom_filters.xml.
#
# No Glade dependency: Gramps' EditRule loads its layout from a .glade file, so
# we build a small container by hand (a paned window: rule tree on the left,
# rule arguments on the right). All the *argument widgets* are imported from
# Gramps unchanged -- their get_text()/set_text() contract is identical across
# 5.2 / 6.0 / master, so this fork holds on every target version.
#
# Scope: Person namespace only (matches FilterEngine.palette()).

from gi.repository import Gtk, Gdk, GObject, GLib

import os
import json

# IMPORTANT: use Gramps' MAIN catalog here, not an addon translator, so that
# _("Filter name:") etc. match the label strings the rule classes were built
# with. Mismatched domains would make the dispatch silently miss.
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

from gramps.gen.filters import rules
from gramps.gen.utils.string import conf_strings
from gramps.gen.datehandler import displayer
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.widgets import DateEntry

# Reuse Gramps' own, version-stable argument widgets + the label->type map.
from gramps.gui.editors.filtereditor import (
    MyBoolean, MyInteger, MyLesserEqualGreater, MySelect, MySource,
    MyID, MyList, MyPlaces, MyEntry, MyFilters, _name2typeclass,
)

from filterrefwidget import FilterRefWidget


# ---------------------------------------------------------------------------
# UI-praeferencer (app-brede, IKKE per-traeet): en lille sidecar-fil ved siden
# af EFB's per-traeet filfiler. Bevidst UDEN Gramps' config-API, saa den
# opfoerer sig ens paa 5.2/6.0 og Windows/Linux og er triviel at teste headless.
# Bruges lige nu kun til at huske regel-editorens paned-deler-position, saa den
# ikke altid nulstilles til 450 (for lidt paa en lille indbygget skaerm).
# ---------------------------------------------------------------------------
_RULE_PANED_DEFAULT = 450
_RULE_PANED_KEY = "rule_paned"


# ui.json-hjaelperne bor nu i filterengine (faelles datalag). Beholder de gamle
# private navne som tynde delegater, saa resten af ruleeditor er uroert.
def _ui_prefs_path():
    from filterengine import ui_prefs_path
    return ui_prefs_path()


def _load_ui_prefs():
    from filterengine import load_ui_prefs
    return load_ui_prefs()


def _save_ui_pref(key, value):
    from filterengine import save_ui_pref
    return save_ui_pref(key, value)


def _rule_paned_get():
    try:
        v = int(_load_ui_prefs().get(_RULE_PANED_KEY, _RULE_PANED_DEFAULT))
        return v if v >= 100 else _RULE_PANED_DEFAULT
    except Exception:
        return _RULE_PANED_DEFAULT

FILTER_LABEL = _("Filter name:")   # same-namespace filter argument (Person here)

# A rule's labels are translated by ITS OWN catalog (addon rules use
# get_addon_translator), which may differ from our core translation -- or be
# untranslated (raw English) in this locale. So we match BOTH the English
# msgid AND the localized form. "Person filter name:" is an explicit Person
# filter (used by the ExcludeSubtree / "reachable, stopping at <filter>" rule);
# it references PERSON filters, so it uses our two-box widget too.
_PERSON_FILTER_MSGIDS = ("Filter name:", "Person filter name:")
_FOREIGN_FILTER_MSGIDS = {
    "Family filter name:": "Family",
    "Event filter name:": "Event",
    "Source filter name:": "Source",
    "Repository filter name:": "Repository",
    "Place filter name:": "Place",
    "Citation filter name:": "Citation",
}

# Precompute sets holding both the raw msgid and the localized form.
PERSON_FILTER_LABELS = set()
for _m in _PERSON_FILTER_MSGIDS:
    PERSON_FILTER_LABELS.add(_m)
    PERSON_FILTER_LABELS.add(_(_m))

FOREIGN_FILTER_NS = {}
for _m, _ns in _FOREIGN_FILTER_MSGIDS.items():
    FOREIGN_FILTER_NS[_m] = _ns
    FOREIGN_FILTER_NS[_(_m)] = _ns


class _FilterDBProbe:
    """Wraps Gramps' real custom-filter list.

    Two jobs:
      * it is the object third-party rules fish out of the caller frame as
        ``filterdb`` (they call ``.get_filters(namespace)`` on it), and
      * it records which namespace was last requested, so RuleEditor can tell
        when a rule's own widget is a PERSON-filter selector (which we then
        replace with our two-box widget). Language-independent -- no label
        text parsing.
    """

    def __init__(self, real):
        self._real = real
        self._last_ns = None

    def get_filters(self, namespace):
        self._last_ns = namespace
        if self._real is None:
            return []
        return self._real.get_filters(namespace)

    def reset_probe(self):
        self._last_ns = None

    def last_namespace(self):
        return self._last_ns

    def __getattr__(self, name):
        # pass through anything else a rule might call (e.g. add)
        return getattr(self._real, name)


class RuleEditor(ManagedWindow):
    """Edit ONE rule and hand the result back as our dict via ``update``.

    Parameters
    ----------
    namespace : str
        Must be "Person" for now.
    dbstate, uistate, track :
        Standard Gramps GUI context (a ManagedWindow/tool has all three).
    val : dict | None
        The rule to edit as our dict, or None to add a new one.
    label : str
        Window title.
    update : callable(old_dict_or_None, new_dict)
        Called on OK with the produced rule dict. The OUTER builder dialog owns
        the list of rules and the filter's name/kind -- this editor is just
        "edit one rule".
    main_items, helper_items : iterable of (id, name)
        The two filter lists for the FilterRefWidget. The builder passes:
            main   = [(f["id"], f["name"]) for f in engine.list("main")]
            helper = [(f["id"], f["name"]) for f in engine.list("temp")]
    exclude_id : str | None
        Id of the filter currently being edited -- excluded from both boxes so
        a filter can't reference itself.
    """

    def __init__(self, namespace, dbstate, uistate, track,
                 val, label, update,
                 main_items, helper_items,
                 exclude_id=None):
        if namespace != "Person":
            raise NotImplementedError("RuleEditor is Person-only for now")

        ManagedWindow.__init__(self, uistate, track, self.__class__)
        self.namespace = namespace
        self.dbstate = dbstate
        self.uistate = uistate
        # NOTE: do NOT set self.track = track here. ManagedWindow.__init__ has
        # already set self.track to this window's OWN path. Overwriting it with
        # the incoming (parent) track makes close() run close_track() on the
        # PARENT, closing the whole builder. Gramps' own EditRule never does
        # this -- it lets the base keep self.track.
        self.db = dbstate.db
        self.update_rule = update
        self.active_rule = val
        self._main_items = list(main_items)
        self._helper_items = list(helper_items)
        self._exclude_id = exclude_id

        # Some third-party rules (e.g. the FilterRules addon) build their OWN
        # argument widget and fish a variable named 'filterdb' out of the
        # CALLER's stack frame -- see FamFilt.__init__ doing
        #   caller_locals["filterdb"].get_filters('Family').
        # Gramps' own EditRule happens to have that local; we must provide the
        # same thing, i.e. Gramps' real custom-filter list (Family/Event/... are
        # NOT part of our two Person lists).
        self._filterdb = _FilterDBProbe(self._gramps_filterdb())

        self.page = []          # [(class_obj, tlist, use_regex, use_case), ...]
        self.class2page = {}
        self.page_num = 0

        self._build_container(label)
        self._build_pages()
        self._build_tree()
        self._preselect_if_editing()
        self._connect()

        self.window.show_all()
        self.show()

    # ------------------------------------------------------------------
    # container (replaces the Glade layout)
    # ------------------------------------------------------------------
    def _build_container(self, label):
        window = Gtk.Window()
        # Size is owned by setup_configs() at the end of this method (see there):
        # Gramps' own EditRule works the same way, so no set_default_size() here.
        # The registered default is wider than Gramps' native rule editor, and a
        # wider tree pane (paned.set_position below) gives long rule names on the
        # left and the two filter combos on the right room. Used for BOTH New and
        # Edit, MAIN and HELPER filters.

        outer = Gtk.Box()
        outer.set_orientation(Gtk.Orientation.VERTICAL)
        outer.set_spacing(6)
        outer.set_border_width(6)

        paned = Gtk.Paned()
        paned.set_orientation(Gtk.Orientation.HORIZONTAL)

        # --- left: search + rule tree ---
        left = Gtk.Box()
        left.set_orientation(Gtk.Orientation.VERTICAL)
        left.set_spacing(6)
        self.rname_filter = Gtk.SearchEntry()
        self.rname_filter.set_placeholder_text(_("Search"))
        left.pack_start(self.rname_filter, False, False, 0)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.rname = Gtk.TreeView()
        self.rname.set_headers_visible(False)
        sw.add(self.rname)
        left.pack_start(sw, True, True, 0)
        paned.pack1(left, False, False)

        # --- right: headings + rule name + description + notebook ---
        right = Gtk.Box()
        right.set_orientation(Gtk.Orientation.VERTICAL)
        right.set_spacing(6)

        right.pack_start(self._heading(_("Selected Rule")), False, False, 0)
        self.rule_name = Gtk.Label()
        self.rule_name.set_xalign(0.0)
        self.rule_name.set_margin_start(12)
        right.pack_start(self.rule_name, False, False, 0)

        right.pack_start(self._heading(_("Description")), False, False, 0)
        self.description = Gtk.Label()
        self.description.set_xalign(0.0)
        self.description.set_line_wrap(True)
        self.description.set_margin_start(12)
        right.pack_start(self.description, False, False, 0)

        right.pack_start(self._heading(_("Values")), False, False, 0)
        self.notebook = Gtk.Notebook()
        self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(False)
        self.valuebox = Gtk.Box()
        self.valuebox.set_orientation(Gtk.Orientation.VERTICAL)
        self.valuebox.pack_start(self.notebook, True, True, 0)
        right.pack_start(self.valuebox, True, True, 0)

        paned.pack2(right, True, False)
        paned.set_position(_rule_paned_get())   # husket position (default 450)
        self._paned = paned
        outer.pack_start(paned, True, True, 0)

        # --- buttons ---
        btns = Gtk.Box()
        btns.set_orientation(Gtk.Orientation.HORIZONTAL)
        btns.set_spacing(6)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", self.close_window)
        ok = Gtk.Button(label=_("OK"))
        ok.connect("clicked", self.rule_ok)
        btns.pack_end(ok, False, False, 0)
        btns.pack_end(cancel, False, False, 0)
        outer.pack_end(btns, False, False, 0)

        window.add(outer)
        self.set_window(window, None, label)
        # Geometry lives in Gramps' own config (ini), exactly like Gramps' native
        # dialogs (EditRule uses "interface.edit-rule", 600x450). We use our OWN
        # key so we never touch Gramps' values. The 900px default opens wider
        # than Gramps' rule editor; after that setup_configs remembers whatever
        # width/height/position the user drags it to (saved on close()).
        self.setup_configs("interface.easyfilter-rule", 900, 470)

    def _heading(self, text):
        lab = Gtk.Label()
        lab.set_markup("<b>%s</b>" % text)
        lab.set_xalign(0.0)
        return lab

    # ------------------------------------------------------------------
    # one notebook page per rule; label -> widget dispatch
    # ------------------------------------------------------------------
    def _build_pages(self):
        self._class_list = rules.person.editor_rule_list
        for class_obj in self._class_list:
            grid = Gtk.Grid()
            grid.set_border_width(12)
            grid.set_column_spacing(6)
            grid.set_row_spacing(6)
            tlist = []
            pos = 0
            for v in class_obj.labels:
                text = v[0] if isinstance(v, tuple) else v
                lab = Gtk.Label(label=text, halign=Gtk.Align.END)
                t = self._make_widget(v)
                t.set_hexpand(True)
                tlist.append(t)
                grid.attach(lab, 0, pos, 1, 1)
                grid.attach(t, 1, pos, 1, 1)
                pos += 1

            use_regex = None
            use_case = None
            if class_obj.allow_regex:
                # regex/case baeres nu gennem motoren (_clean_rules +
                # _make_rule): tikkes regex, gemmes use_regex (+ use_case) paa
                # reglen og saettes paa Gramps-reglen ved materialisering.
                use_regex = Gtk.CheckButton(label=_("Use regular expressions"))
                use_regex.set_halign(Gtk.Align.START)
                grid.attach(use_regex, 1, pos, 1, 1)
                pos += 1
                use_case = Gtk.CheckButton(label=_("Case sensitive"))
                use_case.set_halign(Gtk.Align.START)
                grid.attach(use_case, 1, pos, 1, 1)
                use_regex.connect("toggled", self.regex_selection, use_case)
                use_case.set_sensitive(False)

            self.page.append((class_obj, tlist, use_regex, use_case))

            scr = Gtk.ScrolledWindow()
            scr.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scr.add(grid)
            self.notebook.append_page(scr, Gtk.Label(label=class_obj.name))
            self.class2page[class_obj] = self.page_num
            self.page_num += 1
        self.page_num = 0

    def _make_widget(self, v):
        # IMPORTANT: this local is named 'filterdb' ON PURPOSE. Third-party
        # rules that supply their own widget (the tuple-label case below) read
        # it from THIS frame via inspect.stack()[1][0].f_locals["filterdb"].
        # Do not rename or remove it even though it looks unused.
        filterdb = self._filterdb  # noqa: F841

        # SEAM 1: Person-filter arguments -> our two-box widget (our lists).
        if v in PERSON_FILTER_LABELS:
            return self._filter_ref_widget()
        # Foreign-namespace filter arguments -> Gramps' own combo over the real
        # custom filters (e.g. the core "events matching <event filter>" rule).
        if v in FOREIGN_FILTER_NS:
            return MyFilters(self._filterdb.get_filters(FOREIGN_FILTER_NS[v]))

        if v == _("Place:"):
            return MyPlaces([])
        if v in (_("Reference count:"), _("Number of instances:")):
            return MyInteger(0, 999)
        if v == _("Reference count must be:"):
            return MyLesserEqualGreater()
        if v == _("Number must be:"):
            return MyLesserEqualGreater(2)
        if v == _("Number of generations:"):
            return MyInteger(1, 32)
        if v == _("ID:"):
            return MyID(self.dbstate, self.uistate, self.track, self.namespace)
        if v == _("Source ID:"):
            return MySource(self.dbstate, self.uistate, self.track)
        if v in _name2typeclass:
            return MySelect(_name2typeclass[v], self._type_additional(v))
        if v == _("Inclusive:"):
            return MyBoolean(_("Include selected Gramps ID"))
        if v == _("Case sensitive:"):
            return MyBoolean(_("Use exact case of letters"))
        if v == _("Regular-Expression matching:"):
            return MyBoolean(_("Use regular expression"))
        if v == _("Include Family events:"):
            return MyBoolean(_("Also family events where person is spouse"))
        if v == _("Primary Role:"):
            return MyBoolean(_("Only include primary participants"))
        if v == _("Tag:"):
            taglist = [""] + [tag.get_name() for tag in self.db.iter_tags()]
            return MyList(taglist, taglist)
        if v == _("Confidence level:"):
            return MyList(list(map(str, range(5))),
                          [_(conf_strings[i]) for i in range(5)])
        if v == _("Date:"):
            return DateEntry(self.uistate, self.track)
        if v == _("Day of Week:"):
            long_days = displayer.long_days
            days = long_days[2:] + long_days[1:2]
            return MyList(list(map(str, range(7))), days)
        if v == _("Units:"):
            return MyList([0, 1, 2], [_("kilometers"), _("miles"), _("degrees")])
        if isinstance(v, tuple):
            # A rule that supplies its OWN widget factory. If that widget turns
            # out to be a PERSON-filter selector (it asks filterdb for filters
            # in our namespace -- e.g. the Isotammi "reachable/stopping at
            # <filter>" rule), swap in our two-box widget so it uses OUR lists
            # instead of Gramps' custom_filters.xml. Detected by probing which
            # namespace the factory requested -- language-independent.
            self._filterdb.reset_probe()
            widget = v[1](self.db)
            if self._filterdb.last_namespace() == self.namespace:
                return self._filter_ref_widget()
            return widget
        return MyEntry()

    def _filter_ref_widget(self):
        return FilterRefWidget(
            self._main_items, self._helper_items,
            exclude_id=self._exclude_id)

    def _gramps_filterdb(self):
        """Gramps' real custom-filter list, exposed for rules that fish it out
        of the caller frame. Returns an object with get_filters(namespace);
        falls back to an empty FilterList so such rules never crash."""
        try:
            import gramps.gen.filters as gfilt
            if gfilt.CustomFilters is None:
                gfilt.reload_custom_filters()
            if gfilt.CustomFilters is not None:
                return gfilt.CustomFilters
        except Exception as exc:
            print("[ruleeditor] custom filters unavailable:", exc)
        try:
            from gramps.gen.filters import FilterList
            return FilterList("")   # not loaded -> get_filters(...) returns []
        except Exception:
            return None

    def _type_additional(self, v):
        db = self.db
        if v in (_("Event type:"), _("Personal event:"), _("Family event:")):
            return db.get_event_types()
        if v == _("Personal attribute:"):
            return db.get_person_attribute_types()
        if v == _("Family attribute:"):
            return db.get_family_attribute_types()
        if v == _("Event attribute:"):
            return db.get_event_attribute_types()
        if v == _("Media attribute:"):
            return db.get_media_attribute_types()
        if v == _("Relationship type:"):
            return db.get_family_relation_types()
        if v == _("Note type:"):
            return db.get_note_types()
        if v == _("Name type:"):
            return db.get_name_types()
        if v == _("Surname origin type:"):
            return db.get_origin_types()
        if v == _("Place type:"):
            return sorted(db.get_place_types(), key=lambda s: s.lower())
        return None

    # ------------------------------------------------------------------
    # category-grouped, searchable rule tree
    # ------------------------------------------------------------------
    def _build_tree(self):
        self.store = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_PYOBJECT)
        self.ruletree_filter = self.store.filter_new()
        self.ruletree_filter.set_visible_func(self.rtree_visible_func)
        self.selection = self.rname.get_selection()
        col = Gtk.TreeViewColumn(_("Rule Name"), Gtk.CellRendererText(), text=0)
        self.rname.append_column(col)
        self.rname.set_model(self.ruletree_filter)

        keys = sorted(self._class_list, key=lambda x: x.name, reverse=True)
        catlist = sorted(set(c.category for c in keys))
        self._top_node = {}
        last_top = None
        for category in catlist:
            node = self.store.insert_after(None, last_top)
            last_top = node
            self.store.set(node, 0, category, 1, "")
            self._top_node[category] = node
        prev = None
        for class_obj in keys:
            node = self.store.insert_after(self._top_node[class_obj.category], prev)
            self.store.set(node, 0, class_obj.name, 1, class_obj)

    def _preselect_if_editing(self):
        if not self.active_rule:
            return
        target = self.active_rule.get("class")
        class_obj = next((c for c in self._class_list
                          if c.__name__ == target), None)
        if class_obj is None:
            return
        top = self._top_node[class_obj.category]
        # Reveal the rule in the tree so Edit shows WHERE it lives: expand its
        # category, select the row and scroll it into view. (Gramps' own EditRule
        # doesn't do this.) The view model is a TreeModelFilter, so we must
        # convert the STORE iters to FILTER iters before selecting -- selecting a
        # store iter against the filter-backed selection silently misses, which
        # is why editing previously showed nothing selected.
        self._reveal_class(class_obj, top)
        page = self.class2page[class_obj]
        # The notebook (and its pages) must be shown BEFORE switching page:
        # Gtk.Notebook.set_current_page() silently no-ops on pages that are not
        # yet visible, leaving the notebook on page 0. Our window is only shown
        # via show_all() *after* this method, so realize the notebook subtree
        # here. Without this, editing showed page 0 (arg-less "Everyone") -- the
        # rule's fields were filled but hidden -- and rule_ok read page 0's
        # empty widget list, wiping the rule's arguments on OK.
        self.notebook.show_all()
        self.notebook.set_current_page(page)
        self.display_values(class_obj)
        _co, tlist, use_regex_w, use_case_w = self.page[page]
        vals = self.active_rule.get("values", [])
        for i in range(min(len(tlist), len(vals))):
            tlist[i].set_text(vals[i])
        # Genskab regex/case-tilstanden fra den gemte regel, saa Rediger viser
        # praecis som gemt (og OK ikke taber flaget). use_case foelger regex.
        if use_regex_w is not None:
            want_regex = bool(self.active_rule.get("use_regex"))
            use_regex_w.set_active(want_regex)
            if use_case_w is not None:
                use_case_w.set_sensitive(want_regex)
                use_case_w.set_active(want_regex
                                      and bool(self.active_rule.get("use_case")))

    def _reveal_class(self, class_obj, top_store_iter):
        """Expand the rule's category, select its row and scroll to it.

        Works against the filter-backed view model by converting the child-model
        (store) iters to filter iters. Scrolling is deferred with idle_add so it
        runs after the window is realized (this method runs before show_all)."""
        # locate the store child iter for this rule class
        child = self.store.iter_children(top_store_iter)
        while child is not None:
            if self.store.get_value(child, 1) is class_obj:
                break
            child = self.store.iter_next(child)
        if child is None:
            return
        fmodel = self.ruletree_filter
        ok_top, f_top = fmodel.convert_child_iter_to_iter(top_store_iter)
        ok_child, f_child = fmodel.convert_child_iter_to_iter(child)
        if not (ok_top and ok_child):
            return
        cat_path = fmodel.get_path(f_top)
        self.rname.expand_row(cat_path, False)
        self.selection.select_iter(f_child)
        row_path = fmodel.get_path(f_child)

        def _scroll_once():
            self.rname.scroll_to_cell(row_path, None, True, 0.5, 0.0)
            return False    # run once
        GLib.idle_add(_scroll_once)

    def _connect(self):
        self.selection.connect("changed", self.on_node_selected)
        self.rname.connect("button-press-event", self._button_press)
        self.rname.connect("key-press-event", self._key_press)
        self.rname_filter.connect("search-changed", self.on_rname_filter_changed)

    # ------------------------------------------------------------------
    # behaviour (kept close to Gramps' EditRule)
    # ------------------------------------------------------------------
    def regex_selection(self, widget=None, use_case=None):
        if use_case:
            if widget and widget.get_active():
                use_case.set_sensitive(True)
            else:
                use_case.set_active(False)
                use_case.set_sensitive(False)

    def select_iter(self, data):
        top_node, it = data
        self.selection.select_iter(top_node)
        self.expand_collapse()
        self.selection.select_iter(it)

    def _button_press(self, obj, event):
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and event.button == 1:
            return self.expand_collapse()

    def _key_press(self, obj, event):
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return self.expand_collapse()
        return False

    def expand_collapse(self):
        store, paths = self.selection.get_selected_rows()
        if paths and len(paths[0].get_indices()) == 1:
            if self.rname.row_expanded(paths[0]):
                self.rname.collapse_row(paths[0])
            else:
                self.rname.expand_row(paths[0], 0)
            return True
        return False

    def close_window(self, obj):
        self.close()

    def close(self, *args):
        # Save the paned divider position on EVERY close path (OK, Cancel, the
        # window's X). Geometry (w/h/pos) is still owned by setup_configs; this
        # only adds the internal splitter, which setup_configs does not track.
        try:
            if getattr(self, "_paned", None) is not None:
                _save_ui_pref(_RULE_PANED_KEY, int(self._paned.get_position()))
        except Exception:
            pass
        return ManagedWindow.close(self, *args)

    def on_node_selected(self, obj):
        store, node = self.selection.get_selected()
        if node:
            class_obj = store.get_value(node, 1)
            self.display_values(class_obj)

    def on_rname_filter_changed(self, obj):
        self.ruletree_filter.refilter()

    def display_values(self, class_obj):
        if class_obj in self.class2page:
            page = self.class2page[class_obj]
            self.notebook.set_current_page(page)
            self.valuebox.set_sensitive(True)
            self.rule_name.set_text(class_obj.name)
            self.description.set_text(class_obj.description)
        else:
            self.valuebox.set_sensitive(False)
            self.rule_name.set_text(_("No rule selected"))
            self.description.set_text("")

    def rule_ok(self, obj):
        if self.rule_name.get_text() == _("No rule selected"):
            return
        try:
            page = self.notebook.get_current_page()
            class_obj, tlist, use_regex_w, use_case_w = self.page[page]
        except (KeyError, IndexError):
            return

        # SEAM 2: build OUR dict. Any argument shown with a FilterRefWidget is a
        # filter reference (this covers both the "Filter name:" case and the
        # tuple-label Person-filter rules), and it returns the STABLE id.
        values = [str(w.get_text()) for w in tlist]
        refs = [values[i] for i, w in enumerate(tlist)
                if isinstance(w, FilterRefWidget) and values[i]]
        rule = {"class": class_obj.__name__,
                "values": values,
                "filter_refs": refs}
        # regex/case-flag baeres kun med naar reglen tillader regex OG boksen er
        # tikket (case er kun aktiv naar regex er det -- se regex_selection).
        if use_regex_w is not None and use_regex_w.get_active():
            rule["use_regex"] = True
            if use_case_w is not None and use_case_w.get_active():
                rule["use_case"] = True
        self.update_rule(self.active_rule, rule)
        self.close()

    def rtree_visible_func(self, model, it, data):
        filter_text = self.rname_filter.get_text()
        tree_text = model[it][0]
        children = model[it].iterchildren()
        return (not tree_text or children.iter
                or filter_text.lower() in tree_text.lower())

    def build_menu_names(self, obj):
        # non-None submenu label => BRANCH, so this window can host its own
        # child pickers (MyID / MySource / date entry). Gramps' EditRule
        # inherits the base default (both non-None); the earlier None here made
        # it a leaf, which would reject those child windows.
        return (_("Edit Rule"), _("Edit Rule"))
