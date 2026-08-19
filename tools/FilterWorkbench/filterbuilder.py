# -*- coding: utf-8 -*-
#
# filterbuilder.py -- the builder window (_FilterBuilderWindow) and helper
# editor. No longer a Gramps Tool; the gramplet (filterbuildergramplet.py)
# imports this module and opens _FilterBuilderWindow for New / Edit.
#
# Why the imports are at MODULE level (not inside methods):
# Gramps has this plugin folder on Python's import path only WHILE it loads a
# module. Sibling imports must therefore run at load time -- exactly like the
# working opwidgettest / ruleeditor do. If they were deferred into a method
# (run on click), they'd fail with "No module named 'filterengine'".
# As a belt-and-braces measure we also add this folder to sys.path, and we
# capture any import failure into _IMPORT_ERROR so it can be shown as a real
# dialog instead of Gramps' blank "Failed Loading Plugin".
#
# THIS IS A SEED: owns a FilterEngine (load only, no save) and hosts one
# FilterPanel for a MAIN filter. Filter picker, pinned main + scrolling helper
# list, real create_helper_cb, Save/Preview/Apply/Reset come next.

import os
import sys
import json
import traceback

from gi.repository import Gtk, GObject

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except Exception:
    _trans = glocale.translation
_ = _trans.gettext

from gramps.gui.managedwindow import ManagedWindow
from gramps.gen.errors import WindowActiveError
from gramps.gui.dialog import ErrorDialog

# belt-and-braces: keep this folder importable
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# sibling imports at LOAD time (the mechanism that works); any failure is
# captured so the tool can show a readable dialog instead of failing silently
_IMPORT_ERROR = None
try:
    from filterengine import (FilterEngine, make_quiet_user,
                              load_ui_prefs, save_ui_pref)
    from filterpanel import FilterPanel
except Exception:
    _IMPORT_ERROR = traceback.format_exc()
    FilterEngine = None
    FilterPanel = None
    make_quiet_user = None
    load_ui_prefs = lambda: {}
    save_ui_pref = lambda *_a: None


# Rules whose live match count cannot be computed from the FLOATING builder
# window: they resolve a live UI selection -- the ACTIVE person -- via
# uistate.get_active('Person'), and that person-navigation history is not
# reliably populated for a floating ManagedWindow, so it comes back empty. Such
# a rule still APPLIES correctly once the filter is pushed to the People view
# (build_tree re-runs it in the view's own context, where the active person
# exists), but a *preview* here reads 0 -- a FALSE zero. So when a build uses one
# of these (directly or via a referenced helper) we BLANK the count -- an honest
# "unknown" -- instead of showing a wrong 0. A genuine 0 from any other build is
# still shown, so the "matches nobody" signal is preserved.
#
# This is a third-party rule (Gramps ships no active-person filter rule; only
# "Home Person"/IsDefaultPerson, which IS countable). Confirm the exact class
# name for YOUR installed rule from a saved filter's JSON --
# VERSION_DIR/filterbuilder/<dbid>.json, the "class" field of the rule -- or the
# rule add-on's own .py. Add any other active-person-dependent rule names here.
_UNCOUNTABLE_RULES = {"IsActivePerson"}


def _ref_comment(engine, rule):
    """Description-column text for a rule: the comment(s) of the Easy Filter
    Builder filter(s) the rule references (helper or main). This mirrors the
    helper list's own Description column, so a referenced filter can be told
    apart at a glance. Empty for rules that don't reference one of our filters.
    """
    parts = []
    for ref in rule.get("filter_refs", []):
        try:
            f = engine.get(ref)
        except Exception:
            f = None
        if f and (f.get("comment") or "").strip():
            parts.append(f["comment"].strip())
    return "; ".join(parts)


