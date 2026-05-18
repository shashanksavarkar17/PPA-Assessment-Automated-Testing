import os
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException, StaleElementReferenceException
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class SeleniumHelpers:
    """
    Helper class containing common reusable wrapper methods for Selenium interactions.
    Provides robust waiting, clicking, and text entry capabilities.
    """

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, settings.EXPLICIT_WAIT)

    def wait_for_element(self, locator, timeout=None):
        """
        Wait for an element to be visible on the page.
        locator: tuple (By.<STRATEGY>, "selector")
        """
        try:
            wait_obj = WebDriverWait(self.driver, timeout) if timeout else self.wait
            element = wait_obj.until(EC.visibility_of_element_located(locator))
            return element
        except TimeoutException:
            logger.error(f"Timeout waiting for element to be visible: {locator}")
            self.take_screenshot("timeout_wait_visible")
            raise

    def wait_for_element_clickable(self, locator, timeout=None):
        """
        Wait for an element to be clickable on the page.
        locator: tuple (By.<STRATEGY>, "selector")
        """
        try:
            wait_obj = WebDriverWait(self.driver, timeout) if timeout else self.wait
            element = wait_obj.until(EC.element_to_be_clickable(locator))
            return element
        except TimeoutException:
            logger.error(f"Timeout waiting for element to be clickable: {locator}")
            self.take_screenshot("timeout_wait_clickable")
            raise

    def click_element(self, locator):
        """
        Wait for element to be clickable and click it.
        """
        try:
            element = self.wait_for_element_clickable(locator)
            element.click()
            logger.info(f"Clicked element: {locator}")
        except Exception as e:
            logger.error(f"Failed to click element {locator}. Exception: {e}")
            self.take_screenshot("click_failed")
            raise

    def safe_click(self, locator):
        """
        Click element safely, handling ElementClickInterceptedException by falling back to JS click.
        """
        try:
            element = self.wait_for_element_clickable(locator)
            element.click()
            logger.info(f"Safely clicked element: {locator}")
        except ElementClickInterceptedException:
            logger.warning(f"Element intercepted: {locator}. Attempting JS click fallback.")
            element = self.driver.find_element(*locator)
            self.driver.execute_script("arguments[0].click();", element)
            logger.info(f"JS Click successful: {locator}")
        except Exception as e:
            logger.error(f"Safe click failed for {locator}. Exception: {e}")
            self.take_screenshot("safe_click_failed")
            raise

    def enter_text(self, locator, text, clear_first=True):
        """
        Wait for element, clear it, and enter text.
        """
        try:
            element = self.wait_for_element(locator)
            if clear_first:
                # Robustly clear React inputs using Ctrl+A and Backspace
                element.send_keys(Keys.CONTROL + "a")
                time.sleep(0.1)
                element.send_keys(Keys.BACKSPACE)
                time.sleep(0.1)
            element.send_keys(text)
            logger.info(f"Entered text into element: {locator}") # omitting text value for security if needed, but fine for test
        except Exception as e:
            logger.error(f"Failed to enter text in {locator}. Exception: {e}")
            self.take_screenshot("enter_text_failed")
            raise

    def scroll_into_view(self, locator):
        """
        Scroll the page until the element is in view.
        """
        try:
            element = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            logger.info(f"Scrolled to element: {locator}")
            # small sleep to let UI settle after scroll
            time.sleep(0.5) 
        except Exception as e:
            logger.error(f"Failed to scroll to element {locator}. Exception: {e}")
            raise

    def get_text(self, locator):
        """
        Retrieve text from an element.
        """
        try:
            element = self.wait_for_element(locator)
            text = element.text
            logger.info(f"Retrieved text '{text}' from {locator}")
            return text
        except Exception as e:
            logger.error(f"Failed to get text from {locator}. Exception: {e}")
            raise

    def take_screenshot(self, name_prefix):
        """
        Take a screenshot and save it to the screenshots directory.
        """
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{name_prefix}_{timestamp}.png"
        filepath = os.path.join(settings.SCREENSHOTS_DIR, filename)
        try:
            self.driver.save_screenshot(filepath)
            logger.info(f"Screenshot saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")

    def wait_for_url_change(self, old_url, timeout=settings.EXPLICIT_WAIT):
        """
        Wait until the current URL changes from the old_url.
        """
        try:
            WebDriverWait(self.driver, timeout).until(EC.url_changes(old_url))
            logger.info(f"URL successfully changed from {old_url}")
        except TimeoutException:
            logger.error(f"Timeout waiting for URL to change from {old_url}")
            raise
