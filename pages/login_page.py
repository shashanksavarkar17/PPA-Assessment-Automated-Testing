import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from config import settings

# Page Object representing the user login and OTP verification interface.
class LoginPage(BasePage):
    def wait_for_page_load(self):
        # Wait for the email input element to become visible, indicating page load.
        self.helpers.wait_for_element((By.NAME, "email"))
        
    def login_with_email(self, email):
        # Submit candidate email to trigger authentication OTP generation.
        self.helpers.enter_text((By.NAME, "email"), email)
        self.helpers.click_element((By.XPATH, "//button[contains(text(), 'Send OTP')]"))
        
    def enter_otp_and_verify(self, otp_code):
        # Allow the DOM a short duration to render the OTP input interface.
        time.sleep(1)
        # Identify all visible, non-email input fields for entering the OTP.
        inputs = [i for i in self.driver.find_elements(By.XPATH, "//input") if i.is_displayed() and i.is_enabled() and i.get_attribute("name") != "email" and i.get_attribute("type") not in ["button", "submit", "hidden", "checkbox", "radio"]]
        
        # Distribute OTP characters across the corresponding input fields.
        if len(inputs) >= len(otp_code):
            for i, char in enumerate(otp_code): inputs[i].send_keys(char)
        elif inputs:
            inputs[0].send_keys(otp_code)
            
        # Identify and submit the verification button.
        for btn in self.driver.find_elements(By.XPATH, "//button[contains(normalize-space(.), 'Verify') or contains(normalize-space(.), 'Submit')]"):
            if btn.is_displayed():
                btn.click()
                break
                
        # Wait for verification completion and target transition button rendering.
        self.helpers.wait_for_element((By.XPATH, "//button[contains(normalize-space(.), 'Proceed')]"), timeout=settings.OTP_WAIT_TIMEOUT)
