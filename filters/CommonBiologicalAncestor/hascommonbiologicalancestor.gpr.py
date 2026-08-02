#
# Gramps Plugin Registration (GPR) for the "Common biological ancestor" rule
#
# NOTE: set gramps_target_version to YOUR Gramps version (major.minor),
# e.g. "5.2" or "6.0". You can find it under Help -> About.
# "register", "RULE", "STABLE" AND "_" are provided automatically by the
# Gramps plugin loader -- do not import or reassign them. When a locale/
# folder is present next to this file, "_" is this addon's own translator.

register(
    RULE,
    id="HasCommonBiologicalAncestorWith",
    name=_("People with a common biological ancestor with <person>"),
    description=_(
        "Matches people who share a biological ancestor; only birth "
        "relationships are followed, so purely adopted and foster children "
        "are excluded."
    ),
    version="1.0.0",
    authors=["Henning"],
    authors_email=[""],
    gramps_target_version="6.0",
    status=STABLE,
    fname="hascommonbiologicalancestor.py",
    ruleclass="HasCommonBiologicalAncestorWith",  # must match the class name
    namespace="Person",                           # rule in the Person category
)
