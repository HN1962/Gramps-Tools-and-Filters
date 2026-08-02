#
# Gramps addon rule: common BIOLOGICAL ancestor
#
# Copyright (C) 2026  Henning
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
"""
Filter rule that matches people who share a BIOLOGICAL ancestor with a
specified person.

Unlike the built-in rule
    "People with a common ancestor with <person>"  (HasCommonAncestorWith)
this rule follows parent/child links ONLY when the child's relationship
to the parent is "Birth".

Adopted, foster, step and sponsored children are therefore included only
if they are ALSO recorded as a birth child in a biological family. A
child that appears solely in an adoptive/foster family is given no
ancestors beyond itself and will not match through that family.
"""

# -------------------------------------------------------------------------
# Gramps modules
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
# HasCommonBiologicalAncestorWith
# -------------------------------------------------------------------------
class HasCommonBiologicalAncestorWith(Rule):
    """People who share a biological ancestor with <person>."""

    labels = [_("ID:")]
    name = _("People with a common biological ancestor with <person>")
    category = _("Ancestral filters")
    description = _(
        "Matches people that share a biological (blood) ancestor with a "
        "specified person. Only birth relationships are followed; adopted, "
        "foster, step and sponsored children are not included unless they "
        "are also a birth child in a biological family."
    )

    # ---------------------------------------------------------------------
    # Setup: compute the reference person's biological ancestors once.
    # ---------------------------------------------------------------------
    def prepare(self, db, user):
        self.db = db
        # handle -> set of (the person itself + all biological ancestors)
        self.ancestor_cache = {}
        root = db.get_person_from_gramps_id(self.list[0])
        if root:
            self.add_ancs(db, root)
            self.with_people = [root.handle]
        else:
            self.with_people = []

    def reset(self):
        self.ancestor_cache = {}

    # ---------------------------------------------------------------------
    # Core: build the ancestor set, but follow ONLY birth relationships.
    # ---------------------------------------------------------------------
    def add_ancs(self, db, person):
        if person is None or person.handle in self.ancestor_cache:
            return

        # A person counts as their own "ancestor". This makes two people in
        # a direct descending line (e.g. parent and child) share a common
        # ancestor.
        self.ancestor_cache[person.handle] = {person.handle}

        for fam_handle in person.get_parent_family_handle_list():
            fam = db.get_family_from_handle(fam_handle)
            if fam is None:
                continue

            # Locate this person's child reference in the family and read
            # the relationship to the father and to the mother.
            frel = mrel = None
            for cref in fam.get_child_ref_list():
                if cref.ref == person.handle:
                    frel = cref.get_father_relation()
                    mrel = cref.get_mother_relation()
                    break

            father_is_birth = frel == ChildRefType.BIRTH
            mother_is_birth = mrel == ChildRefType.BIRTH

            # Not a birth relationship in this family (e.g. a pure adoptive
            # or foster family) -> skip the family entirely.
            if not (father_is_birth or mother_is_birth):
                continue

            no_birth_parent_recorded = True
            for par_handle, is_birth in (
                (fam.get_father_handle(), father_is_birth),
                (fam.get_mother_handle(), mother_is_birth),
            ):
                if par_handle and is_birth:
                    no_birth_parent_recorded = False
                    par = db.get_person_from_handle(par_handle)
                    if par:
                        self.add_ancs(db, par)
                        self.ancestor_cache[person.handle] |= \
                            self.ancestor_cache[par.handle]

            # Biological family whose parents are not recorded: use the
            # family handle itself as a shared "token" so that full siblings
            # still match each other. (Same trick as the built-in rule, but
            # applied only to birth families.)
            if no_birth_parent_recorded:
                self.ancestor_cache[person.handle].add(fam_handle)

    # ---------------------------------------------------------------------
    # Comparison: does the person share an ancestor with the reference?
    # ---------------------------------------------------------------------
    def has_common_ancestor(self, other):
        if other is None or other.handle not in self.ancestor_cache:
            return False
        other_ancs = self.ancestor_cache[other.handle]
        for handle in self.with_people:
            if handle in self.ancestor_cache and \
                    (self.ancestor_cache[handle] & other_ancs):
                return True
        return False

    def _apply(self, db, person):
        if person is not None and person.handle not in self.ancestor_cache:
            self.add_ancs(db, person)
        return self.has_common_ancestor(person)

    # ---------------------------------------------------------------------
    # The rule method was renamed between Gramps 5.x ("apply") and Gramps
    # 6.x ("apply_to_one"). We define both so the same file works on either
    # version. Both receive a Person object.
    # ---------------------------------------------------------------------
    def apply(self, db, person):
        return self._apply(db, person)

    def apply_to_one(self, db, person):
        return self._apply(db, person)
