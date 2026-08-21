#
# Gramps Plugin Registration (GPR) for the "named place and its sub-places" rule
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
# Gramps plugin loader. When a locale/ folder is present next to this file,
# "_" is this addon's own translator.

from gramps.version import major_version, VERSION_TUPLE

if VERSION_TUPLE >= (5, 1, 0):
    args = {
        "id": "PlaceInNamedPlaceEnclosed",
        "name": _("Places within a named place or its sub-places"),
        "description": _(
            "Matches a named place and every place enclosed by it "
            "(by place name)."
        ),
        "version": "1.0.0",
        "authors": ["Henning"],
        "authors_email": ["https://myown-project.dk"],
        "gramps_target_version": major_version,
        "status": STABLE,
        "fname": "placeinnamedplaceenclosed.py",   # must match your .py file
        "ruleclass": "PlaceInNamedPlaceEnclosed",   # must match the class name
        "namespace": "Place",                       # rule in the Places view
    }
    # help_url may only be set on GRAMPLET plugins before Gramps 5.2; setting it
    # on a rule under 5.1 raises and hides the plugin, so add it from 5.2 on.
    if VERSION_TUPLE >= (5, 2, 0):
        args["help_url"] = (
            "https://myown-project.dk/tools/gramps-filter-rules/"
            "place-in-named-place-enclosed"
        )
    register(RULE, **args)
