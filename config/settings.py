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
BASE_URL = "https://instatest.programmingpathshala.com/assessment/01KSAM1KYPSH8N2BNJ7JKFW8DC"

# Let's collect any available NVIDIA API keys and endpoints from the environment.
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "").strip()
NVIDIA_NIM_MODEL = os.environ.get("NVIDIA_NIM_MODEL", "meta/llama-3.1-70b-instruct").strip()
NVIDIA_NIM_BASE_URL = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()

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

# Setup paths for screen captures, making sure the directory exists!
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
