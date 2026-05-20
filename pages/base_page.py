from utils.selenium_helpers import SeleniumHelpers

# This is the base parent class that all our page objects will inherit from.
class BasePage:
    def __init__(self, driver):
        # Store the driver instance and initialize our custom selenium interactions helper.
        self.driver = driver
        self.helpers = SeleniumHelpers(self.driver)

    def navigate_to(self, url):
        # Quick helper to point our browser to any URL we need.
        self.driver.get(url)
