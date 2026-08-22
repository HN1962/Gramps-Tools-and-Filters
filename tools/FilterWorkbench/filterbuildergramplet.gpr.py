# -*- coding: utf-8 -*-
#
# filterbuildergramplet.gpr.py -- registration for the FilterWorkbench
# gramplet.
#
# Add it in the People view sidebar (Add a gramplet -> FilterWorkbench),
# where it can push filters to the person list. GRAMPLET, register, STABLE and
# _ are injected by Gramps; do not import them. gramps_target_version is read
# from gramps.version so one file fits 5.2 / 6.0 / master.

from gramps.version import VERSION_TUPLE

register(
    GRAMPLET,
    id="FilterWorkbenchGramplet",
    name=_("FilterWorkbench"),
    description=_("Use, build, edit and share your own person filters, "
                  "separate from Gramps' own filter list."),
    version="1.1.0",
    gramps_target_version="%d.%d" % (VERSION_TUPLE[0], VERSION_TUPLE[1]),
    status=STABLE,
    fname="filterbuildergramplet.py",
    height=300,
    gramplet="FilterWorkbenchGramplet",
    gramplet_title=_("FilterWorkbench"),
    navtypes=["Person"],
    authors=["Henning"],
    authors_email=["contact@myown-project.dk"],
)
