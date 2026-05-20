import os

BASE_URL = "https://instatest.programmingpathshala.com/assessment/01KRTKRPQK997GQWC0FYG8SJT3"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyB1VPCVN9F238N_XNcnVkuKCAnDTftSfzE")

GEMINI_API_KEYS = [
    key.strip() for key in [
        os.environ.get("GEMINI_API_KEY", "AIzaSyB1VPCVN9F238N_XNcnVkuKCAnDTftSfzE"),
    ] if key.strip()
]

TEST_USER = {
    "email": "ppa@yopmail.com",
    "name": "BOT",
    "mobile": "9999999999",
    "roll_number": "9988774455"
}

EXPLICIT_WAIT = 20
OTP_WAIT_TIMEOUT = 120

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "automation.log")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
