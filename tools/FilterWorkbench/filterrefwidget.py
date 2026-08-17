# -*- coding: utf-8 -*-
#
# filterrefwidget.py -- composite argument widget for the forked EditRule.
#
# When a rule needs a filter argument (label "Filter name:" / "Person filter
# name:"), the user must pick ONE filter -- either a MAIN filter or a HELPER
# filter. Hence TWO comboboxes, so the choice is section-unambiguous. The id
# lives under the hood (in the model); the name is shown. That means:
#   * no name<->id translation, and
#   * no ambiguity if a main and a helper filter share a name.
#
# The widget honours the SAME contract as Gramps' own argument widgets, so it
# drops straight into the EditRule grid in place of a single MyFilters:
#   get_text() -> str   returns the selected filter's STABLE id ("" if none)
#   set_text(val)       val is an id; selects the right box ("" clears both)
#
# The widget does NOT know the engine: the dialog fetches the lists
# (engine.list("main") / engine.list("temp")) and passes them as (id, name)
# lists, plus an optional callback for INLINE creation of a helper filter.

from gi.repository import Gtk, GObject

# Translator -- same pattern as Gramps' own addons (Danish .po can be added).
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except (ValueError, AttributeError):
    _trans = glocale.translation
_ = _trans.gettext


_NONE_ID = ""          # sentinel id for the "(select ...)" top row
_LABEL_WIDTH = 110     # px, so the two rows line up


class FilterRefWidget(Gtk.Box):
    """Two comboboxes (main + helper) that together pick ONE filter id.

    Parameters
    ----------
    main_items, helper_items : iterable of (id, name)
        The two lists to show. The dialog builds them like:
            main   = [(f["id"], f["name"]) for f in engine.list("main")]
            helper = [(f["id"], f["name"]) for f in engine.list("temp")]
    exclude_id : str | None
        Id of the filter currently being edited -- excluded from both lists so
        trivial self-reference is impossible. None during first build (the
        filter has no id yet).
    """

    def __init__(self, main_items, helper_items, exclude_id=None):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(6)

        self._exclude_id = exclude_id
        self._guard = False                    # breaks the mutual-exclusion loop
        self._helper_items = list(helper_items)  # kept for the initial fill

        # --- Main filters ---
        self.main_combo = self._make_combo()
        self.pack_start(self._labelled(_("Main filters:"), self.main_combo),
                        False, False, 0)

        # --- Helper filters (pick an existing one; new helpers are created and
        #     given rules from the builder's "Helper filters" list) ---
        self.helper_combo = self._make_combo()
        helper_row = Gtk.Box()
        helper_row.set_orientation(Gtk.Orientation.HORIZONTAL)
        helper_row.set_spacing(6)
        helper_row.pack_start(self.helper_combo, True, True, 0)
        self.pack_start(self._labelled(_("Helper filters:"), helper_row),
                        False, False, 0)

        # fill BEFORE connecting handlers, so the initial set_active(0) is silent
        self._fill(self.main_combo, main_items)
        self._fill(self.helper_combo, self._helper_items)

        self.main_combo.connect("changed", self._on_main_changed)
        self.helper_combo.connect("changed", self._on_helper_changed)

        self.show_all()

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    def _make_combo(self):
        # model: (id, display name); id in column 0, name shown from column 1
        store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        combo = Gtk.ComboBox.new_with_model(store)
        cell = Gtk.CellRendererText()
        combo.pack_start(cell, True)
        combo.add_attribute(cell, "text", 1)
        combo.set_hexpand(True)
        return combo

    def _labelled(self, text, widget):
        row = Gtk.Box()
        row.set_orientation(Gtk.Orientation.HORIZONTAL)
        row.set_spacing(6)
        lab = Gtk.Label(label=text, halign=Gtk.Align.END)
        lab.set_size_request(_LABEL_WIDTH, -1)
        row.pack_start(lab, False, False, 0)
        row.pack_start(widget, True, True, 0)
        return row

    def _fill(self, combo, items):
        store = combo.get_model()
        store.clear()
        store.append([_NONE_ID, _("(select …)")])
        for fid, name in sorted(items, key=lambda t: (t[1] or "").lower()):
            if self._exclude_id is not None and fid == self._exclude_id:
                continue                       # never trivial self-reference
            store.append([fid, name])
        combo.set_active(0)

    # ------------------------------------------------------------------
    # mutual exclusion: a choice in one box clears the other
    # ------------------------------------------------------------------
    def _on_main_changed(self, combo):
        if self._guard:
            return
        if self._active_id(combo):
            self._guard = True
            self.helper_combo.set_active(0)
            self._guard = False

    def _on_helper_changed(self, combo):
        if self._guard:
            return
        if self._active_id(combo):
            self._guard = True
            self.main_combo.set_active(0)
            self._guard = False

    # ------------------------------------------------------------------
    # contract: get_text / set_text  (the id is the "truth")
    # ------------------------------------------------------------------
    def _active_id(self, combo):
        it = combo.get_active_iter()
        if it is None:
            return ""
        return combo.get_model()[it][0] or ""

    def get_text(self):
        """Return the selected filter's id, or "" if nothing is selected."""
        return self._active_id(self.main_combo) or self._active_id(self.helper_combo)

    def set_text(self, val):
        """Select the filter with id=val in the right box; "" clears both."""
        self._guard = True
        try:
            in_main = self._select(self.main_combo, val)
            if not in_main:
                self.main_combo.set_active(0)
            if in_main:
                self.helper_combo.set_active(0)
            else:
                self._select(self.helper_combo, val)  # sets 0 if not found
        finally:
            self._guard = False

    def _select(self, combo, fid):
        store = combo.get_model()
        if not fid:
            combo.set_active(0)
            return False
        for i, row in enumerate(store):
            if row[0] == fid:
                combo.set_active(i)
                return True
        combo.set_active(0)
        return False

    # ------------------------------------------------------------------
    # small helpers for the dialog (optional)
    # ------------------------------------------------------------------
    def has_selection(self):
        return bool(self.get_text())
