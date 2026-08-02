# -*- coding: utf-8 -*-
#
# Registration for the VerifyHTML tool.
#
# NOTE: gramps_target_version must match your Gramps version (major.minor).
#       On Gramps 5.2, change "6.0" below to "5.2".
#
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
    gramps_target_version="6.0",
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
