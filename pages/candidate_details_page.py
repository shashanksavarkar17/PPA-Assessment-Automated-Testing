from selenium.webdriver.common.by import By
from pages.base_page import BasePage

# Page Object representing the candidate information and registration form.
class CandidateDetailsPage(BasePage):
    NAME_LOC = (By.XPATH, "//label[starts-with(normalize-space(.), 'Name')]/following::input[1]")
    MOB_LOC = (By.XPATH, "//label[starts-with(normalize-space(.), 'Mobile Number')]/following::input[1]")
    ROLL_LOC = (By.XPATH, "//label[starts-with(normalize-space(.), 'Roll Number')]/following::input[1]")
    PROC_LOC = (By.XPATH, "//button[contains(normalize-space(.), 'Proceed')]")

    def wait_for_page_load(self):
        # Wait for the name input element to become visible, indicating the form is loaded.
        self.helpers.wait_for_element(self.NAME_LOC)
        
    def fill_details_and_proceed(self, name, mobile, roll_number):
        # Populate the candidate information form and submit.
        self.helpers.enter_text(self.NAME_LOC, name)
        self.helpers.enter_text(self.MOB_LOC, mobile)
        self.helpers.enter_text(self.ROLL_LOC, roll_number)
        self.helpers.scroll_into_view(self.PROC_LOC)
        self.helpers.click_element(self.PROC_LOC)
