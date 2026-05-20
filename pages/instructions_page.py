from selenium.webdriver.common.by import By
from pages.base_page import BasePage

class InstructionsPage(BasePage):
    """Step 2 - Instructions Page"""
    HEAD_LOC = (By.XPATH, "//*[contains(normalize-space(.), 'ASSESSMENT INSTRUCTIONS BY PROGRAMMING PATHSHALA')]")
    CHK_LOC = (By.XPATH, "//button[@role='checkbox']")
    CONF_LOC = (By.XPATH, "//button[contains(normalize-space(.), 'Confirm and Proceed')]")

    def wait_for_page_load(self):
        self.helpers.wait_for_element(self.HEAD_LOC)
        
    def accept_instructions(self):
        self.helpers.scroll_into_view(self.CHK_LOC)
        self.helpers.click_element(self.CHK_LOC)
        self.helpers.click_element(self.CONF_LOC)
