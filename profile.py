# ============================================================
# ARASH PROFESSIONAL MATCHING PROFILE
# Authoritative basis: Arash final CV + user clarifications
# Updated: 2026-09-28
# ============================================================

ARASH_EXPERIENCE_YEARS = 3.0
MAX_REQUIRED_EXPERIENCE_YEARS = 3

MIN_MATCH_PERCENT = 60
SENIOR_MIN_MATCH_PERCENT = 75

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

DRIVING_LICENSE_B = True


# ============================================================
# ACCEPTED ONSITE LOCATIONS
# Roughly Munich + ~150 km commuter/relocation radius.
# Remote jobs anywhere in Germany are also accepted.
# ============================================================

MUNICH_AREA = [
    "münchen", "munich",
    "greater munich metropolitan area",
    "metropolregion münchen",

    "garching", "garching bei münchen",
    "unterföhring", "ismaning", "eching",
    "neufahrn", "neufahrn bei freising",
    "unterschleißheim", "oberschleißheim",
    "hallbergmoos", "freising", "erding",

    "aschheim", "feldkirchen",
    "kirchheim", "kirchheim bei münchen",
    "poing", "haar", "vaterstetten",
    "markt schwaben", "ebersberg",

    "ottobrunn", "unterhaching", "taufkirchen",
    "neubiberg", "hohenbrunn", "brunnthal",
    "oberhaching", "pullach", "pullach im isartal",
    "grünwald",

    "dachau", "karlsfeld", "fürstenfeldbruck",
    "germering", "puchheim", "olching",
    "gröbenzell", "maisach",

    "gräfelfing", "planegg", "krailling",
    "gauting", "starnberg",

    # Extended ~150 km area
    "augsburg",
    "ingolstadt",
    "rosenheim",
    "landshut",
    "regensburg",
    "ulm",
    "memmingen",
    "kaufbeuren",
    "kempten",
    "traunstein",
    "bad tölz",
    "bad toelz",
    "holzkirchen",
    "miesbach",
    "wasserburg am inn",
    "wasserburg",
    "pfaffenhofen an der ilm",
    "pfaffenhofen",
    "neuburg an der donau",
    "neuburg",
    "donauwörth",
    "donauwoerth",
    "landsberg am lech",
    "landsberg",
    "weilheim",
    "wolfratshausen",
    "murnau",
    "garmisch-partenkirchen",
]


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
# ============================================================

EXCLUDE_WORDS = [
    "praktikant", "praktikantin", "praktikum", "internship",
    "werkstudent", "werkstudentin", "working student",
    "azubi", "auszubild", "ausbildung", "apprenticeship",
    "duales studium", "dualer student", "dual student",
    "studienabschlussarbeit", "abschlussarbeit",
    "masterarbeit", "bachelorarbeit", "thesis",
    "doktorand", "promotion", "phd position",
    "trainee", "schülerpraktik",
]


# ============================================================
# SKILL LEVELS
# 1 = Basic, 2 = Intermediate, 3 = Professional
# ============================================================

SKILL_LEVELS = {
    # Strong direct V&V / diagnostics
    "ecu-test": 3,
    "amts": 3,
    "canoe": 3,
    "can fd": 3,
    "uds": 3,
    "restbus": 3,
    "xcp": 3,
    "diagnostics": 3,
    "dtc": 3,
    "did": 3,
    "system testing": 3,
    "system integration testing": 3,
    "requirements-based testing": 3,
    "regression testing": 3,
    "defect analysis": 3,
    "root cause analysis": 3,

    # User-confirmed hands-on / daily-work technologies
    "iso 26262": 2,
    "autosar": 2,
    "adaptive autosar": 2,
    "ci/cd": 3,
    "git": 3,
    "vteststudio": 1,
    "odx": 3,
    "pdx": 3,
    "ethernet diagnostics": 3,
    "some/ip-sd": 3,
    "restbus simulation": 3,
    "vector vt": 2,
    "canalyzer": 2,

    # Current CV / clarified level
    "python": 2,
    "hil": 2,
    "sil": 2,
    "automotive ethernet": 2,
    "doip": 2,
    "some/ip": 2,
    "dlt": 2,
    "capl": 1,
    "c++": 1,

    # Current project / domain knowledge
    "adas": 3,
    "radar": 3,
    "lidar": 2,
    "usrr": 3,
    "mrr": 2,
    "srr": 2,
    "ecu": 3,
    "sensor": 2,
    "vehicle integration": 3,

    # Tools used in CV / daily work
    "carmen": 2,
    "wireshark": 2,
    "zedis": 3,
    "e-sys": 3,
    "ediabas": 2,
    "codebeamer": 3,
    "octane": 3,
    "jira": 2,
    "confluence": 2,
    "github": 3,
}


