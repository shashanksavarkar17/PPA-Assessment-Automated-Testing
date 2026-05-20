from selenium.webdriver.common.by import By
from pages.base_page import BasePage

# This page handles the starting terms and instructions check before entering the assessment.
class InstructionsPage(BasePage):
    HEAD_LOC = (By.XPATH, "//*[contains(normalize-space(.), 'ASSESSMENT INSTRUCTIONS BY PROGRAMMING PATHSHALA')]")
    CHK_LOC = (By.XPATH, "//button[@role='checkbox']")
    CONF_LOC = (By.XPATH, "//button[contains(normalize-space(.), 'Confirm and Proceed')]")

    def wait_for_page_load(self):
        # We wait until the big assessment instructions header is visible to know the page has fully loaded.
        self.helpers.wait_for_element(self.HEAD_LOC)
        
    def accept_instructions(self):
        # Let's scroll the checkbox into view, click it to check it, and proceed past instructions.
        self.helpers.scroll_into_view(self.CHK_LOC)
        self.helpers.click_element(self.CHK_LOC)
        self.helpers.click_element(self.CONF_LOC)
