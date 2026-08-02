#
# Gramps addon rule: people recorded as a non-birth child
#
# Copyright (C) 2026  Henning
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
"""
Filter rule that matches people who are recorded as a child with a
relationship to a parent OTHER than "Birth".

It is a review/QA companion to the "Common biological ancestor" rule: run
it to list everyone marked as adopted, foster, step, sponsored, etc. and
confirm those relationship types are set correctly. The biological rule
can only be as accurate as these labels, and in Gramps the DEFAULT
relationship for a new child is "Birth", so a mislabeled adopted/foster
child silently looks biological.

The relationship type is chosen from a drop-down list in the filter
editor. The first entry, "(any non-birth)", matches every non-birth
relationship at once; the remaining entries narrow the match to a single
type.
"""

# -------------------------------------------------------------------------
# Gramps modules (all GUI-free, safe to import in headless/CLI use)
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gen.lib import ChildRefType
from gramps.gen.const import GRAMPS_LOCALE as glocale

# Use this addon's own translation catalog (locale/<lang>/LC_MESSAGES/addon.mo)
# if present, otherwise fall back to the standard Gramps translation.
try:
    _ = glocale.get_addon_translator(__file__).gettext
except ValueError:
    _ = glocale.translation.gettext


# -------------------------------------------------------------------------
# Drop-down widget for the filter editor.
#
# The Gramps filter editor lets a rule supply its own GUI element by using
# a (label, factory) tuple as a label; the editor calls factory(db). We use
# that hook to offer a drop-down of child-relationship types.
#
# GTK is imported LAZILY inside the factory so that merely importing this
# rule (e.g. for command-line filtering) never pulls in the GUI.
# -------------------------------------------------------------------------
def _child_relation_widget(db):
    from gi.repository import Gtk

    class _ChildRelCombo(Gtk.ComboBox):
        """Combo box: shows localized names, returns language-neutral keys.

        For the built-in types the stored value is the English keyword
        (xml_str), so a saved filter keeps working after an interface-
        language change. For user-defined (custom) types the stored value
        is the type string itself. An empty value means "any non-birth
        relationship".
        """

        def __init__(self):
            store = Gtk.ListStore(str, str)  # (display, stored value)
            store.append([_("(any non-birth)"), ""])
            seen = set()
            for value in (
                ChildRefType.ADOPTED,
                ChildRefType.FOSTER,
                ChildRefType.STEPCHILD,
                ChildRefType.SPONSORED,
                ChildRefType.NONE,
                ChildRefType.UNKNOWN,
            ):
                crt = ChildRefType(value)
                store.append([str(crt), crt.xml_str()])
                seen.add(str(crt).lower())

            # Custom child-relationship types recorded in THIS database, e.g.
            # a user-defined "udlagt barnefader". For custom types the stored
            # value is the string itself.
            try:
                customs = db.get_child_reference_types() if db is not None else []
            except Exception:
                customs = []
            for custom in sorted(set(customs)):
                if custom and custom.lower() not in seen:
                    store.append([custom, custom])
                    seen.add(custom.lower())

            Gtk.ComboBox.__init__(self, model=store)
            cell = Gtk.CellRendererText()
            self.pack_start(cell, True)
            self.add_attribute(cell, "text", 0)
            self.set_active(0)

        def get_text(self):
            it = self.get_active_iter()
            if it is None:
                return ""
            return self.get_model().get_value(it, 1)

        def set_text(self, val):
            target = (val or "").lower()
            model = self.get_model()
            for idx, row in enumerate(model):
                if row[1].lower() == target:
                    self.set_active(idx)
                    return
            self.set_active(0)

    return _ChildRelCombo()


# -------------------------------------------------------------------------
# HasNonBirthChildRelation
# -------------------------------------------------------------------------
class HasNonBirthChildRelation(Rule):
    """People recorded as a child with a non-birth relationship."""

    # A (label, widget-factory) tuple tells the editor to build our own
    # drop-down instead of a plain text field.
    labels = [(_("Child relationship type:"), _child_relation_widget)]
    name = _("People recorded as a non-birth child")
    category = _("Family filters")
    description = _(
        "Matches people who are recorded as a child with a relationship to "
        "a parent other than 'Birth'. Choose a single type from the list "
        "(Adopted, Foster, Stepchild, Sponsored, None, Unknown) or the "
        "first entry '(any non-birth)' to match them all. Useful for "
        "reviewing that child relationship types are set correctly before "
        "relying on biological-only filters."
    )

    def prepare(self, db, user):
        self.db = db
        # stored value: English keyword, or "" meaning "any non-birth"
        self.wanted = (self.list[0] or "").strip().lower()

    def _rel_matches(self, rel):
        if self.wanted:
            # accept either the localized name or the English keyword
            names = {str(rel).lower(), rel.xml_str().lower()}
            return self.wanted in names
        # no specific type chosen -> anything that is not "Birth"
        return int(rel) != ChildRefType.BIRTH

    def _apply(self, db, person):
        for fam_handle in person.get_parent_family_handle_list():
            fam = db.get_family_from_handle(fam_handle)
            if fam is None:
                continue
            for cref in fam.get_child_ref_list():
                if cref.ref != person.handle:
                    continue
                for rel in (cref.get_father_relation(),
                            cref.get_mother_relation()):
                    if self._rel_matches(rel):
                        return True
        return False

    # The rule method was renamed between Gramps 5.x ("apply") and Gramps
    # 6.x ("apply_to_one"). Define both so the file works on either version.
    def apply(self, db, person):
        return self._apply(db, person)

    def apply_to_one(self, db, person):
        return self._apply(db, person)
