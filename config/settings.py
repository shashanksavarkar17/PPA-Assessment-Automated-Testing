import os

# Load .env file manually if it exists
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(base_dir, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

BASE_URL = "https://instatest.programmingpathshala.com/assessment/01KS2DCCN9SHTCJ2SZM3G7BG2D"

DEFAULT_LEAKED_KEY = "AIzaSyCjM1b0E5wlVNCHa1OdDiD6TdNwfnRdYRk"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

GEMINI_API_KEYS = []
raw_keys = [
    os.environ.get("GEMINI_API_KEY", ""),
    os.environ.get("GEMINI_API_KEY_FALLBACK", ""),
]
for k in raw_keys:
    k_strip = k.strip()
    if k_strip and k_strip not in GEMINI_API_KEYS:
        GEMINI_API_KEYS.append(k_strip)

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

