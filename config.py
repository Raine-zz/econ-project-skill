import os

# =============================================================================
# SECRETS (read from env vars / GitHub Secrets — NEVER hardcode)
# =============================================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# =============================================================================
# AGENT MODEL
# =============================================================================
AGENT_MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")

# =============================================================================
# TARGET TARGETS  (school tiers / regions to crawl)
# =============================================================================
PRIORITY_SCHOOLS: list[dict] = [
    # ---- UK ----
    {"name": "LSE", "region": "Europe", "country": "UK", "city": "London"},
    {"name": "University of Oxford", "region": "Europe", "country": "UK", "city": "Oxford"},
    {"name": "University of Cambridge", "region": "Europe", "country": "UK", "city": "Cambridge"},

    # ---- Europe (strong econ & "jump-board" masters) ----
    {"name": "Toulouse School of Economics", "region": "Europe", "country": "France", "city": "Toulouse"},
    {"name": "Paris School of Economics", "region": "Europe", "country": "France", "city": "Paris"},
    {"name": "Bocconi University", "region": "Europe", "country": "Italy", "city": "Milan"},
    {"name": "University of Bonn", "region": "Europe", "country": "Germany", "city": "Bonn"},
    {"name": "University of Mannheim", "region": "Europe", "country": "Germany", "city": "Mannheim"},
    {"name": "Stockholm School of Economics", "region": "Europe", "country": "Sweden", "city": "Stockholm"},
    {"name": "Tinbergen Institute", "region": "Europe", "country": "Netherlands", "city": "Amsterdam"},
    {"name": "Tilburg University", "region": "Europe", "country": "Netherlands", "city": "Tilburg"},
    {"name": "KU Leuven", "region": "Europe", "country": "Belgium", "city": "Leuven"},
    {"name": "University of Zurich", "region": "Europe", "country": "Switzerland", "city": "Zurich"},
    {"name": "ETH Zurich", "region": "Europe", "country": "Switzerland", "city": "Zurich"},
    {"name": "Sciences Po", "region": "Europe", "country": "France", "city": "Paris"},
    {"name": "Erasmus University Rotterdam", "region": "Europe", "country": "Netherlands", "city": "Rotterdam"},
    {"name": "University of Copenhagen", "region": "Europe", "country": "Denmark", "city": "Copenhagen"},

    # ---- HK3 + SG2 ----
    {"name": "University of Hong Kong", "region": "Asia", "country": "Hong Kong", "city": "Hong Kong"},
    {"name": "Chinese University of Hong Kong", "region": "Asia", "country": "Hong Kong", "city": "Hong Kong"},
    {"name": "Hong Kong University of Science and Technology", "region": "Asia", "country": "Hong Kong", "city": "Hong Kong"},
    {"name": "National University of Singapore", "region": "Asia", "country": "Singapore", "city": "Singapore"},
    {"name": "Nanyang Technological University", "region": "Asia", "country": "Singapore", "city": "Singapore"},

    # ---- US Top-30 Econ (sample — extend as needed) ----
    {"name": "Harvard University", "region": "North America", "country": "US", "city": "Cambridge, MA"},
    {"name": "MIT", "region": "North America", "country": "US", "city": "Cambridge, MA"},
    {"name": "Stanford University", "region": "North America", "country": "US", "city": "Stanford, CA"},
    {"name": "UC Berkeley", "region": "North America", "country": "US", "city": "Berkeley, CA"},
    {"name": "University of Chicago", "region": "North America", "country": "US", "city": "Chicago, IL"},
    {"name": "Princeton University", "region": "North America", "country": "US", "city": "Princeton, NJ"},
    {"name": "Yale University", "region": "North America", "country": "US", "city": "New Haven, CT"},
    {"name": "Columbia University", "region": "North America", "country": "US", "city": "New York, NY"},
    {"name": "New York University", "region": "North America", "country": "US", "city": "New York, NY"},
    {"name": "Northwestern University", "region": "North America", "country": "US", "city": "Evanston, IL"},
    {"name": "University of Pennsylvania", "region": "North America", "country": "US", "city": "Philadelphia, PA"},
    {"name": "UCLA", "region": "North America", "country": "US", "city": "Los Angeles, CA"},
    {"name": "Duke University", "region": "North America", "country": "US", "city": "Durham, NC"},
    {"name": "University of Michigan", "region": "North America", "country": "US", "city": "Ann Arbor, MI"},
    {"name": "University of Wisconsin–Madison", "region": "North America", "country": "US", "city": "Madison, WI"},
]

