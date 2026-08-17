# -*- coding: utf-8 -*-
#
# filterbuildergramplet.py -- the FilterWorkbench gramplet.
#
# Lives in the People view sidebar. It is a small console over the per-tree
# store of MAIN filters (FilterWorkbench's own filters, kept completely
# separate from Gramps' native filter list):
#
#   Saved filters (dropdown)  -> engine.list("main")
#   Apply filter              -> engine.apply_to_view(id, view)   (like Gramps)
#   New                       -> open the builder on a NEW main filter
#   Edit                      -> open the builder on the SELECTED main filter
#   Reset                     -> engine.reset_view(view)          (show all)
#   Delete                    -> engine.delete(id)  (Gramps' menu Delete only
#                                touches Gramps' own filters, so ours lives here)
#   Import / Export           -> the WHOLE per-tree file (all main + helpers),
#                                moved between family trees
#
# The builder module and engine are imported at LOAD time (the timing that
# works); any import failure is captured so the buttons surface a real traceback
# instead of failing silently.

import os
import sys
import traceback

from gi.repository import Gtk, Pango

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except Exception:
    _trans = glocale.translation
_ = _trans.gettext

from gramps.gen.plug import Gramplet
from gramps.gui.dialog import ErrorDialog

# belt-and-braces: keep this folder importable
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# import the builder module + engine at LOAD time; capture any failure
_IMPORT_ERROR = None
try:
    import filterbuilder as _fb
    from filterengine import FilterEngine
except Exception:
    _fb = None
    FilterEngine = None
    _IMPORT_ERROR = traceback.format_exc()


