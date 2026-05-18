from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

logger = get_logger(__name__)

class StartTestPage(BasePage):
    """
    Step 6 - Start Test
    """

    START_TEST_BTN_LOCATOR = (By.XPATH, "//button[contains(normalize-space(.), 'Start Test')]")

    def wait_for_page_load(self):
        logger.info("Waiting for Start Test page...")
        self.helpers.wait_for_element(self.START_TEST_BTN_LOCATOR)
        
    def click_start_test(self):
        """Click the Start Test button."""
        self.helpers.scroll_into_view(self.START_TEST_BTN_LOCATOR)
        self.helpers.click_element(self.START_TEST_BTN_LOCATOR)
        logger.info("Clicked Start Test button.")
