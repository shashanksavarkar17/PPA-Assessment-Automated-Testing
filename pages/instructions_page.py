from selenium.webdriver.common.by import By
from pages.base_page import BasePage

# Page Object representing the test instructions and acknowledgment interface.
class InstructionsPage(BasePage):
    HEAD_LOC = (By.XPATH, "//*[contains(normalize-space(.), 'ASSESSMENT INSTRUCTIONS BY PROGRAMMING PATHSHALA')]")
    CHK_LOC = (By.XPATH, "//button[@role='checkbox']")
    CONF_LOC = (By.XPATH, "//button[contains(normalize-space(.), 'Confirm and Proceed')]")

    def wait_for_page_load(self):
        # Wait for the instruction header element to become visible, indicating page load.
        self.helpers.wait_for_element(self.HEAD_LOC)
        
    def accept_instructions(self):
        # Accept instructions and transition to the test.
        import time
        time.sleep(1.5)
        try:
            self.helpers.scroll_into_view(self.CHK_LOC)
            time.sleep(0.3)
            self.helpers.click_element(self.CHK_LOC)
        except Exception as e:
            # Fallback click via JS
            try:
                el = self.driver.find_element(*self.CHK_LOC)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                time.sleep(0.2)
                self.driver.execute_script("arguments[0].click();", el)
            except: pass
            
        time.sleep(0.5)
        try:
            self.helpers.click_element(self.CONF_LOC)
        except Exception as e:
            try:
                el = self.driver.find_element(*self.CONF_LOC)
                self.driver.execute_script("arguments[0].click();", el)
            except: pass
