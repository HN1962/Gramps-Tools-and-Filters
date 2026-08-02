#
# Gramps Plugin Registration (GPR) for the "non-birth child" rule
#
# NOTE: set gramps_target_version to YOUR Gramps version (major.minor),
# e.g. "5.2" or "6.0". You can find it under Help -> About.
# "register", "RULE", "STABLE" AND "_" are provided automatically by the
# Gramps plugin loader -- do not import or reassign them. When a locale/
# folder is present next to this file, "_" is this addon's own translator.

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
    authors_email=[""],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hasnonbirthchildrelation.py",
    ruleclass="HasNonBirthChildRelation",  # must match the class name
    namespace="Person",                    # rule in the Person category
)
