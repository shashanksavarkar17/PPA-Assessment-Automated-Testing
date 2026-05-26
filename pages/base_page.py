from utils.selenium_helpers import SeleniumHelpers

# Base Page Object class defining common driver properties and helper instantiations.
class BasePage:
    def __init__(self, driver):
        # Initialize WebDriver reference and utility helpers.
        self.driver = driver
        self.helpers = SeleniumHelpers(self.driver)

    def navigate_to(self, url):
        # Navigate the browser to the specified URL.
        self.driver.get(url)