class FilterWorkbenchGramplet(Gramplet):

    # ------------------------------------------------------------------ setup
    def init(self):
        self._engine = None
        self._applied_fid = None      # hvilket hovedfilter der LIGE NU er anvendt
        self.gui.WIDGET = self._build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show_all()
        self._reload_filters()
        # Fej evt. efterladte koere-filtre fra en TIDLIGERE session i samme
        # Gramps-proces (panelet fjernet og lagt paa igen, byggevindue lukket
        # haardt i en aeldre version osv.). Sikkert: rammer kun __flow_-navne der
        # ikke er live.
        if FilterEngine:
            try:
                self._ensure_engine().sweep_orphans()
            except Exception:
                pass

    def db_changed(self):
        # A different tree was opened -> its own per-tree file governs now.
        # Ryd foerst vores egne koere-filtre (__flow_) ud af den delte
        # CustomFilters + fej evt. efterladte lig, saa de ikke haenger med over
        # i det nye traeet (og bliver til restart-affald).
        if self._engine is not None:
            try:
                self._engine.cleanup()
                self._engine.sweep_orphans()
            except Exception:
                pass
        self._engine = None
        self._applied_fid = None
        self._reload_filters()

    def _build_gui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        # Explicit margins (a little more on the right, which read as too tight).
        box.set_margin_start(10)
        box.set_margin_end(16)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        info = Gtk.Label()
        info.set_halign(Gtk.Align.START)
        info.set_xalign(0.0)
        info.set_line_wrap(True)
        info.set_text(_("FilterWorkbench is for beginners and slightly "
                        "experienced users who understand how the 3 ways of "
                        "combining rules work."))
        box.pack_start(info, False, False, 0)

        # --- saved-filter picker -----------------------------------------
        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.START)
        lbl.set_markup("<b>%s</b>" % _("Saved filters"))
        box.pack_start(lbl, False, False, 0)

        self.combo = Gtk.ComboBoxText()
        self.combo.connect("changed", lambda *_a: self._update_sensitivity())
        box.pack_start(self.combo, False, False, 0)

        # --- run / show-all ----------------------------------------------
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row1.set_homogeneous(True)
        row1.set_margin_top(4)
        # Anvend / Nulstil er nu ikon-only (som New/Edit/Delete) -- "Anvend
        # filter" klippede pladsen. Oeje = "vis de matchede"; hus = "hjem/vis
        # alle" (cirkelpilen laestes som Edge's genindlaes, hvilket den IKKE goer).
        # Det danske ord staar stadig i tooltip'en ved hover.
        self.btn_use = self._icon_button(
            "view-reveal-symbolic", self._on_use,
            _("Apply filter — show the people it matches"))
        self.btn_reset = self._icon_button(
            "go-home-symbolic", self._on_reset,
            _("Reset — show all people again"))
        row1.pack_start(self.btn_use, True, True, 0)
        row1.pack_start(self.btn_reset, True, True, 0)
        box.pack_start(row1, False, False, 0)

        # --- manage (new / edit / delete) --------------------------------
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row2.set_homogeneous(True)
        # New / Edit / Delete are icon-only (same family as the validated
        # trash icon). Icons never truncate the way the Danish labels do
        # ("Rediger" -> "Red..."); the localized word still shows on hover.
        self.btn_new = self._icon_button(
            "list-add-symbolic", self._on_new,
            _("Build a new main filter"))
        self.btn_edit = self._icon_button(
            "document-edit-symbolic", self._on_edit,
            _("Edit the selected main filter"))
        self.btn_delete = self._icon_button(
            "user-trash-symbolic", self._on_delete,
            _("Delete the selected main filter"))
        row2.pack_start(self.btn_new, True, True, 0)
        row2.pack_start(self.btn_edit, True, True, 0)
        row2.pack_start(self.btn_delete, True, True, 0)
        box.pack_start(row2, False, False, 0)

        # --- import / export (whole file, between trees) -----------------
        row3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row3.set_homogeneous(True)
        row3.set_margin_top(4)
        self.btn_import = self._button(_("Import"), self._on_import,
                                       _("Add filters from another tree's "
                                         "file (existing filters are kept)"))
        self.btn_export = self._button(_("Export"), self._on_export,
                                       _("Save all this tree's filters to a "
                                         "file"))
        row3.pack_start(self.btn_import, True, True, 0)
        row3.pack_start(self.btn_export, True, True, 0)
        box.pack_start(row3, False, False, 0)

        features = Gtk.Label()
        features.set_halign(Gtk.Align.START)
        features.set_xalign(0.0)
        features.set_line_wrap(True)
        features.get_style_context().add_class("dim-label")
        # Afloeser de to gamle fod-tekster: samler funktions-oversigten ét sted
        # (pkt. 4 daekker den tidligere "wb_<navn> i Gramps' lister"-tekst).
        features.set_text(_(
            "New features include:\n"
            "1. While building, rules/filters can be tested in the person view "
            "before saving.\n"
            "2. Helper filters no longer clutter the main filter list.\n"
            "3. Helper filters can be reused.\n"
            "4. Main and helper filters appear in Gramps' filter lists as "
            "wb_<name>, but only while applied in the person view.\n"
            "5. Import/Export to another device.\n"
            "6. A feature description everyone can understand."))
        box.pack_start(features, False, False, 0)

        return box

    def _button(self, label, handler, tooltip=None):
        btn = Gtk.Button(label=label)
        # Allow the label to ellipsize so the button can shrink below its
        # natural width. Without this, the homogeneous button rows force a
        # minimum width; when the sidebar is dragged narrower than that, GTK
        # clips the overflow on the right and eats the panel's right margin.
        child = btn.get_child()
        if isinstance(child, Gtk.Label):
            child.set_ellipsize(Pango.EllipsizeMode.END)
        btn.connect("clicked", handler)
        if tooltip:
            btn.set_tooltip_text(tooltip)
        return btn

    def _icon_button(self, icon_name, handler, tooltip=None):
        """A compact icon button (used for Delete: a trash can never truncates
        the way a text label does, and reads as 'destructive' at a glance)."""
        btn = Gtk.Button()
        btn.set_image(Gtk.Image.new_from_icon_name(icon_name,
                                                   Gtk.IconSize.BUTTON))
        btn.set_always_show_image(True)
        btn.connect("clicked", handler)
        if tooltip:
            btn.set_tooltip_text(tooltip)
        return btn

    # -------------------------------------------------------------- plumbing
    def _parent(self):
        return self.uistate.window

    def _import_ok(self):
        """True if the builder module + engine loaded; else show the traceback."""
        err = _IMPORT_ERROR or (getattr(_fb, "_IMPORT_ERROR", None) if _fb else None)
        if err:
            ErrorDialog(_("FilterWorkbench failed to load"), err,
                        parent=self._parent())
            return False
        return True

    def _confirm(self, text):
        """Yes/No confirmation, same widget the builder uses for import."""
        q = Gtk.MessageDialog(
            transient_for=self._parent(), modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO, text=text)
        # A yes/no confirm has no meaningful geometry to persist; center it on
        # the main window so it always appears in a predictable place (was
        # popping up at the WM's default spot, esp. on Linux).
        q.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        proceed = (q.run() == Gtk.ResponseType.YES)
        q.destroy()
        return proceed

    def _ensure_engine(self):
        # Create ONCE and load ONCE. Do NOT reload on every access: a mutation
        # like delete() lives in memory until save(), so a reload between the
        # two would silently undo it. Freshness comes from explicit reload()
        # calls (below) at the right moments instead.
        if self._engine is None:
            self._engine = FilterEngine(self.dbstate, namespace="Person")
            self._engine.load()
        return self._engine

    def _reload(self):
        """Re-read THIS tree's file into the (single) engine."""
        try:
            self._ensure_engine().load()
        except Exception:
            pass

    def _view(self):
        # In the People sidebar self.gui.view IS the person list (has
        # generic_filter). Elsewhere it isn't, and apply/reset say so clearly.
        return getattr(self.gui, "view", None)

    def _reload_filters(self, select_id=None):
        """Rebuild the dropdown from the store. Keep the current selection when
        possible, or select select_id (e.g. a just-saved filter)."""
        if not FilterEngine:
            return
        keep = select_id or self._selected_id()
        try:
            eng = self._ensure_engine()
            eng.load()                 # pick up writes the builder just made
            mains = sorted(eng.list("main"),
                           key=lambda f: f["name"].lower())
        except Exception:
            mains = []
        self.combo.remove_all()
        ids = []
        for f in mains:
            self.combo.append(f["id"], f["name"])
            ids.append(f["id"])
        if keep in ids:
            self.combo.set_active_id(keep)
        elif ids:
            self.combo.set_active(0)
        self._update_sensitivity()

    def _selected_id(self):
        return self.combo.get_active_id()

    def _selected_name(self):
        return self.combo.get_active_text() or ""

    def _update_sensitivity(self):
        has_sel = self._selected_id() is not None
        for b in (self.btn_use, self.btn_edit, self.btn_delete):
            b.set_sensitive(has_sel)
        # export makes sense only when there is something to export
        self.btn_export.set_sensitive(
            self.combo.get_model() is not None
            and len(self.combo.get_model()) > 0)

    # --------------------------------------------------------------- actions
    def _on_use(self, _btn):
        fid = self._selected_id()
        if not fid:
            return
        view = self._view()
        try:
            eng = self._ensure_engine()
            eng.load()                 # be current with the builder's last save
            eng.apply_to_view(fid, view)
            self._applied_fid = fid    # husk hvad der er anvendt (til slet/reset)
        except RuntimeError:
            ErrorDialog(_("Cannot apply filter"),
                        _("Open this from the People view to show matches "
                          "in the person list."),
                        parent=self._parent())
        except Exception:
            ErrorDialog(_("Cannot apply filter"), traceback.format_exc(),
                        parent=self._parent())

    def _on_reset(self, _btn):
        try:
            eng = self._ensure_engine()
            eng.reset_view(self._view())
            eng.sweep_orphans()        # + evt. lig fra et lukket byggevindue
            self._applied_fid = None
        except Exception:
            ErrorDialog(_("Cannot reset"), traceback.format_exc(),
                        parent=self._parent())

    def _open_builder(self, main_id=None, new=False):
        if not self._import_ok():
            return
        try:
            _fb._FilterBuilderWindow(
                self.dbstate, self.uistate, [], view=self._view(),
                main_id=main_id, new=new, on_change=self._reload_filters)
        except Exception as exc:
            if type(exc).__name__ == "WindowActiveError":
                return          # a builder is already open -> brought forward
            ErrorDialog(_("FilterWorkbench failed to open"),
                        traceback.format_exc(), parent=self._parent())

    def _on_new(self, _btn):
        self._open_builder(new=True)

    def _on_edit(self, _btn):
        fid = self._selected_id()
        if not fid:
            return
        self._open_builder(main_id=fid)

    def _on_delete(self, _btn):
        fid = self._selected_id()
        if not fid:
            return
        name = self._selected_name()
        if not self._confirm(
                _("Delete the main filter \u201c%s\u201d? "
                  "This cannot be undone.") % name):
            return
        try:
            eng = self._ensure_engine()
            eng.load()                 # current disk truth before mutating
            ok, users = eng.delete(fid)
            if not ok:
                ErrorDialog(
                    _("Cannot delete"),
                    _("\u201c%s\u201d is still used by: %s")
                    % (name, ", ".join(users)),
                    parent=self._parent())
                return
            eng.save()                 # SAME engine, no reload in between
        except Exception:
            ErrorDialog(_("Cannot delete"), traceback.format_exc(),
                        parent=self._parent())
            return
        # Slettede vi det filter der LIGE NU er anvendt paa personlisten, saa
        # nulstil visningen: filteret findes ikke laengere, saa det skal hverken
        # blive ved med at filtrere listen eller staa tilbage som wb_<navn> i
        # Gramps' vaelgere. Et ANDET (ikke-anvendt) filter roerer visningen ikke.
        if fid == self._applied_fid:
            try:
                eng.reset_view(self._view())
                eng.sweep_orphans()
            except Exception:
                pass
            self._applied_fid = None
        self._reload_filters()

    def _on_export(self, _btn):
        if not self._import_ok():
            return
        eng = self._ensure_engine()
        eng.load()                     # export the current on-disk state
        dlg = Gtk.FileChooserDialog(
            title=_("Export filters"), transient_for=self._parent(),
            action=Gtk.FileChooserAction.SAVE)
        dlg.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dlg.add_button(_("Export"), Gtk.ResponseType.OK)
        try:
            dlg.set_current_folder(eng.base_dir())
        except Exception:
            pass
        dlg.set_current_name("easyfilter_export.json")
        flt = Gtk.FileFilter()
        flt.set_name(_("JSON files"))
        flt.add_pattern("*.json")
        dlg.add_filter(flt)
        path = None
        if dlg.run() == Gtk.ResponseType.OK:
            path = dlg.get_filename()
            if path and not path.lower().endswith(".json"):
                path += ".json"
        dlg.destroy()
        if not path:
            return
        try:
            eng.export_to(path)
        except Exception:
            ErrorDialog(_("Cannot export"), traceback.format_exc(),
                        parent=self._parent())

    def _on_import(self, _btn):
        if not self._import_ok():
            return
        eng = self._ensure_engine()
        dlg = Gtk.FileChooserDialog(
            title=_("Import filters"), transient_for=self._parent(),
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dlg.add_button(_("Import"), Gtk.ResponseType.OK)
        try:
            dlg.set_current_folder(eng.base_dir())
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
        # MERGE (never replace): add the file's filters, skip any whose name is
        # already here. Preview the plan first so the confirm can state it.
        try:
            eng.load()                     # current disk truth before comparing
            info = eng.file_info(path)
            plan = eng.merge_from(path, apply=False)
        except Exception:
            ErrorDialog(_("Cannot import"), traceback.format_exc(),
                        parent=self._parent())
            return
        src = ((info or {}).get("name") or (info or {}).get("id")
               or _("another tree"))
        added = plan["added_main"] + plan["added_temp"]
        nskip = len(plan["skipped"])
        if added == 0 and nskip == 0:
            ErrorDialog(_("Nothing to import"),
                        _("\u201c%s\u201d has no filters.") % src,
                        parent=self._parent())
            return
        lines = [_("Add %d filter(s) from \u201c%s\u201d to this tree?")
                 % (added, src)]
        if nskip:
            shown = ", ".join(sorted(set(plan["skipped"]))[:8])
            if len(set(plan["skipped"])) > 8:
                shown += " \u2026"
            lines.append("")
            lines.append(_("%d filter(s) are already here (same filter) and "
                           "will be skipped: %s") % (nskip, shown))
        renamed = plan.get("renamed", [])
        if renamed:
            rshown = ", ".join("%s \u2192 %s" % (o, n)
                               for (o, n) in renamed[:8])
            if len(renamed) > 8:
                rshown += " \u2026"
            lines.append("")
            lines.append(_("%d filter(s) share a name with a DIFFERENT local "
                           "filter and will be added under a new name (the "
                           "imported filters keep pointing at these): %s")
                         % (len(renamed), rshown))
        lines.append("")
        lines.append(_("Your existing filters are not changed."))
        try:
            missing = eng.missing_rules(path)
        except Exception:
            missing = []
        if missing:
            mshown = ", ".join(missing[:10])
            if len(missing) > 10:
                mshown += " \u2026"
            lines.append("")
            lines.append(_("WARNING: %d rule type(s) used by these filters are "
                           "not installed in this Gramps. Affected filters will "
                           "import but fail when used until you install the "
                           "matching rule add-on(s): %s") % (len(missing), mshown))
        if not self._confirm("\n".join(lines)):
            return
        try:
            eng.merge_from(path, apply=True)
            eng.save()                     # persist into THIS tree
        except Exception:
            ErrorDialog(_("Cannot import"), traceback.format_exc(),
                        parent=self._parent())
            return
        self._reload_filters()
