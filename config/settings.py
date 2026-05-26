import os

# Base directory of the project.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from local .env file if it exists.
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            clean_line = line.strip()
            if clean_line and not clean_line.startswith("#") and "=" in clean_line:
                k, v = clean_line.split("=", 1)
                os.environ[k.strip()] = v.strip()

# Target assessment portal URL.
BASE_URL = "https://instatest.programmingpathshala.com/assessment/01KSHMHWQ9AEZ9VSS8PA03C71G"

# Retrieve NVIDIA API keys and model configuration from environment variables.
NVIDIA_API_KEYS = [k.strip() for k in [os.environ.get("NVIDIA_NIM_API_KEY", ""), os.environ.get("NVIDIA_NIM_API_KEY_FALLBACK", "")] if k.strip()]
NVIDIA_NIM_API_KEY = NVIDIA_API_KEYS[0] if NVIDIA_API_KEYS else ""
NVIDIA_NIM_MODEL = os.environ.get("NVIDIA_NIM_MODEL", "meta/llama-3.3-70b-instruct").strip()
NVIDIA_NIM_BASE_URL = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()

# Standard candidate credentials for registration and authentication.
TEST_USER = {
    "email": "ppa@yopmail.com",
    "name": "BOT",
    "mobile": "9999999999",
    "roll_number": "9988774455"
}

# Timeout parameters for explicit waits and OTP retrieval.
EXPLICIT_WAIT = 25
OTP_WAIT_TIMEOUT = 120

# Directory for saving execution screenshots.
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Directory for saving execution reports.
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# Manual execution mode: set to True to manually click 'Run'/'Submit' and verify each coding problem in the browser.
# If True, the script will inject the solution and pause, waiting for you to press Enter in the terminal.
MANUAL_MODE = os.environ.get("MANUAL_MODE", "false").lower() == "true"