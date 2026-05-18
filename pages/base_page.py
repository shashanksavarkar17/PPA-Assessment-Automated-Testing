from utils.selenium_helpers import SeleniumHelpers

class BasePage:
    """
    Base class for all Page Objects.
    Contains common functionalities to interact with any page.
    """
    def __init__(self, driver):
        self.driver = driver
        self.helpers = SeleniumHelpers(self.driver)

    def navigate_to(self, url):
        """Navigate to the specified URL."""
        self.driver.get(url)
