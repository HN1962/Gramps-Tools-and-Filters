#
# Gramps addon rule: person has an event in a place (or any sub-place)
#
# Copyright (C) 2026  Henning
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
"""
Filter rule that matches people who have an event whose place lies WITHIN a
named place -- transitively, down through the whole place hierarchy. The named
place itself always counts, as does every place enclosed by it.

Place matching is by NAME (not by Gramps ID, which is brittle across upgrades
and imports). By default the name is matched exactly (case-insensitive). If the
"Use regular expressions" box is ticked, the place-name field is treated as a
regular expression instead, so patterns like "Bagen.*" or "^Skaane$" work.

If several places share a name, ALL of them are used as targets, so a duplicate
name like "Skaane" simply works.
"""

# -------------------------------------------------------------------------
# Gramps modules
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gen.lib import EventType
from gramps.gen.utils.location import located_in
from gramps.gen.const import GRAMPS_LOCALE as glocale

# Use this addon's own translation catalog (locale/<lang>/LC_MESSAGES/addon.mo)
# if present, otherwise fall back to the standard Gramps translation.
try:
    _ = glocale.get_addon_translator(__file__).gettext
except ValueError:
    _ = glocale.translation.gettext


# -------------------------------------------------------------------------
# HasEventInPlaceEnclosed
# -------------------------------------------------------------------------
class HasEventInPlaceEnclosed(Rule):
    """People with an event in a named place or any place it encloses."""

    # "Event type:" is a standard Gramps label: the rule editor recognises it
    # and renders an event-type combo automatically; its translation comes from
    # Gramps' own catalog, so we must NOT translate it in this addon.
    # "Place name:" is our own label and falls back to a plain text entry.
    labels = [_("Place name:"), _("Event type:")]
    name = _("People with an event in a place or its sub-places")
    category = _("Event filters")
    description = _(
        "Matches people who have an event whose place is the named place or "
        "lies within it, including every place enclosed by it, transitively "
        "down through the whole place hierarchy. Matching is by place name, so "
        "all places with that name are used as targets. Unticked = exact name "
        "match (not a substring); tick to use a regular expression."
    )

    # Opt into Gramps' shared regex support. This adds the standard
    # "Use regular expressions" checkbox to the rule in the editor and sets
    # self.use_regex / compiles self.regex for us before prepare() runs.
    # Unticked -> exact (case-insensitive) name match; ticked -> the place-name
    # field is a regular expression.
    allow_regex = True

    # ---------------------------------------------------------------------
    # Setup: resolve the place name to a set of target handles and parse the
    # optional event type. Done once.
    # ---------------------------------------------------------------------
    def prepare(self, db, user):
        self.db = db

        # 1) place NAME -> set of matching place handles. Compared against both
        #    the primary name value and the full title.
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

        # 2) optional event type (empty = match events of any type). The event
        #    type is always matched exactly; regex applies only to place names.
        etype_xml = (self.list[1] or "").strip()
        if etype_xml:
            self._etype = EventType()
            self._etype.set_from_xml_str(etype_xml)
        else:
            self._etype = None

    def reset(self):
        self._targets = set()

    # ---------------------------------------------------------------------
    # Core comparison. The named place itself always counts (membership),
    # and so does anything enclosed by it (located_in, which is strict).
    # ---------------------------------------------------------------------
    def _apply(self, db, person):
        if not self._targets:
            return False
        for event_ref in person.get_event_ref_list():
            if not event_ref:
                continue
            event = db.get_event_from_handle(event_ref.ref)
            if event is None:
                continue
            if self._etype is not None and event.get_type() != self._etype:
                continue
            place_handle = event.get_place_handle()
            if not place_handle:
                continue
            if place_handle in self._targets:
                return True
            if any(located_in(db, place_handle, t) for t in self._targets):
                return True
        return False

    # The rule method was renamed between Gramps 5.x ("apply") and Gramps 6.x
    # ("apply_to_one"). Define both so the same file works on either version.
    def apply(self, db, person):
        return self._apply(db, person)

    def apply_to_one(self, db, person):
        return self._apply(db, person)
