#
# Gramps Plugin Registration (GPR) for the "non-birth child" rule
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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# NOTE: 
# "register", "RULE", "STABLE" AND "_" are provided automatically by the
# Gramps plugin loader -- do not import or reassign them. When a locale/
# folder is present next to this file, "_" is this addon's own translator.

from gramps.version import major_version, VERSION_TUPLE

if VERSION_TUPLE >= (5, 2, 0):
    register(
        RULE,
        id="HasNonBirthChildRelation",
        name=_("People recorded as a non-birth child"),
        description=_(
            "Matches people recorded as a child with a non-birth relationship "
            "to a parent (adopted, foster, step, etc.). Helps review that child "
            "relationship types are set correctly."
        ),
        version="1.1.0",
        authors=["Henning"],
        authors_email=["https://myown-project.dk"],
        gramps_target_version=major_version,
        status=STABLE,
        fname="hasnonbirthchildrelation.py",
        ruleclass="HasNonBirthChildRelation",  # must match the class name
        namespace="Person",                    # rule in the Person category
        help_url= "https://myown-project.dk/tools/gramps-filter-rules/non-birth-child-relation",
    )