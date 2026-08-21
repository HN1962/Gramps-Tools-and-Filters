#
# Gramps Plugin Registration (GPR) for the "event in place (or sub-place)" rule
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026      Henning
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.
#

# NOTE:
# "register", "RULE", "STABLE" AND "_" are provided automatically by the
# Gramps plugin loader -- do not import or reassign them. When a locale/
# folder is present next to this file, "_" is this addon's own translator.

from gramps.version import major_version, VERSION_TUPLE

if VERSION_TUPLE >= (5, 1, 0):
    args = {
        "id": "HasEventInPlaceEnclosed",
        "name": _("People with an event in a place or its sub-places"),
        "description": _(
            "Matches people who have an event whose place is a named place "
            "or lies within it and everything enclosed by it."
        ),
        "version": "1.0.0",
        "authors": ["Henning"],
        "authors_email": ["https://myown-project.dk"],
        "gramps_target_version": major_version,
        "status": STABLE,
        "fname": "haseventinplaceenclosed.py",   # must match your .py file
        "ruleclass": "HasEventInPlaceEnclosed",   # must match the class name
        "namespace": "Person",                    # rule in the Person category
    }
    # help_url may only be set on GRAMPLET plugins before Gramps 5.2. Setting
    # it on a rule under 5.1 raises inside register() and hides the whole
    # plugin, so only add it from 5.2 onwards.
    if VERSION_TUPLE >= (5, 2, 0):
        args["help_url"] = (
            "https://myown-project.dk/tools/gramps-filter-rules/"
            "event-in-place-enclosed"
        )
    register(RULE, **args)
