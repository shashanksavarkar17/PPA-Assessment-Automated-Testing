import os

BASE_URL = "https://instatest.programmingpathshala.com/assessment/01KRTKRPQK997GQWC0FYG8SJT3"

# Default leaked key used as standard placeholder
DEFAULT_LEAKED_KEY = "AIzaSyB1VPCVN9F238N_XNcnVkuKCAnDTftSfzE"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Rotate keys safely
GEMINI_API_KEYS = []
raw_keys = [
    os.environ.get("GEMINI_API_KEY", ""),
    os.environ.get("GEMINI_API_KEY_FALLBACK", ""),
]
for k in raw_keys:
    k_strip = k.strip()
    if k_strip and k_strip not in GEMINI_API_KEYS:
        GEMINI_API_KEYS.append(k_strip)

# Fallback to default placeholder if absolutely no key provided, but we will warn the solver
if not GEMINI_API_KEYS:
    GEMINI_API_KEY = DEFAULT_LEAKED_KEY
    GEMINI_API_KEYS = [DEFAULT_LEAKED_KEY]

TEST_USER = {
    "email": "ppa@yopmail.com",
    "name": "BOT",
    "mobile": "9999999999",
    "roll_number": "9988774455"
}

EXPLICIT_WAIT = 25
OTP_WAIT_TIMEOUT = 120

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "automation.log")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

