import os

# --- Assessment URLs ---
BASE_URL = "https://instatest.programmingpathshala.com/assessment/01KRTKRPQK997GQWC0FYG8SJT3"

# --- API Keys ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyB1VPCVN9F238N_XNcnVkuKCAnDTftSfzE")

# --- Test Data ---
TEST_USER = {
    "email": "narumodi@yopmail.com",
    "name": "BOT",
    "mobile": "9999999999",
    "roll_number": "9988774455"
}

# --- Timeouts ---
EXPLICIT_WAIT = 20  # standard explicit wait in seconds
OTP_WAIT_TIMEOUT = 120  # seconds to wait for manual OTP entry

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "automation.log")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

# Create directories if they don't exist
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
