from selenium.webdriver.common.by import By
from pages.base_page import BasePage

class StartTestPage(BasePage):
    """Step 6 - Start Test"""
    START_LOC = (By.XPATH, "//button[contains(normalize-space(.), 'Start Test')]")

    def wait_for_page_load(self):
        self.helpers.wait_for_element(self.START_LOC)
        
    def click_start_test(self):
        self.helpers.scroll_into_view(self.START_LOC)
        self.helpers.click_element(self.START_LOC)
