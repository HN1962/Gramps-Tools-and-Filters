#
# Gramps Plugin Registration (GPR) for the "common biological ancestor" rule
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

if VERSION_TUPLE >= (5, 2, 0):
    register(
        RULE,
        id="HasCommonBiologicalAncestorWith",
        name=_("People with a common biological ancestor with <person>"),
        description=_(
            "Matches people who share a common ancestor with a specified "
            "person, following biological parent-child links only "
            "(adoptive, foster and step relationships are excluded)."
        ),
        version="1.1.0",
        authors=["Henning"],
        authors_email=["https://myown-project.dk"],
        gramps_target_version=major_version,
        status=STABLE,
        fname="hascommonbiologicalancestor.py",  # must match your .py file
        ruleclass="HasCommonBiologicalAncestorWith",  # must match the class name
        namespace="Person",                           # rule in the Person category
        help_url="https://myown-project.dk/tools/gramps-filter-rules/common-biological-ancestor",
    )
