from selenium.webdriver.common.by import By
from pages.base_page import BasePage

# This page displays the final "Start Test" trigger before launch.
class StartTestPage(BasePage):
    START_LOC = (By.XPATH, "//button[contains(normalize-space(.), 'Start Test')]")

    def wait_for_page_load(self):
        # Wait until the launch button is visible on screen.
        self.helpers.wait_for_element(self.START_LOC)
        
    def click_start_test(self):
        # Scroll down to ensure we can see it clearly, and then click it!
        self.helpers.scroll_into_view(self.START_LOC)
        self.helpers.click_element(self.START_LOC)
