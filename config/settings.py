import os

# Hey there! Let's figure out where our main project root is located.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# If we have a local .env file, let's load those variables directly into our environment.
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            clean_line = line.strip()
            if clean_line and not clean_line.startswith("#") and "=" in clean_line:
                k, v = clean_line.split("=", 1)
                os.environ[k.strip()] = v.strip()

# This is our target test assessment portal URL.
BASE_URL = "https://instatest.programmingpathshala.com/assessment/01KRTKRPQK997GQWC0FYG8SJT3"

# We have a fallback API key just in case the environment is missing one.
DEFAULT_KEY = "AIzaSyCjM1b0E5wlVNCHa1OdDiD6TdNwfnRdYRk"

# Let's collect any available Gemini API keys from the environment to handle fallback switching.
GEMINI_API_KEYS = [k.strip() for k in [os.environ.get("GEMINI_API_KEY", ""), os.environ.get("GEMINI_API_KEY_FALLBACK", "")] if k.strip()]
if not GEMINI_API_KEYS:
    GEMINI_API_KEYS = [DEFAULT_KEY]
GEMINI_API_KEY = GEMINI_API_KEYS[0]

# Standard credentials we use to register and login as a candidate.
TEST_USER = {
    "email": "ppa@yopmail.com",
    "name": "BOT",
    "mobile": "9999999999",
    "roll_number": "9988774455"
}

# Timeout limits for page loads and our OTP extraction wait time.
EXPLICIT_WAIT = 25
OTP_WAIT_TIMEOUT = 120

# Setup paths for logs and screen captures, making sure the directory exists!
LOG_FILE = os.path.join(BASE_DIR, "automation.log")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
