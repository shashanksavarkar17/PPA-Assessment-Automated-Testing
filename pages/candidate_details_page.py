from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

logger = get_logger(__name__)

class CandidateDetailsPage(BasePage):
    """
    Step 5 - Candidate Details
    """

    NAME_INPUT_LOCATOR = (By.XPATH, "//label[starts-with(normalize-space(.), 'Name')]/following::input[1]")
    MOBILE_INPUT_LOCATOR = (By.XPATH, "//label[starts-with(normalize-space(.), 'Mobile Number')]/following::input[1]")
    ROLL_NUMBER_INPUT_LOCATOR = (By.XPATH, "//label[starts-with(normalize-space(.), 'Roll Number')]/following::input[1]")
    PROCEED_BTN_LOCATOR = (By.XPATH, "//button[contains(normalize-space(.), 'Proceed')]")

    def wait_for_page_load(self):
        logger.info("Waiting for Candidate Details page...")
        self.helpers.wait_for_element(self.NAME_INPUT_LOCATOR)
        
    def fill_details_and_proceed(self, name, mobile, roll_number):
        """Fill all candidate details and submit."""
        logger.info("Filling candidate details...")
        
        self.helpers.enter_text(self.NAME_INPUT_LOCATOR, name)
        self.helpers.enter_text(self.MOBILE_INPUT_LOCATOR, mobile)
        self.helpers.enter_text(self.ROLL_NUMBER_INPUT_LOCATOR, roll_number)
        
        self.helpers.scroll_into_view(self.PROCEED_BTN_LOCATOR)
        self.helpers.click_element(self.PROCEED_BTN_LOCATOR)
        logger.info("Clicked Proceed on Candidate Details page.")
