import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

logger = get_logger(__name__)

class SummaryPage(BasePage):
    """
    Step 7 - Overall Summary Page
    """

    SECTIONS_LOCATOR = (By.CLASS_NAME, "section-container-class") 
    SOLVE_BUTTONS_LOCATOR = (By.XPATH, "//button[contains(text(), 'Solve')]")
    
    def wait_for_page_load(self):
        logger.info("Waiting for Summary page to load...")
        self.helpers.wait_for_element(self.SOLVE_BUTTONS_LOCATOR)
        
    def get_all_sections(self):
        """Dynamically detect all sections."""
        try:
            sections = self.driver.find_elements(*self.SECTIONS_LOCATOR)
            return sections
        except Exception as e:
            logger.error(f"Failed to detect sections: {e}")
            self.helpers.take_screenshot("detect_sections_failed")
            return []
            
    def start_first_section(self):
        """Click 'Solve' on the first section."""
        logger.info("Attempting to start the first section...")
        try:
            self.helpers.wait_for_element(self.SOLVE_BUTTONS_LOCATOR)
            solve_buttons = self.driver.find_elements(*self.SOLVE_BUTTONS_LOCATOR)
            
            if not solve_buttons:
                raise Exception("No 'Solve' buttons found on the page.")
                
            first_solve_button = solve_buttons[0]
            
            self.driver.execute_script("arguments[0].scrollIntoView(true);", first_solve_button)
            time.sleep(0.5)
            
            first_solve_button.click()
            logger.info("Successfully clicked 'Solve' for the first section.")
            
        except Exception as e:
            logger.error(f"Failed to start the first section: {e}")
            self.helpers.take_screenshot("start_first_section_failed")
            raise e
