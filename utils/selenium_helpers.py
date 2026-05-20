import os, time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

class SeleniumHelpers:
    """Reusable wrapper for robust Selenium interactions."""

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, settings.EXPLICIT_WAIT)

    def wait_for_element(self, locator, timeout=None):
        wait = WebDriverWait(self.driver, timeout) if timeout else self.wait
        return wait.until(EC.visibility_of_element_located(locator))

    def wait_for_element_clickable(self, locator, timeout=None):
        wait = WebDriverWait(self.driver, timeout) if timeout else self.wait
        return wait.until(EC.element_to_be_clickable(locator))

    def click_element(self, locator):
        self.wait_for_element_clickable(locator).click()

    def safe_click(self, locator):
        try:
            self.wait_for_element_clickable(locator).click()
        except ElementClickInterceptedException:
            self.driver.execute_script("arguments[0].click();", self.driver.find_element(*locator))

    def enter_text(self, locator, text, clear_first=True):
        el = self.wait_for_element(locator)
        if clear_first:
            el.send_keys(Keys.CONTROL + "a")
            time.sleep(0.1)
            el.send_keys(Keys.BACKSPACE)
            time.sleep(0.1)
        el.send_keys(text)

    def scroll_into_view(self, locator):
        el = self.wait.until(EC.presence_of_element_located(locator))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
        time.sleep(0.5)

    def get_text(self, locator):
        return self.wait_for_element(locator).text

    def take_screenshot(self, name_prefix):
        path = os.path.join(settings.SCREENSHOTS_DIR, f"{name_prefix}_{time.strftime('%Y%m%d-%H%M%S')}.png")
        try: self.driver.save_screenshot(path)
        except: pass
        return path

    def wait_for_url_change(self, old_url, timeout=settings.EXPLICIT_WAIT):
        WebDriverWait(self.driver, timeout).until(EC.url_changes(old_url))