SKILL_ALIASES = {
    "ecu-test": [
        "ecu-test", "ecu test", "ecutest",
        "tracetronic ecu-test", "tracetronic ecu test",
        "tracetronic", "trace tronic",
    ],
    "amts": ["amts", "amts regression"],
    "canoe": ["canoe", "vector canoe"],
    "can fd": ["can fd", "can-fd"],
    "uds": ["uds", "unified diagnostic services"],
    "restbus": ["restbus", "rest bus"],
    "xcp": ["xcp"],
    "diagnostics": [
        "diagnostic", "diagnostics", "diagnose",
        "diagnostic testing", "diagnoseentwicklung",
    ],
    "dtc": ["dtc", "diagnostic trouble code"],
    "did": ["did", "data identifier"],
    "system testing": ["system testing", "system test", "systemtest"],
    "system integration testing": [
        "system integration testing",
        "integration testing",
        "systemintegrationstest",
        "system integration test",
    ],
    "requirements-based testing": [
        "requirements-based testing",
        "requirement based testing",
        "anforderungsbasiert",
    ],
    "regression testing": [
        "regression testing", "regression test",
        "regressionstest",
    ],
    "defect analysis": [
        "defect analysis", "defect investigation",
        "fehleranalyse", "issue analysis",
    ],
    "root cause analysis": [
        "root cause", "root-cause",
        "ursachenanalyse",
    ],

    "iso 26262": ["iso 26262", "functional safety", "funktionale sicherheit"],
    "autosar": ["autosar", "classic autosar"],
    "adaptive autosar": ["adaptive autosar", "autosar adaptive"],
    "ci/cd": ["ci/cd", "continuous integration", "continuous delivery"],
    "git": [" git ", "git workflow", "git repository", "gitlab"],
    "vteststudio": ["vteststudio", "vtest studio", "vector vteststudio"],
    "odx": ["odx"],
    "pdx": ["pdx"],
    "ethernet diagnostics": [
        "ethernet diagnostics", "diagnostics over ethernet",
        "ethernet diagnostic",
    ],
    "some/ip-sd": ["some/ip-sd", "some/ip sd", "service discovery"],
    "restbus simulation": [
        "restbus simulation", "rest bus simulation",
        "restbussimulation",
    ],
    "vector vt": ["vector vt", "vt system", "vector vt system"],
    "canalyzer": ["canalyzer", "vector canalyzer"],

    "python": ["python", "pybus"],
    "hil": ["hil", "hardware-in-the-loop", "hardware in the loop"],
    "sil": ["sil", "software-in-the-loop", "software in the loop"],
    "automotive ethernet": ["automotive ethernet", "100base-t1", "1000base-t1"],
    "doip": ["doip", "diagnostics over ip"],
    "some/ip": ["some/ip", "some ip"],
    "dlt": ["dlt", "diagnostic log and trace"],
    "capl": ["capl"],
    "c++": ["c++"],

    "adas": ["adas", "advanced driver assistance"],
    "radar": ["radar", "usrr", "mrr", "srr"],
    "lidar": ["lidar", "laser scanner"],
    "usrr": ["usrr", "ultra short range radar"],
    "mrr": ["mrr", "mid range radar", "medium range radar"],
    "srr": ["srr", "short range radar"],
    "ecu": ["ecu", "steuergerät", "steuergeraet", "electronic control unit"],
    "sensor": ["sensor", "sensors", "sensorik"],
    "vehicle integration": [
        "vehicle integration", "fahrzeugintegration",
        "e/e integration", "ee integration",
    ],

    "carmen": ["carmen"],
    "wireshark": ["wireshark"],
    "zedis": ["zedis"],
    "e-sys": ["e-sys", "esys"],
    "ediabas": ["ediabas"],
    "codebeamer": ["codebeamer"],
    "octane": ["octane"],
    "jira": ["jira"],
    "confluence": ["confluence"],
    "github": ["github"],
}


# ============================================================
# TARGET ROLE WORDS - English + German
# ============================================================

GOOD_ROLE_WORDS = [
    "research and development engineer",
    "r&d engineer",
    "forschungs- und entwicklungsingenieur",
    "forschungsingenieur",
    "entwicklungsingenieur",
    "development engineer",

    "test and validation engineer",
    "test & validation engineer",
    "test- und validierungsingenieur",
    "testingenieur",
    "test engineer",
    "validation engineer",
    "validierungsingenieur",

    "verification and qualification engineer",
    "verification engineer",
    "verifikationsingenieur",
    "qualifikationsingenieur",

    "software engineer",
    "softwareingenieur",
    "software test engineer",
    "software tester",

    "system tester",
    "systemtester",
    "system test engineer",
    "system engineer",
    "systems engineer",
    "systemingenieur",

    "system integration engineer",
    "integration engineer",
    "integrationsingenieur",
    "vehicle integration engineer",
    "fahrzeugintegrationsingenieur",

    "requirements engineer",
    "requirement engineer",
    "anforderungsingenieur",

    "automotive engineer",
    "automotive ingenieur",
    "fahrzeugingenieur",

    "vehicle test engineer",
    "fahrzeugtestingenieur",
    "erprobungsingenieur",
    "versuchsingenieur",

    "diagnostics engineer",
    "diagnostic engineer",
    "diagnoseingenieur",
    "diagnoseentwickler",
    "diagnostic test engineer",

    "hil test engineer",
    "sil test engineer",
    "adas test engineer",
    "adas engineer",
    "radar test engineer",
    "lidar engineer",
    "sensor engineer",
    "test automation engineer",
]


# ============================================================
# Legacy numeric weights retained for older source code.
# ============================================================

SKILLS = {
    key: (
        22 if level == 3
        else 15 if level == 2
        else 6
    )
    for key, level in SKILL_LEVELS.items()
}