class _FilterBuilderWindow(ManagedWindow):
    def __init__(self, dbstate, uistate, track, view=None,
                 main_id=None, new=False, on_change=None):
        self.title = _("FilterWorkbench")
        ManagedWindow.__init__(self, uistate, track, self.__class__)
        self.dbstate = dbstate
        self.uistate = uistate
        # Optional explicit person view (a person-sidebar gramplet passes its
        # own self.gui.view here). If it isn't a person list we fall back to the
        # active main-window page -- see _target_view(). The builder is a
        # non-modal ManagedWindow, so Apply pushes the filter to the person list
        # BEHIND it without closing the builder.
        self._view = view
        self._applied_name = None
        # Det TOP-filter vi sidst pressede til visningen (fra apply_rules_to_view).
        # Bruges i close() til at afgoere om personlisten STADIG viser VORES preview
        # (saa nulstiller vi den) eller et andet filter (saa lader vi den staa).
        self._applied_top = None
        # Optional callback fired after a successful Save, so a launcher (the
        # gramplet) can refresh its saved-filter list. Given the id just saved.
        self._on_change = on_change
        # NOTE: do NOT set self.track = track here. The base __init__ already
        # set self.track to this window's OWN path; overwriting it with the
        # incoming (parent) track makes close() close the parent too.

        self.engine = FilterEngine(dbstate, namespace="Person")
        self.engine.load()                      # in-memory only; disk only on Save
        # A silent user that carries our real uistate: rules that talk to the
        # user (e.g. the "active person" rule) don't crash the count/apply, and
        # such rules can reach the active person via user.uistate -- without any
        # warning dialog popping up on every debounced recount.
        self._user = make_quiet_user(dbstate=dbstate, uistate=uistate)

        # Which main filter this window edits (the gramplet drives this):
        #   new=True      -> start blank; the first Save create()s a NEW main
        #                    (the gramplet's "New" button).
        #   main_id="..." -> edit exactly that main; Save update()s it
        #                    (the gramplet's "Edit" button). If the id has since
        #                    been deleted, get() returns None -> we degrade to a
        #                    blank/new window rather than crash.
        #   otherwise     -> v1 default: edit the first existing main, or blank
        #                    if none. This is what the Tool entry point uses, so
        #                    its behaviour is unchanged.
        # _main_id is None until the filter exists in the store; that flag is
        # what decides create() vs update() in _on_save.
        if new:
            self._main = None
        elif main_id is not None:
            self._main = self.engine.get(main_id)
        else:
            _mains = self.engine.list("main")
            self._main = _mains[0] if _mains else None
        self._main_id = self._main["id"] if self._main else None

        window = Gtk.Window()
        # Size/position owned by setup_configs() after set_window() below.

        box = Gtk.Box()
        box.set_orientation(Gtk.Orientation.VERTICAL)
        box.set_spacing(10)
        box.set_border_width(12)

        heading = Gtk.Label()
        heading.set_halign(Gtk.Align.START)
        heading.set_markup("<b>%s</b>" % _("Main filter"))
        box.pack_start(heading, False, False, 0)

        note = Gtk.Label()
        note.set_halign(Gtk.Align.START)
        note.set_xalign(0.0)
        note.set_line_wrap(True)
        note.get_style_context().add_class("dim-label")
        note.set_text(_("Build a main filter below. The match count updates "
                        "automatically. \u26a0\ufe0f Main and helper "
                        "filters don't appear in Gramps' own filter "
                        "editor."))
        box.pack_start(note, False, False, 0)

        main_items = [(f["id"], f["name"]) for f in self.engine.list("main")]
        helper_items = [(f["id"], f["name"]) for f in self.engine.list("temp")]

        # Gemte kolonne-bredder (Filter|Description-deleren) for de to lister --
        # trukket ud af ui.json, saa de ikke nulstilles hver gang (Hennings oenske).
        self._ui_prefs = load_ui_prefs()

        self.panel = FilterPanel(
            dbstate, uistate, self.track,
            main_items, helper_items,
            exclude_id=self._main_id,        # can't reference itself
            describe_rule=self._describe_rule,
            describe_ref=lambda r: _ref_comment(self.engine, r),
            count_cb=self._count_rules,      # live match count in the panel
            live_count_cb=self._on_live_count,   # -> unified status line
            test_rule_cb=self._on_test_selected_rule,
            filter_col_width=self._ui_prefs.get("main_col"))
        # The panel's rule list has vexpand=True, which would otherwise bubble
        # up and make the whole panel claim the window's spare height -- and
        # since the panel is packed fill=False, that surfaced as growing GAPS
        # above and below it when the window was dragged taller. Pin the panel
        # to non-expanding so ALL the spare height goes to the helper list below
        # (the only thing that should grow). The main rule list stays a fixed
        # height. (The helper editor keeps its own expanding panel untouched.)
        self.panel.set_vexpand(False)
        if self._main is not None:
            self.panel.load_filter(self._main)   # show the existing filter
        box.pack_start(self.panel, False, False, 0)  # helper list takes slack

        # The action buttons live WITH the main filter -- on the operator row --
        # so it reads as "this is the filter that gets applied, saved, shown",
        # and the helper list below is clearly just building blocks.
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        apply_btn = Gtk.Button(label=_("Test filter"))
        apply_btn.set_tooltip_text(
            _("Show the people matched by the filter you are building"))
        apply_btn.connect("clicked", self._on_apply)
        actions.pack_start(apply_btn, False, False, 0)
        reset_btn = Gtk.Button(label=_("Reset view"))
        reset_btn.connect("clicked", self._on_reset)
        actions.pack_start(reset_btn, False, False, 0)
        save = Gtk.Button(label=_("Save"))
        save.set_margin_start(16)          # gap: preview | commit/close
        save.connect("clicked", self._on_save)
        actions.pack_start(save, False, False, 0)
        close = Gtk.Button(label=_("Close"))
        close.connect("clicked", lambda _b: self.close())
        actions.pack_start(close, False, False, 0)
        self.panel.attach_action_row(actions)

        # "Saved: …" sits to the right of the operator explanation line.
        self._status = Gtk.Label()
        self._status.set_xalign(1.0)
        self._status.get_style_context().add_class("dim-label")
        self._refresh_status()
        self.panel.attach_saved_status(self._status)

        # "Not shown … / Showing in list …" sits LEFT of the match count.
        self._applied = Gtk.Label()
        self._applied.set_xalign(0.0)
        self._applied.get_style_context().add_class("dim-label")
        self._refresh_applied()
        self.panel.attach_applied(self._applied)

        # --- helper filters (one main filter, the rest are helpers) ----------
        hsep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(hsep, False, False, 0)
        hhead = Gtk.Label()
        hhead.set_halign(Gtk.Align.START)
        hhead.set_markup("<b>%s</b>" % _("Helper filters"))
        box.pack_start(hhead, False, False, 0)

        hrow = Gtk.Box()
        hrow.set_orientation(Gtk.Orientation.HORIZONTAL)
        hrow.set_spacing(6)
        # model: (name, description, id). The description (the helper's comment)
        # is shown so helpers can be told apart at a glance; id is hidden.
        self._helper_store = Gtk.ListStore(GObject.TYPE_STRING,
                                           GObject.TYPE_STRING,
                                           GObject.TYPE_STRING)
        self._helper_tree = Gtk.TreeView(model=self._helper_store)
        self._helper_tree.set_headers_visible(True)
        col_name = Gtk.TreeViewColumn(_("Filter"),
                                      Gtk.CellRendererText(), text=0)
        # FIXED + restorable width, mirroring the main rule list.
        col_name.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        col_name.set_min_width(130)
        try:
            _hw = int(self._ui_prefs.get("helper_col"))
        except (TypeError, ValueError):
            _hw = 130
        col_name.set_fixed_width(max(_hw, 130))
        col_name.set_resizable(True)
        self._helper_col = col_name
        self._helper_tree.append_column(col_name)
        col_desc = Gtk.TreeViewColumn(_("Description"),
                                      Gtk.CellRendererText(), text=1)
        col_desc.set_resizable(True)
        col_desc.set_expand(True)
        self._helper_tree.append_column(col_desc)
        self._helper_tree.connect("row-activated",
                                  lambda *_a: self._on_edit_helper(None))
        hscroll = Gtk.ScrolledWindow()
        hscroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        hscroll.set_min_content_height(160)   # taller than the rules list --
        hscroll.set_min_content_width(380)    # there are usually more helpers
        hscroll.set_hexpand(False)            # than main-filter rules, and it
        hscroll.set_vexpand(True)             # takes the window's spare height
        hscroll.add(self._helper_tree)        # (narrower, so it reads as UNDER)
        hrow.pack_start(hscroll, True, True, 0)

        # spacer pushes the helper buttons to the right, lining them up with
        # the main filter's New/Edit/Remove column.
        hrow.pack_start(Gtk.Box(), True, True, 0)

        hbtns = Gtk.Box()
        hbtns.set_orientation(Gtk.Orientation.VERTICAL)
        hbtns.set_spacing(6)
        hbtns.set_valign(Gtk.Align.START)
        for label, handler in ((_("New …"), self._on_new_helper),
                               (_("Edit …"), self._on_edit_helper),
                               (_("Remove"), self._on_remove_helper)):
            b = Gtk.Button(label=label)
            b.connect("clicked", handler)
            hbtns.pack_start(b, False, False, 0)
        # Afproev det MARKEREDE hjaelpefilter direkte paa personlisten. Saettes
        # lidt fra de tre redigerings-knapper -- det er en afproev-handling, ikke
        # en redigering -- og parrer med hovedfilterets "Test filter".
        test_helper_btn = Gtk.Button(label=_("Test selected filter"))
        test_helper_btn.set_margin_top(12)
        test_helper_btn.set_tooltip_text(
            _("Show the people matched by the selected helper filter"))
        test_helper_btn.connect("clicked", self._on_test_helper)
        hbtns.pack_start(test_helper_btn, False, False, 0)
        hrow.pack_start(hbtns, False, False, 0)
        box.pack_start(hrow, True, True, 0)
        self._refresh_helpers()

        # (whole-file Import/Export moved OUT of the builder to the Gramplet
        # launcher window -- its own design is still to come. The _on_export /
        # _on_import / _do_* methods below are kept, unused here, so that logic
        # can be lifted into the Gramplet later without rewriting it. The action
        # buttons + "Saved:" status now live up on the operator row, injected
        # into the panel above.)

        # baseline for the unsaved-changes check on Close (see close()).
        self._clean_snapshot = self._payload_snapshot()

        # Wrap the whole content in a vertical scroller so the window stays
        # usable at large font sizes / small screens: if the content is taller
        # than the window, a vertical scrollbar appears instead of the bottom
        # (buttons) being clipped off with no way to reach it. A Gtk.Box isn't
        # natively scrollable, so ScrolledWindow.add() wraps it in a Viewport
        # automatically. NEVER on the horizontal axis fits content to the
        # window width; the inner lists keep their own scroll for wide rows.
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(box)
        window.add(scroller)
        self.set_window(window, None, self.title)
        # Remember this window's geometry in Gramps' config (ini), the same way
        # Gramps' own dialogs do. close() calls super().close(), which saves size
        # + position; setup_configs restores them on the next open.
        self.setup_configs("interface.easyfilter-builder", 600, 700)
        self.window.show_all()
        self.show()

    def _describe_rule(self, rule):
        try:
            cls = self.engine.palette().get(rule.get("class"))
            base = cls.name if cls is not None else rule.get("class", "?")
        except Exception:
            base = rule.get("class", "?")
        namemap = {f["id"]: f["name"] for _k, f in self.engine.all()}
        shown = [namemap.get(v, v) for v in rule.get("values", []) if v != ""]
        if shown:
            return "%s: %s" % (base, ", ".join(str(s) for s in shown))
        return base

    def _count_rules(self, rules, op, invert):
        """Live match count for the current (unsaved) build. Returns an int,
        or None to blank the label (no rules yet, or a transient error such as
        a half-built reference)."""
        if not rules:
            return None
        # An active-person rule (directly or via a helper) can't be counted from
        # this floating window; showing "0" would be factually wrong (it applies
        # fine in the view). Blank it instead -- a missing number, not a lie.
        if self._build_uses_uncountable(rules):
            return None
        try:
            return len(self.engine.preview_rules(rules, op, invert,
                                                  user=self._user))
        except Exception:
            return None

    def _build_uses_uncountable(self, rules, _seen=None):
        """True if the build uses a rule we can't count here -- following helper
        references too (cycle-safe)."""
        if _seen is None:
            _seen = set()
        for r in (rules or []):
            if r.get("class") in _UNCOUNTABLE_RULES:
                return True
            for ref in r.get("filter_refs", []):
                if ref in _seen:
                    continue
                _seen.add(ref)
                try:
                    child = self.engine.get(ref)
                except Exception:
                    child = None
                if child and self._build_uses_uncountable(
                        child.get("rules", []), _seen):
                    return True
        return False

    # ------------------------------------------------------------------
    # Apply / Reset to the person list (Learning 5: never cleanup() while a
    # filter is live on the view -- reset_view is the right way to clear it).
    # ------------------------------------------------------------------
    @staticmethod
    def _is_person_view(page):
        """A page we may push a person filter to: has the filter hook AND is
        the People list (navigation_type == 'Person')."""
        return (page is not None
                and hasattr(page, "generic_filter")
                and hasattr(page, "build_tree")
                and getattr(page, "navigation_type", lambda: None)() == "Person")

    def _target_view(self):
        """Return (view, error_or_None). An explicit person view (passed by a
        person-sidebar gramplet) wins; otherwise the active main-window page,
        if it is the People list. The builder floats, so the user can select
        People behind it and press Apply."""
        if self._is_person_view(self._view):
            return self._view, None
        try:
            page = self.uistate.viewmanager.active_page
        except Exception:
            page = None
        if self._is_person_view(page):
            return page, None
        return None, _("Switch to the People view (the person list) and press "
                       "Apply again — the builder applies filters there.")

    def _on_apply(self, _btn):
        view, err = self._target_view()
        if err:
            ErrorDialog(_("Cannot apply"), err, parent=self.window)
            return
        f = self.panel.get_fields()
        name = (f.get("name") or "").strip() or _("(unsaved filter)")
        try:
            _top, count = self.engine.apply_rules_to_view(
                f["rules"], f.get("op", "and"),
                bool(f.get("invert", False)), view, user=self._user)
        except ValueError as exc:
            # cyclic / dangling / unknown-rule problems come back as ValueError
            ErrorDialog(_("Cannot apply"), str(exc), parent=self.window)
            return
        except Exception:
            ErrorDialog(_("Cannot apply"), traceback.format_exc(),
                        parent=self.window)
            return
        self._applied_name = name
        self._applied_top = _top
        # Samme falske-0-regel som live-tallet: bruger bygget en regel vi ikke kan
        # taelle fra det svaevende vindue (aktiv person), saa blank tallet i
        # "Vises i listen"-linjen ogsaa -- et 0 dér ville vaere en loegn (filteret
        # ANVENDER fint). Aegte 0 fra ethvert andet byg vises stadig.
        shown = None if self._build_uses_uncountable(f.get("rules", [])) else count
        self.panel.cancel_pending_count()   # a pending live count must not clobber this
        self._refresh_applied(shown)

    def _on_test_selected_rule(self, rule):
        """Afproev KUN den markerede regel i hovedfilterets regelliste -- som et
        ét-regels-filter paa personlisten (spejler hjaelpe-listens afproev, men paa
        regel-niveau, saa man kan se hvad netop den regel rammer). Refererer reglen
        et hjaelpefilter, materialiseres det automatisk som ellers."""
        if not rule:
            return
        view, err = self._target_view()
        if err:
            ErrorDialog(_("Cannot test"), err, parent=self.window)
            return
        try:
            _top, count = self.engine.apply_rules_to_view(
                [rule], "and", False, view, user=self._user)
        except ValueError as exc:
            ErrorDialog(_("Cannot test"), str(exc), parent=self.window)
            return
        except Exception:
            ErrorDialog(_("Cannot test"), traceback.format_exc(),
                        parent=self.window)
            return
        self._applied_name = self._describe_rule(rule)
        self._applied_top = _top
        shown = None if self._build_uses_uncountable([rule]) else count
        self.panel.cancel_pending_count()
        self._refresh_applied(shown)

    def _on_reset(self, _btn):
        view, err = self._target_view()
        if err:
            ErrorDialog(_("Cannot reset"), err, parent=self.window)
            return
        try:
            self.engine.reset_view(view)
        except Exception:
            ErrorDialog(_("Cannot reset"), traceback.format_exc(),
                        parent=self.window)
            return
        self._applied_name = None
        self._applied_top = None
        self._refresh_applied()

    # ------------------------------------------------------------------
    # Import / Export -- whole-file, to move filters between trees.
    # ------------------------------------------------------------------
    def _suggested_export_name(self):
        tid, tname = self.engine._tree_meta()
        base = tname or tid or "filters"
        safe = "".join(c if (c.isalnum() or c in " _-") else "_"
                       for c in base).strip().replace(" ", "_")
        return "filterbuilder_%s.json" % (safe or "filters")

    def _on_export(self, _btn):
        dlg = Gtk.FileChooserDialog(
            title=_("Export filters"), transient_for=self.window,
            action=Gtk.FileChooserAction.SAVE)
        dlg.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dlg.add_button(_("Export"), Gtk.ResponseType.OK)
        dlg.set_do_overwrite_confirmation(True)
        try:
            os.makedirs(self.engine.base_dir(), exist_ok=True)
            dlg.set_current_folder(self.engine.base_dir())
        except Exception:
            pass
        dlg.set_current_name(self._suggested_export_name())
        flt = Gtk.FileFilter()
        flt.set_name(_("JSON files"))
        flt.add_pattern("*.json")
        dlg.add_filter(flt)
        if dlg.run() == Gtk.ResponseType.OK:
            path = dlg.get_filename()
            if path and not path.lower().endswith(".json"):
                path += ".json"
            self._do_export(path)
        dlg.destroy()

    def _do_export(self, path):
        try:
            self.engine.export_to(path)
        except Exception:
            ErrorDialog(_("Cannot export"), traceback.format_exc(),
                        parent=self.window)
            return
        self._refresh_status(_("Exported to %s") % os.path.basename(path))

    def _on_import(self, _btn):
        dlg = Gtk.FileChooserDialog(
            title=_("Import filters"), transient_for=self.window,
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dlg.add_button(_("Import"), Gtk.ResponseType.OK)
        try:
            dlg.set_current_folder(self.engine.base_dir())
        except Exception:
            pass
        flt = Gtk.FileFilter()
        flt.set_name(_("JSON files"))
        flt.add_pattern("*.json")
        dlg.add_filter(flt)
        path = dlg.get_filename() if dlg.run() == Gtk.ResponseType.OK else None
        dlg.destroy()
        if not path:
            return
        # peek who/how-many the file holds, to name the source in the prompt
        try:
            info = self.engine.file_info(path)
        except Exception:
            info = None
        src = ((info or {}).get("name") or (info or {}).get("id")
               or _("an unknown tree"))
        if info is not None:
            text = _("Replace this tree's filters with %d filter(s) "
                     "from “%s”?") % (info["main"] + info["temp"], src)
        else:
            text = _("Replace this tree's filters with the file's contents?")
        # importing REPLACES this tree's filters -- confirm first
        q = Gtk.MessageDialog(
            transient_for=self.window, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO, text=text)
        proceed = (q.run() == Gtk.ResponseType.YES)
        q.destroy()
        if proceed:
            self._do_import(path)

    def _do_import(self, path):
        try:
            src = ""
            try:
                info = self.engine.file_info(path)
                src = info.get("name") or info.get("id") or ""
            except Exception:
                src = ""
            nmain, ntemp = self.engine.import_from(path)
            self.engine.save()               # persist into THIS tree
        except Exception:
            ErrorDialog(_("Cannot import"), traceback.format_exc(),
                        parent=self.window)
            return
        self._reload_first_main()
        self._clean_snapshot = self._payload_snapshot()   # import already saved
        if src:
            self._refresh_status(
                _("Imported %d main and %d helper filters from “%s”")
                % (nmain, ntemp, src))
        else:
            self._refresh_status(
                _("Imported %d main and %d helper filters") % (nmain, ntemp))

    def _reload_first_main(self):
        """After import, show the (new) first main filter in the panel."""
        mains = self.engine.list("main")
        self._main = mains[0] if mains else None
        self._main_id = self._main["id"] if self._main else None
        if self._main is not None:
            self.panel.load_filter(self._main)
        else:
            self.panel.load_filter(
                {"name": "", "op": "and", "invert": False, "rules": []})
        self._refresh_status()

    def _refresh_applied(self, count=None):
        # ONE status line, one number. The RIGHT always shows "Matches: N"
        # (via the panel); the LEFT carries context only when a test is shown:
        #   * build  (no test on screen): left empty,             right = live count
        #   * tested (a Test button used): "Showing in Person      right = shown count
        #                                   view list: X"
        if self._applied_name is None:
            self._applied.set_text("")
            self.panel.refresh_count()            # right = live "Matches: N"
        else:
            self._applied.set_text(
                _("Showing in Person view list: %s") % self._applied_name)
            self.panel.set_count_display(count)

    def _on_live_count(self, n):
        """Called by the panel whenever the live whole-filter count updates --
        i.e. whenever the build CHANGES (a rule/op/invert was edited). Editing
        supersedes any prior test on the STATUS line, so we flip back to build
        state and let the count keep updating (this is what makes the auto-count
        resume after a Test filter). The person list still shows the last test
        until you re-test or Reset; that is tracked separately by _applied_top,
        which we deliberately leave set so close/reset still cleans the list up.
        Stray timers can't reach here after a test -- the test path cancels the
        pending count (see cancel_pending_count)."""
        if not hasattr(self, "_applied"):
            return                              # not wired yet (early init)
        self._applied_name = None               # editing -> back to build state
        self._applied.set_text("")
        self.panel.set_count_display(n)          # "Matches: N" (live)

    def _refresh_status(self, text=None):
        if text is not None:
            self._status.set_text(text)
        elif self._main is not None:
            self._status.set_text(_("Saved: %s") % self._main["name"])
        else:
            self._status.set_text(_("Not saved yet"))

    def _on_save(self, _btn):
        """Read the panel, enforce the name-gate, then create/update + save().

        This is the ONLY place that writes to disk, and only on an explicit
        Save -- nothing touches the file before that.
        """
        f = self.panel.get_fields()
        name = (f.get("name") or "").strip()
        if not name:
            ErrorDialog(_("Cannot save"),
                        _("The filter needs a name."),
                        parent=self.window)
            return
        # Main-filter names must be unique AMONG MAIN filters (a helper may
        # share the name); exclude this filter itself when updating.
        for other in self.engine.list("main"):
            if other["name"] == name and other["id"] != self._main_id:
                ErrorDialog(
                    _("Cannot save"),
                    _("A main filter named \u201c%s\u201d already exists.")
                    % name,
                    parent=self.window)
                return
        try:
            if self._main_id is None:
                self._main_id = self.engine.create(
                    "main", name, f["rules"], f.get("comment", ""),
                    f.get("op", "and"), bool(f.get("invert", False)))
            else:
                self.engine.update(
                    self._main_id, name=name, rules=f["rules"],
                    comment=f.get("comment", ""), op=f.get("op", "and"),
                    invert=bool(f.get("invert", False)))
            self.engine.save()          # <-- the only disk write
        except ValueError as exc:
            # empty/cyclic/dangling-ref problems come back as ValueError
            ErrorDialog(_("Cannot save"), str(exc), parent=self.window)
            return
        self._main = self.engine.get(self._main_id)
        # Efter foerste Save har filteret nu et id -- udeluk det fra reference-
        # vaelgerne, saa dets egne regler ikke kan referere sig selv.
        self.panel.set_exclude_id(self._main_id)
        self._clean_snapshot = self._payload_snapshot()   # edits now persisted
        self._refresh_status(_("Saved: %s") % self._main["name"])
        self._notify_change()      # let a launcher refresh its saved-filter list

    # ------------------------------------------------------------------
    # Helper filters (one main filter, the rest are helpers). Everything stays
    # in memory ("temp" kind) until Save, which writes main + all helpers.
    # ------------------------------------------------------------------
    def _refresh_helpers(self):
        """Rebuild the helper list and keep the main panel's rule-editor lists
        current, so a newly created helper is immediately pickable."""
        self._helper_store.clear()
        for f in sorted(self.engine.list("temp"),
                        key=lambda f: (f.get("name") or "").lower()):
            self._helper_store.append(
                [f["name"], f.get("comment", ""), f["id"]])
        self.panel.set_filter_lists(
            [(f["id"], f["name"]) for f in self.engine.list("main")],
            [(f["id"], f["name"]) for f in self.engine.list("temp")])

    def _selected_helper_id(self):
        model, it = self._helper_tree.get_selection().get_selected()
        return model[it][2] if it is not None else None

    def _on_new_helper(self, _btn):
        try:
            _HelperEditor(self.dbstate, self.uistate, self.track, self.engine,
                          existing=None, on_commit=self._commit_helper,
                          count_cb=self._count_rules)
        except WindowActiveError:
            pass   # the helper editor is already open -> it was brought forward

    def _on_edit_helper(self, _btn):
        hid = self._selected_helper_id()
        if hid is None:
            return
        existing = self.engine.get(hid)
        if existing is None:
            return
        try:
            _HelperEditor(self.dbstate, self.uistate, self.track, self.engine,
                          existing=existing, on_commit=self._commit_helper,
                          count_cb=self._count_rules)
        except WindowActiveError:
            pass   # that helper's editor is already open -> brought forward

    def _commit_helper(self, existing_id, fields):
        """Called by _HelperEditor on OK. Create or update the in-memory helper
        (disk write still only happens on the builder's Save)."""
        if existing_id is None:
            self.engine.create("temp", fields["name"], fields["rules"],
                               fields.get("comment", ""), fields.get("op", "and"),
                               bool(fields.get("invert", False)))
        else:
            self.engine.update(existing_id, name=fields["name"],
                               rules=fields["rules"],
                               comment=fields.get("comment", ""),
                               op=fields.get("op", "and"),
                               invert=bool(fields.get("invert", False)))
        self._refresh_helpers()

    def _on_remove_helper(self, _btn):
        hid = self._selected_helper_id()
        if hid is None:
            return
        # Push the main filter's CURRENT (unsaved) rules into the in-memory
        # store first, so "is this helper still used?" reflects what you see
        # now -- e.g. after deleting the rule that referenced it -- rather than
        # the last-saved copy. (Disk is still written only on Save.)
        if self._main_id is not None:
            try:
                self.engine.update(
                    self._main_id,
                    rules=self.panel.get_fields().get("rules", []))
            except Exception:
                pass   # in-progress rules didn't validate; use the stored copy
        ok, users = self.engine.delete(hid)   # (ok, users); blocks if in use
        if not ok:
            ErrorDialog(
                _("Cannot remove"),
                _("This helper filter is used by: %s") % ", ".join(users),
                parent=self.window)
            return
        self._refresh_helpers()

    def _on_test_helper(self, _btn):
        """Afproev det MARKEREDE hjaelpefilter paa personlisten -- samme vej som et
        hovedfilter (``apply_to_view``), saa man kan kontrollere hvem det rammer.
        Hjaelpefilteret vises transient som ``wb_<navn>`` i Gramps' andre person-
        vaelgere indtil Reset/Close (praecis som et hovedfilter der afproeves); det
        skrives ALDRIG til ``custom_filters.xml``. "Vises i listen"-linjen viser
        hjaelperens navn + antal (blank for det utaellelige aktiv-person-tilfaelde)."""
        hid = self._selected_helper_id()
        if hid is None:
            return
        view, err = self._target_view()
        if err:
            ErrorDialog(_("Cannot test"), err, parent=self.window)
            return
        helper = self.engine.get(hid)
        if helper is None:
            return
        try:
            self.engine.apply_to_view(hid, view)
        except ValueError as exc:
            ErrorDialog(_("Cannot test"), str(exc), parent=self.window)
            return
        except Exception:
            ErrorDialog(_("Cannot test"), traceback.format_exc(),
                        parent=self.window)
            return
        self._applied_name = helper.get("name") or _("(helper filter)")
        # apply_to_view satte view.generic_filter til top-filteret; hold styr paa
        # det saa close() ved om listen stadig viser VORES afproevning.
        self._applied_top = getattr(view, "generic_filter", None)
        if self._build_uses_uncountable(helper.get("rules", [])):
            shown = None
        else:
            try:
                shown = len(self.engine.preview(hid, user=self._user))
            except Exception:
                shown = None
        self.panel.cancel_pending_count()
        self._refresh_applied(shown)
    # discarding edits, so a mis-click can't lose a session's work -- while
    # Close still lets you abandon an unwanted filter.
    # ------------------------------------------------------------------
    def _payload_snapshot(self):
        """Normalized JSON of everything Save would persist, INCLUDING the main
        panel's not-yet-committed edits. Compared against the snapshot taken at
        load / last Save to detect unsaved changes."""
        def norm(items):
            out = []
            for x in items:
                out.append({
                    "id": x.get("id", ""),
                    "name": (x.get("name") or "").strip(),
                    "comment": x.get("comment", "") or "",
                    "op": x.get("op", "and"),
                    "invert": bool(x.get("invert", False)),
                    "rules": x.get("rules", []),
                })
            out.sort(key=lambda d: (d["id"], d["name"]))
            return out

        mains = [dict(m) for m in self.engine.list("main")]
        f = self.panel.get_fields()
        cur = {
            "name": (f.get("name") or "").strip(),
            "comment": f.get("comment", "") or "",
            "op": f.get("op", "and"),
            "invert": bool(f.get("invert", False)),
            "rules": f.get("rules", []),
        }
        if self._main_id is not None:
            for m in mains:
                if m.get("id") == self._main_id:
                    m.update(cur)
        elif cur["name"] or cur["rules"]:
            mains.append(dict(cur, id="__unsaved_main__"))
        temps = [dict(t) for t in self.engine.list("temp")]
        return json.dumps({"main": norm(mains), "temp": norm(temps)},
                          sort_keys=True, ensure_ascii=False)

    def _is_dirty(self):
        return self._payload_snapshot() != self._clean_snapshot

    def _confirm_discard(self):
        q = Gtk.MessageDialog(
            transient_for=self.window, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=_("You have unsaved changes."),
            secondary_text=_("Close without saving?"))
        q.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        q.add_button(_("Close without saving"), Gtk.ResponseType.OK)
        q.set_default_response(Gtk.ResponseType.CANCEL)
        proceed = (q.run() == Gtk.ResponseType.OK)
        q.destroy()
        return proceed

    def _notify_change(self):
        """Tell the launcher (if any) that the saved main filters changed, so it
        can rebuild its list. Never let a callback error disturb the builder."""
        if self._on_change is not None:
            try:
                self._on_change(self._main_id)
            except Exception:
                pass

    def close(self, *args):
        """Close button and the window X both land here. Prompt if there are
        unsaved edits; returning True on Cancel keeps the window open and stops
        GTK's default (destroy) handler."""
        try:
            dirty = self._is_dirty()
        except Exception:
            dirty = False    # never trap the user because of an internal error
        if dirty and not self._confirm_discard():
            return True
        # Ryd op efter os selv saa koere-filtrene (__flow_) IKKE efterlades i den
        # delte in-memory CustomFilters (de hobede sig ellers op og forsvandt
        # foerst ved Gramps-genstart). To tilfaelde:
        #   * Viser personlisten STADIG vores eget preview -> nulstil visningen
        #     (fjerner top + hjaelpere rent, praecis som Reset view-knappen).
        #   * Ellers -> drop bare VORES egne koere-filtre uden at roere visningen
        #     (brugeren kan have anvendt et andet (gramplet-)filter bagefter).
        # Til sidst fejes evt. AELDRE efterladte lig fra tidligere lukninger.
        try:
            view, _err = self._target_view()
            cur = getattr(view, "generic_filter", None) if view is not None else None
            if (view is not None and self._applied_top is not None
                    and cur is self._applied_top):
                self.engine.reset_view(view)
            else:
                self.engine.cleanup()
            self.engine.sweep_orphans()
        except Exception:
            pass                     # oprydning maa aldrig blokere selve luk
        self._applied_top = None
        # Gem de to lister's "Filter"-kolonnebredde, saa de ikke nulstilles naeste
        # gang (Hennings 2 positioner). Kun fornuftige vaerdier -- en kollapset
        # 0-bredde (vindue aldrig realiseret) skal ikke overskrive en god vaerdi.
        try:
            mw = self.panel.filter_col_width()
            if mw and mw >= 40:
                save_ui_pref("main_col", int(mw))
            hw = int(self._helper_col.get_width())
            if hw and hw >= 40:
                save_ui_pref("helper_col", hw)
        except Exception:
            pass
        return super().close(*args)

    def build_menu_names(self, obj):
        # non-None submenu label => this is a BRANCH that can host child
        # windows (RuleEditor). Returning None would make it a leaf and the
        # window manager would reject the child with "not a leaf".
        return (self.title, self.title)


class _HelperEditor(ManagedWindow):
    """Non-modal editor for ONE helper filter, reusing FilterPanel so a helper
    has the SAME editing (rules + operator + opposite) as the main filter. On OK
    it validates the name (non-empty, unique among helpers) and calls on_commit;
    nothing is written to disk here -- the builder's Save does that."""

    def __init__(self, dbstate, uistate, track, engine, existing, on_commit,
                 count_cb=None):
        self.title = _("FilterWorkbench — Helper filter")
        ManagedWindow.__init__(self, uistate, track, self.__class__)
        self.dbstate = dbstate
        self.uistate = uistate
        self.engine = engine
        self._existing_id = existing["id"] if existing else None
        self._on_commit = on_commit

        window = Gtk.Window()
        # Size/position owned by setup_configs() after set_window() below.
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(12)

        heading = Gtk.Label()
        heading.set_halign(Gtk.Align.START)
        heading.set_markup("<b>%s</b>" % (_("Edit helper filter")
                                          if existing else _("New helper filter")))
        box.pack_start(heading, False, False, 0)

        # New helper filters aren't stored on their own -- they're persisted as
        # part of a main filter. Warn up front so a user who builds several
        # helpers here doesn't expect them to survive without saving a main
        # filter. (Only for NEW helpers; an existing one is already stored.)
        if not existing:
            hnote = Gtk.Label()
            hnote.set_halign(Gtk.Align.START)
            hnote.set_xalign(0.0)
            hnote.set_line_wrap(True)
            hnote.get_style_context().add_class("dim-label")
            hnote.set_text(_("\u26a0 New helper filters can only be saved while "
                             "creating or editing a main filter."))
            box.pack_start(hnote, False, False, 0)

        main_items = [(f["id"], f["name"]) for f in engine.list("main")]
        helper_items = [(f["id"], f["name"]) for f in engine.list("temp")]
        # Husk "Filter"-kolonnens bredde paa tvaers af luk/genaabn -- samme sidecar
        # ui.json som byggevinduets to lister (egen noegle, saa den ikke deler
        # bredde med hoved-regellisten).
        self._ui_prefs = load_ui_prefs()
        self.panel = FilterPanel(dbstate, uistate, self.track,
                                 main_items, helper_items,
                                 exclude_id=self._existing_id,
                                 describe_rule=self._describe_rule,
                                 describe_ref=lambda r: _ref_comment(
                                     self.engine, r),
                                 count_cb=count_cb,
                                 compact_count=True,
                                 filter_col_width=self._ui_prefs.get(
                                     "helper_edit_col"))
        if existing is not None:
            self.panel.load_filter(existing)
        box.pack_start(self.panel, True, True, 0)

        btnrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btnrow.pack_start(Gtk.Label(), True, True, 0)   # spacer, pushes right
        okb = Gtk.Button(label=_("OK"))
        okb.connect("clicked", self._on_ok)
        cab = Gtk.Button(label=_("Cancel"))
        cab.connect("clicked", lambda _b: self.close())
        btnrow.pack_start(okb, False, False, 0)
        btnrow.pack_start(cab, False, False, 0)
        box.pack_start(btnrow, False, False, 0)

        # Wrap the whole content in a vertical scroller so the window stays
        # usable at large font sizes / small screens: if the content is taller
        # than the window, a vertical scrollbar appears instead of the bottom
        # (buttons) being clipped off with no way to reach it. A Gtk.Box isn't
        # natively scrollable, so ScrolledWindow.add() wraps it in a Viewport
        # automatically. NEVER on the horizontal axis fits content to the
        # window width; the inner lists keep their own scroll for wide rows.
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(box)
        window.add(scroller)
        self.set_window(window, None, self.title)
        # Remember this window's geometry in Gramps' config (ini), the same way
        # Gramps' own dialogs do. Our close() calls super().close(), which saves
        # size + position; setup_configs restores them on the next open.
        self.setup_configs("interface.easyfilter-helper", 560, 620)
        self.window.show_all()
        self.show()

    def _describe_rule(self, rule):
        try:
            cls = self.engine.palette().get(rule.get("class"))
            base = cls.name if cls is not None else rule.get("class", "?")
        except Exception:
            base = rule.get("class", "?")
        namemap = {}
        for kind in ("main", "temp"):
            for f in self.engine.list(kind):
                namemap[f["id"]] = f["name"]
        vals = [namemap.get(v, v) for v in rule.get("values", []) if v != ""]
        return ("%s: %s" % (base, ", ".join(map(str, vals)))) if vals else base

    def _on_ok(self, _btn):
        f = self.panel.get_fields()
        name = (f.get("name") or "").strip()
        if not name:
            ErrorDialog(_("Cannot save"),
                        _("The helper filter needs a name."),
                        parent=self.window)
            return
        for other in self.engine.list("temp"):
            if other["name"] == name and other["id"] != self._existing_id:
                ErrorDialog(_("Cannot save"),
                            _("A helper filter named \u201c%s\u201d already "
                              "exists.") % name, parent=self.window)
                return
        try:
            self._on_commit(self._existing_id, f)
        except ValueError as exc:
            ErrorDialog(_("Cannot save"), str(exc), parent=self.window)
            return
        self.close()

    def close(self, *args):
        # Gem "Filter"-kolonnens bredde (samme moenster som byggevinduet). Kun
        # fornuftige vaerdier -- en kollapset 0-bredde (aldrig realiseret) maa
        # ikke overskrive en god vaerdi. Gaelder ALLE luk-veje (OK/Cancel/kryds).
        try:
            w = self.panel.filter_col_width()
            if w and w >= 40:
                save_ui_pref("helper_edit_col", int(w))
        except Exception:
            pass
        return super().close(*args)

    def build_menu_names(self, obj):
        return (self.title, self.title)
