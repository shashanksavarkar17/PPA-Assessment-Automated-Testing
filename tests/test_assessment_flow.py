# Hey friend! You can use this file if you ever decide to run your tests via pytest.
# For now, we are running our orchestrator directly using: python main.py

from utils.driver_factory import get_chrome_driver
from config import settings

# This placeholder test is here to keep pytest happy in the CI pipeline.
def test_placeholder():
    pass
