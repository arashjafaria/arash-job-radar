# ============================================================
# ARASH PROFESSIONAL PROFILE
# Based on latest CV - 2026
# ============================================================

ARASH_EXPERIENCE_YEARS = 2.5

CURRENT_LOCATION = "Munich, Germany"

CURRENT_COMPANY = "ARRK Engineering GmbH"

CURRENT_ROLE = (
    "Development Engineer - "
    "System Function Owner, USRR (ADAS)"
)

LANGUAGES = {
    "persian": "native",
    "english": "B2",
    "german": "B1",
}


# ============================================================
# ACCEPTED LOCATIONS
#
# Munich + surrounding commuter area
# Used by BMW, LinkedIn and future job sources
# ============================================================

MUNICH_AREA = [

    # --------------------------------------------------------
    # Munich itself
    # --------------------------------------------------------

    "münchen",
    "munich",
    "greater munich metropolitan area",
    "metropolregion münchen",


    # --------------------------------------------------------
    # North / North-East
    # --------------------------------------------------------

    "garching",
    "garching bei münchen",

    "unterföhring",

    "ismaning",

    "eching",

    "neufahrn",
    "neufahrn bei freising",

    "unterschleißheim",
    "oberschleißheim",

    "hallbergmoos",

    "freising",

    "erding",


    # --------------------------------------------------------
    # East / North-East
    # --------------------------------------------------------

    "aschheim",

    "feldkirchen",

    "kirchheim",
    "kirchheim bei münchen",

    "poing",

    "haar",

    "vaterstetten",

    "markt schwaben",

    "ebersberg",


    # --------------------------------------------------------
    # South / South-East
    # --------------------------------------------------------

    "ottobrunn",

    "unterhaching",

    "taufkirchen",

    "neubiberg",

    "hohenbrunn",

    "brunnthal",

    "oberhaching",

    "pullach",
    "pullach im isartal",

    "grünwald",


    # --------------------------------------------------------
    # West / North-West
    # --------------------------------------------------------

    "dachau",

    "karlsfeld",

    "fürstenfeldbruck",

    "germering",

    "puchheim",

    "olching",

    "gröbenzell",

    "maisach",


    # --------------------------------------------------------
    # South-West
    # --------------------------------------------------------

    "gräfelfing",

    "planegg",

    "krailling",

    "gauting",

    "starnberg",
]


# ============================================================
# REMOTE JOBS
#
# Remote is accepted only when the job can be performed
# from Germany.
# ============================================================

REMOTE_WORDS = [
    "remote",
    "fully remote",
    "100% remote",

    "remote germany",
    "remote within germany",
    "remote in germany",

    "home office",
    "homeoffice",

    "work from home",
    "working from home",

    "mobiles arbeiten",
    "mobile arbeit",
]


# ============================================================
# HARD EXCLUSIONS
#
# Arash is looking for professional full-time positions.
# ============================================================

EXCLUDE_WORDS = [

    # Internship
    "praktikant",
    "praktikantin",
    "praktikum",
    "internship",

    # Working student
    "werkstudent",
    "werkstudentin",
    "working student",

    # Apprenticeships
    "azubi",
    "auszubild",
    "ausbildung",
    "apprenticeship",

    # Student programs
    "duales studium",
    "dualer student",
    "dual student",

    # Thesis / academic jobs
    "studienabschlussarbeit",
    "abschlussarbeit",
    "masterarbeit",
    "bachelorarbeit",
    "thesis",

    # PhD
    "doktorand",
    "promotion",
    "phd position",

    # Other junior programs
    "trainee",

    # School internship
    "schülerpraktik",
]


# ============================================================
# SKILLS
#
# Used by BMW matcher.
# LinkedIn V4 has its own more detailed core/support weights.
# ============================================================

SKILLS = {

    # --------------------------------------------------------
    # Strongest direct experience
    # --------------------------------------------------------

    "ecu-test": 22,
    "ecu test": 22,

    "canoe": 20,

    "uds": 20,

    "can fd": 20,
    "can-fd": 20,

    "diagnostic": 18,
    "diagnostics": 18,
    "diagnose": 18,

    "dtc": 18,
    "did": 18,

    "system testing": 20,
    "system test": 20,

    "system integration testing": 22,
    "integration testing": 20,

    "requirements-based testing": 18,

    "regression testing": 16,

    "root cause": 14,
    "root-cause": 14,


    # --------------------------------------------------------
    # ADAS / Radar
    # --------------------------------------------------------

    "adas": 18,

    "radar": 18,

    "usrr": 22,

    "mrr": 14,
    "srr": 14,


    # --------------------------------------------------------
    # Automotive communication
    # --------------------------------------------------------

    "automotive ethernet": 18,

    "doip": 18,

    "some/ip": 16,

    "dlt": 14,

    "can bus": 14,


    # --------------------------------------------------------
    # Integration
    # --------------------------------------------------------

    "integration": 18,

    "vehicle integration": 18,
    "fahrzeugintegration": 18,

    "ecu": 16,
    "steuergerät": 16,


    # --------------------------------------------------------
    # Test environments
    # --------------------------------------------------------

    "hil": 16,
    "sil": 16,

    "validation": 14,
    "verification": 14,


    # --------------------------------------------------------
    # Programming / automation
    # --------------------------------------------------------

    "python": 16,

    "python automation": 18,

    "test automation": 18,
    "testautomatisierung": 18,

    "automation": 10,
    "automatisierung": 10,

    "scripting": 10,


    # CAPL and C++ are BASIC in the current CV
    "capl": 5,
    "c++": 2,


    # --------------------------------------------------------
    # Tools actually present in CV
    # --------------------------------------------------------

    "carmen": 10,

    "wireshark": 8,

    "zedis": 10,

    "e-sys": 10,
    "esys": 10,

    "ediabas": 8,

    "codebeamer": 8,

    "octane": 8,

    "jira": 6,

    "confluence": 5,

    "github": 6,


    # --------------------------------------------------------
    # General terms - intentionally low weight
    # --------------------------------------------------------

    "software": 5,

    "automotive": 5,

    "fahrzeug": 4,
    "vehicle": 4,

    "embedded": 7,

    "e/e": 8,
}


# ============================================================
# PREFERRED ROLE WORDS
# ============================================================

GOOD_ROLE_WORDS = [

    # Test
    "automotive test engineer",
    "test engineer",
    "testingenieur",

    "system test engineer",
    "system test",

    "software test engineer",
    "software testing",

    # Integration
    "system integration engineer",
    "integration engineer",
    "integrationsingenieur",

    "vehicle integration engineer",
    "fahrzeugintegration",

    # Diagnostics
    "diagnostics engineer",
    "diagnostic engineer",
    "diagnose",

    # Validation
    "validation engineer",
    "verification engineer",

    # HIL / SIL
    "hil test engineer",
    "sil test engineer",

    # ADAS
    "adas test engineer",
    "adas engineer",

    "radar test engineer",

    # Automation
    "test automation engineer",

    # Development
    "entwicklungsingenieur",
    "development engineer",

    # Systems
    "system engineer",
    "systemingenieur",
]