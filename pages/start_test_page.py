from selenium.webdriver.common.by import By
from pages.base_page import BasePage

# Page Object representing the final test initiation page.
class StartTestPage(BasePage):
    START_LOC = (By.XPATH, "//button[contains(normalize-space(.), 'Start Test')]")

    def wait_for_page_load(self):
        # Wait for the start test initiation button to become visible.
        self.helpers.wait_for_element(self.START_LOC)
        
    def click_start_test(self):
        # Ensure the start button is in viewport and execute the click interaction.
        self.helpers.scroll_into_view(self.START_LOC)
        self.helpers.click_element(self.START_LOC)
