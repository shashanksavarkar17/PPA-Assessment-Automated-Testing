from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

logger = get_logger(__name__)

class InstructionsPage(BasePage):
    """
    Step 2 - Instructions Page
    """

    HEADING_LOCATOR = (By.XPATH, "//*[contains(normalize-space(.), 'ASSESSMENT INSTRUCTIONS BY PROGRAMMING PATHSHALA')]")
    CHECKBOX_LOCATOR = (By.XPATH, "//button[@role='checkbox']")
    CONFIRM_BTN_LOCATOR = (By.XPATH, "//button[contains(normalize-space(.), 'Confirm and Proceed')]")

    def wait_for_page_load(self):
        """Wait for the main heading to be visible."""
        logger.info("Waiting for Instructions page to load...")
        self.helpers.wait_for_element(self.HEADING_LOCATOR)
        
    def validate_heading(self):
        """Validates the assessment instructions heading."""
        text = self.helpers.get_text(self.HEADING_LOCATOR)
        assert "ASSESSMENT INSTRUCTIONS BY PROGRAMMING PATHSHALA" in text, f"Heading mismatch. Found: {text}"
        logger.info("Heading validated successfully.")
        
    def accept_instructions(self):
        """Scrolls to the checkbox, clicks it, and clicks confirm."""
        self.helpers.scroll_into_view(self.CHECKBOX_LOCATOR)
        self.helpers.click_element(self.CHECKBOX_LOCATOR)
        self.helpers.click_element(self.CONFIRM_BTN_LOCATOR)
        logger.info("Instructions accepted.")
