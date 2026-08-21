#
# Gramps addon rule: a named place and everything enclosed by it
#
# Copyright (C) 2026  Henning
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
"""
Place filter rule that matches the named place itself plus every place that
lies WITHIN it -- transitively, down through the whole place hierarchy.

This is a NAME-based companion to Gramps' built-in "IsEnclosedBy" rule, which
selects by Gramps ID. Names are self-documenting and stable across backend
upgrades, backup import and version switches, where IDs are not. If several
places share a name, ALL of them are used as targets.

By default the name is matched exactly (case-insensitive). Tick "Use regular
expressions" to treat the place-name field as a regular expression instead,
e.g. "Bagen.*" or "^Skaane$".
"""

# -------------------------------------------------------------------------
# Gramps modules
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gen.utils.location import located_in
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _ = glocale.get_addon_translator(__file__).gettext
except ValueError:
    _ = glocale.translation.gettext


# -------------------------------------------------------------------------
# PlaceInNamedPlaceEnclosed
# -------------------------------------------------------------------------
class PlaceInNamedPlaceEnclosed(Rule):
    """A named place and every place it encloses."""

    # "Place name:" is our own label -> a plain text entry.
    labels = [_("Place name:")]
    name = _("Places within a named place or its sub-places")
    # Same category as the built-in place enclosure rule (IsEnclosedBy).
    category = _("General filters")
    description = _(
        "Matches places that are the named place or lie within it, including "
        "every place enclosed by it, transitively down through the whole place "
        "hierarchy. Matching is by place name, so all places with that name are "
        "used as targets. Unticked = exact name match (not a substring); tick "
        "to use a regular expression."
    )

    # Opt into Gramps' shared regex support: adds the standard "Use regular
    # expressions" checkbox. Unticked -> exact (case-insensitive) match;
    # ticked -> the place-name field is a regular expression.
    allow_regex = True

    def prepare(self, db, user):
        self.db = db
        raw = (self.list[0] or "").strip()
        self._targets = set()
        if raw:
            use_regex = getattr(self, "use_regex", False)
            compiled = None
            if use_regex:
                regexes = getattr(self, "regex", None)
                if regexes:
                    compiled = regexes[0]

            if use_regex and compiled is not None:
                def matches(text):
                    return compiled.search(text) is not None
            else:
                needle = raw.casefold()
                def matches(text):
                    return text.strip().casefold() == needle

            for handle in db.get_place_handles():
                place = db.get_place_from_handle(handle)
                if place is None:
                    continue
                candidates = []
                pname = place.get_name()
                if pname is not None and pname.get_value():
                    candidates.append(pname.get_value())
                ptitle = place.get_title()
                if ptitle:
                    candidates.append(ptitle)
                if any(c and matches(c) for c in candidates):
                    self._targets.add(place.handle)

    def reset(self):
        self._targets = set()

    def _apply(self, db, place):
        if not self._targets:
            return False
        handle = place.handle
        # the named place itself always counts...
        if handle in self._targets:
            return True
        # ...as does anything enclosed by it (located_in is strict)
        if any(located_in(db, handle, t) for t in self._targets):
            return True
        return False

    # apply (Gramps 5.x) / apply_to_one (Gramps 6.x); both receive a Place.
    def apply(self, db, place):
        return self._apply(db, place)

    def apply_to_one(self, db, place):
        return self._apply(db, place)