# =============================================================================
# URL SEED LIST — each school's main Econ / Finance program page
# Agent can follow *on-domain* links to admission/requirement pages
# =============================================================================
SEED_URLS: list[dict] = [
    # -- UK --
    {"school": "LSE", "url": "https://www.lse.ac.uk/economics/graduate/programmes"},
    {"school": "University of Oxford", "url": "https://www.ox.ac.uk/admissions/graduate/courses/economics"},
    {"school": "University of Cambridge", "url": "https://www.postgraduate.study.cam.ac.uk/courses/departments/acec"},

    # -- Europe --
    {"school": "Toulouse School of Economics", "url": "https://www.tse-fr.eu/admission-masters"},
    {"school": "Paris School of Economics", "url": "https://www.parisschoolofeconomics.eu/en/teaching/masters-programmes/"},
    {"school": "Bocconi University", "url": "https://www.unibocconi.eu/economics-and-social-sciences"},
    {"school": "Bonn Graduate School of Economics", "url": "https://www.bgse.uni-bonn.de/master"},
    {"school": "University of Mannheim", "url": "https://www.uni-mannheim.de/economics/"},
    {"school": "Stockholm School of Economics", "url": "https://www.hhs.se/en/education/msc/me/"},
    {"school": "Tinbergen Institute", "url": "https://www.tinbergen.nl/graduate-program"},
    {"school": "Tilburg University", "url": "https://www.tilburguniversity.edu/education/masters-programmes/economics"},
    {"school": "Sciences Po", "url": "https://www.sciencespo.fr/economics/"},
    {"school": "Erasmus University Rotterdam", "url": "https://www.eur.nl/en/education/master/economics-and-business"},

    # -- HK + SG --
    {"school": "University of Hong Kong", "url": "https://www.sef.hku.hk/programmes/postgraduate/"},
    {"school": "CUHK", "url": "https://www.econ.cuhk.edu.hk/econ/en-gb/programmes"},
    {"school": "HKUST", "url": "https://econ.hkust.edu.hk/programs/postgraduate"},
    {"school": "NUS", "url": "https://fass.nus.edu.sg/ecs/graduate/"},
    {"school": "NTU", "url": "https://www.ntu.edu.sg/education/graduate-programme/master-of-science-in-applied-economics"},

    # -- US --
    {"school": "Harvard University", "url": "https://economics.harvard.edu/graduate"},
    {"school": "MIT", "url": "https://economics.mit.edu/academic-program/graduate"},
    {"school": "Stanford University", "url": "https://economics.stanford.edu/graduate"},
    {"school": "UC Berkeley", "url": "https://www.econ.berkeley.edu/graduate"},
    {"school": "University of Chicago", "url": "https://economics.uchicago.edu/graduate/"},
    {"school": "Princeton University", "url": "https://economics.princeton.edu/graduate-program/"},
    {"school": "Yale University", "url": "https://economics.yale.edu/graduate"},
    {"school": "Columbia University", "url": "https://econ.columbia.edu/graduate/"},
    {"school": "New York University", "url": "https://as.nyu.edu/departments/econ/graduate.html"},
    {"school": "Northwestern University", "url": "https://economics.northwestern.edu/graduate/"},
    {"school": "University of Pennsylvania", "url": "https://economics.sas.upenn.edu/graduate"},
    {"school": "Duke University", "url": "https://econ.duke.edu/graduate"},
    {"school": "University of Michigan", "url": "https://lsa.umich.edu/econ/graduate-studies.html"},
    {"school": "University of Wisconsin–Madison", "url": "https://econ.wisc.edu/graduate/"},
]

# =============================================================================
# TARGET KEYWORDS — used for quick pre-filtering (agent does the deep reading)
# =============================================================================
TARGET_KEYWORDS = [
    "economics", "econometrics", "finance", "financial economics",
    "political economy", "applied economics", "public policy",
    "development economics", "behavioral economics", "quantitative economics",
    "data science for economics", "economic history",
]

# =============================================================================
# DEGREE TYPE MAPPINGS
# =============================================================================
DEGREE_TYPES = ["MSc", "MA", "MPhil", "MRes", "PhD", "DPhil", "Direct PhD", "Joint / Dual Degree"]

# =============================================================================
# NOTION FIELD MAPPING  (adjust to match your Notion database property names)
# =============================================================================
NOTION_FIELD_MAP = {
    "Institution": "Institution",
    "Program": "Program",
    "Website": "Website",
    "Requirement": "Requirement",
    "Project Link": "Project Link",
    "Region": "Region",
    "Country": "Country",
    "City": "City",
    "Degree Type": "Degree Type",
    "Orientation": "Orientation",
    "Preference": "Preference",
    "Process": "Process",
    "Due Date": "Due Date",
    "Days to Prepare": "Days to Prepare",
    "Admission": "Admission",
    "Application Deadline": "Application Deadline",
    "Study Period": "Study Period",
    "Tuition": "Tuition",
    "Language": "Language",
    "IELTS": "IELTS",
    "GRE": "GRE",
    "GPA": "GPA",
    "CV": "CV",
    "Core Requirements": "Core Requirements",
    "Field": "Field",
    "Notes": "Notes",
    "Interview": "Interview",
    "Importance": "Importance",
    "Summary": "Summary",
}

# Maps agent output field names to the keys used for rich_text lookups
# (agent fields differ from the Notion property names used above)
AGENT_TO_NOTION_FIELD = {
    "institution":                     "Institution",
    "program":                         "Program",
    "website":                         "Website",
    "requirement":                     "Requirement",
    "project_link":                    "Project Link",
    "region":                          "Region",
    "country":                         "Country",
    "city":                            "City",
    "degree_type":                     "Degree Type",
    "orientation":                     "Orientation",
    "preference":                      "Preference",
    "process":                         "Process",
    "due_date":                        "Due Date",
    "application_deadline_text":       "Application Deadline",
    "admission":                       "Admission",
    "study_period":                    "Study Period",
    "tuition":                         "Tuition",
    "language_of_instruction":         "Language",
    "ielts_requirement":               "IELTS",
    "gre_requirement":                 "GRE",
    "gpa_requirement":                 "GPA",
    "cv_requirement":                  "CV",
    "core_requirements":               "Core Requirements",
    "field":                           "Field",
    "notes":                           "Notes",
    "interview":                       "Interview",
    "importance":                      "Importance",
    "summary":                         "Summary",
}

# =============================================================================
# SCRAPING CONFIG
# =============================================================================
REQUEST_TIMEOUT = 30
MAX_DEPTH = 2           # max link depth from seed URL (on-domain only)
MAX_PAGES_PER_SCHOOL = 8

# =============================================================================
# SCHEDULE CONFIG
# =============================================================================
HIGH_IMPORTANCE_THRESHOLD = 7   # featured first in Slack summary

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
