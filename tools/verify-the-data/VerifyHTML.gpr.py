# -*- coding: utf-8 -*-
#
# Registration for the VerifyHTML tool.
#
# NOTE:
# "register", "TOOL", "STABLE", "TOOL_ANAL", "TOOL_MODE_GUI" and "_" are
# provided automatically by the Gramps plugin loader -- do not import or
# reassign them. gramps_target_version is read from the running Gramps via
# "major_version", so the same file fits 5.2 / 6.0 / master without any
# manual edits.

from gramps.version import major_version, VERSION_TUPLE

if VERSION_TUPLE >= (5, 2, 0):
    register(
        TOOL,
        id="verifyhtml",
        name=_("Verify the Data \u2192 HTML report"),
        description=_(
            "Runs the built-in \"Verify the Data\" checks and saves the result as "
            "a sortable HTML report in which reviewed items can be ticked off.\n\n"
            "The report reuses the built-in checks, so it automatically follows "
            "along when Gramps adds or improves them. Thresholds (maximum age, "
            "young parent, and so on) are taken from the built-in \"Verify the "
            "Data\" tool. Those settings are only stored when that tool is actually "
            "run, so run \"Verify the Data\" once with your preferred values before "
            "generating this report."
        ),
        version="1.0.0",
        gramps_target_version=major_version,
        status=STABLE,
        fname="VerifyHTML.py",
        authors=["Henning"],
        authors_email=["contact@myown-project.dk"],
        category=TOOL_ANAL,
        toolclass="VerifyHTMLTool",
        optionclass="VerifyHTMLOptions",
        tool_modes=[TOOL_MODE_GUI],
        help_url="https://myown-project.dk/tools/verify-the-data/index.html",
    )
