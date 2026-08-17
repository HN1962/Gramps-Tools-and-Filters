# -*- coding: utf-8 -*-
#
# operatorwidget.py -- how the rules of ONE filter are combined.
#
# A dropdown with the three logical operators (all / one-is-enough / only-one).
# The long explanation for the CURRENT choice is shown just under the dropdown
# and updates when you pick a different one -- so only ONE explanation is ever
# on screen, not three. Below that, an independent "Opposite" (invert) checkbox
# whose own explanation appears only while it is ticked.
#
# This is the per-filter operator: it applies to the MAIN filter AND to every
# HELPER filter, at every level (helpers may contain helpers). One widget,
# reused everywhere.
#
# Contract (matches the engine's field names; op in ("and", "or", "one")):
#   get_op() -> "and" | "or" | "one"      set_op(op)
#   get_invert() -> bool                  set_invert(flag)
#
# English is the source language; Danish arrives via .po/.mo at the very end.

from gi.repository import Gtk, GObject, Pango

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except (ValueError, AttributeError):
    _trans = glocale.translation
_ = _trans.gettext


# (op-code, short label for the dropdown, long explanation shown below).
# op-codes are the engine's OPS -- NEVER translated, stored verbatim.
_CHOICES = (
    ("and",
     _("All rules must apply"),
     _("Included only if it matches every rule.")),
    ("or",
     _("One rule is enough"),
     _("Included as soon as it matches one of the rules (gives the most).")),
    ("one",
     _("Only one rule may apply"),
     _("Included only if it matches exactly one rule, never more "
       "(gives the fewest).")),
)

_INVERT_LABEL = _("Show the opposite result.")
_INVERT_DESC = _("Show the results that would otherwise not appear in the list.")

_INDENT = 12   # px, so the help text sits slightly in from the control


class OperatorWidget(Gtk.Box):
    """Dropdown (and / or / one) with a live description + an invert checkbox."""

    def __init__(self, on_change=None):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(4)

        self._on_change = on_change      # called when op or invert changes

        self._long = {op: long for op, _short, long in _CHOICES}

        heading = Gtk.Label(label=_("How the rules are combined:"))
        heading.set_halign(Gtk.Align.START)
        self.pack_start(heading, False, False, 0)

        # --- the dropdown: model is (op-code, short label); show column 1 ---
        store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        for op, short, _long in _CHOICES:
            store.append([op, short])
        self.combo = Gtk.ComboBox.new_with_model(store)
        cell = Gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.add_attribute(cell, "text", 1)
        self.combo.set_halign(Gtk.Align.START)
        # The dropdown shares its row with a trailing slot (combo_row) the main
        # builder fills with its action buttons, so those sit WITH the main
        # filter. The helper editor leaves the slot empty.
        self.combo_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                 spacing=6)
        self.combo_row.pack_start(self.combo, False, False, 0)
        self.pack_start(self.combo_row, False, False, 0)

        # --- live description; shares its row with a trailing slot (desc_row)
        #     for the builder's "Saved: …" status ------------------------------
        self._desc = self._help_label()
        self.desc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                spacing=6)
        self.desc_row.pack_start(self._desc, True, True, 0)
        self.pack_start(self.desc_row, False, False, 0)
        # Reserve height for the TALLEST explanation, so switching operators
        # (whose texts wrap to a different number of lines) never changes the
        # widget height -- which would make the whole window jump in size.
        self._pin_height_to_tallest(self._desc,
                                    list(self._long.values()), 48)

        # --- invert checkbox + an ALWAYS-visible one-line explanation -------
        self._invert = Gtk.CheckButton(label=_INVERT_LABEL)
        self._invert.set_margin_top(6)
        # Only the box + its label should toggle it. In a vertical box a child
        # is stretched to full width by default, which makes the whole row a
        # click target; halign=START shrinks it to its natural width.
        self._invert.set_halign(Gtk.Align.START)
        self.pack_start(self._invert, False, False, 0)

        self._invert_desc = self._help_label()
        self._invert_desc.set_text(_INVERT_DESC)
        # The invert explanation shares its row with a trailing slot. The helper
        # editor (FilterPanel compact_count=True) drops "Matches: N" in here, so
        # the count sits on this line instead of crowding the OK/Cancel buttons
        # just below it. The main builder leaves the slot empty.
        self.invert_desc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                       spacing=6)
        self.invert_desc_row.pack_start(self._invert_desc, True, True, 0)
        self.pack_start(self.invert_desc_row, False, False, 0)

        self.combo.connect("changed", self._on_combo_changed)
        self._invert.connect("toggled", self._on_invert_toggled)

        self.combo.set_active(0)                     # default "and"; fills _desc

    # ------------------------------------------------------------------
    def _help_label(self):
        lab = Gtk.Label()
        lab.set_halign(Gtk.Align.START)
        lab.set_xalign(0.0)
        lab.set_line_wrap(True)
        lab.set_max_width_chars(48)
        lab.set_margin_start(_INDENT)
        lab.get_style_context().add_class("dim-label")   # softer "help" look
        return lab

    def _pin_height_to_tallest(self, label, texts, width_chars):
        """Force `label` to always be as tall as its tallest possible text, so
        its height never changes when the text does."""
        try:
            ctx = label.get_pango_context()
            metrics = ctx.get_metrics(None, None)
            char_px = metrics.get_approximate_char_width() / Pango.SCALE
            width_px = max(1, int(char_px * width_chars))
            layout = label.create_pango_layout("")
            layout.set_width(width_px * Pango.SCALE)
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            maxh = 0
            for t in texts:
                layout.set_text(t, -1)
                _w, h = layout.get_pixel_size()
                maxh = max(maxh, h)
            if maxh > 0:
                label.set_size_request(-1, maxh)
                label.set_valign(Gtk.Align.START)
        except Exception:
            pass   # height pinning is cosmetic; never break the widget over it

    def _on_combo_changed(self, _combo):
        op = self.get_op()
        self._desc.set_text(self._long.get(op, ""))
        if self._on_change is not None:
            self._on_change()

    def _on_invert_toggled(self, _btn):
        # the description is always visible now; just recount on toggle
        if self._on_change is not None:
            self._on_change()

    # ------------------------------------------------------------------
    # contract
    # ------------------------------------------------------------------
    def get_op(self):
        it = self.combo.get_active_iter()
        if it is None:
            return "and"
        return self.combo.get_model()[it][0]

    def set_op(self, op):
        store = self.combo.get_model()
        for i, row in enumerate(store):
            if row[0] == op:
                self.combo.set_active(i)
                return
        raise ValueError("Unknown operator: %r" % (op,))

    def get_invert(self):
        return self._invert.get_active()

    def set_invert(self, flag):
        self._invert.set_active(bool(flag))
