from selenium.webdriver.common.by import By
from pages.base_page import BasePage

class CandidateDetailsPage(BasePage):
    """Step 5 - Candidate Details"""
    NAME_LOC = (By.XPATH, "//label[starts-with(normalize-space(.), 'Name')]/following::input[1]")
    MOB_LOC = (By.XPATH, "//label[starts-with(normalize-space(.), 'Mobile Number')]/following::input[1]")
    ROLL_LOC = (By.XPATH, "//label[starts-with(normalize-space(.), 'Roll Number')]/following::input[1]")
    PROC_LOC = (By.XPATH, "//button[contains(normalize-space(.), 'Proceed')]")

    def wait_for_page_load(self):
        self.helpers.wait_for_element(self.NAME_LOC)
        
    def fill_details_and_proceed(self, name, mobile, roll_number):
        self.helpers.enter_text(self.NAME_LOC, name)
        self.helpers.enter_text(self.MOB_LOC, mobile)
        self.helpers.enter_text(self.ROLL_LOC, roll_number)
        self.helpers.scroll_into_view(self.PROC_LOC)
        self.helpers.click_element(self.PROC_LOC)
