import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from config import settings

# This page handles credentials input, sending OTP, typing the received code, and verifying.
class LoginPage(BasePage):
    def wait_for_page_load(self):
        # Wait until the email text field appears so we can start logging in.
        self.helpers.wait_for_element((By.NAME, "email"))
        
    def login_with_email(self, email):
        # Type the candidate email and hit the "Send OTP" button to trigger Yopmail delivery.
        self.helpers.enter_text((By.NAME, "email"), email)
        self.helpers.click_element((By.XPATH, "//button[contains(text(), 'Send OTP')]"))
        
    def enter_otp_and_verify(self, otp_code):
        # Give the DOM a quick moment to render the OTP boxes.
        time.sleep(1)
        # Find all active, visible inputs on the screen that aren't the email field or buttons.
        inputs = [i for i in self.driver.find_elements(By.XPATH, "//input") if i.is_displayed() and i.is_enabled() and i.get_attribute("name") != "email" and i.get_attribute("type") not in ["button", "submit", "hidden", "checkbox", "radio"]]
        
        # Fill each input box with a single character of the OTP, or dump the whole code in the first box as a fallback.
        if len(inputs) >= len(otp_code):
            for i, char in enumerate(otp_code): inputs[i].send_keys(char)
        elif inputs:
            inputs[0].send_keys(otp_code)
            
        # Click the first visible verify button we can find.
        for btn in self.driver.find_elements(By.XPATH, "//button[contains(normalize-space(.), 'Verify') or contains(normalize-space(.), 'Submit')]"):
            if btn.is_displayed():
                btn.click()
                break
                
        # Wait up to our configured timeout for the OTP validation to succeed and reveal the Proceed button.
        self.helpers.wait_for_element((By.XPATH, "//button[contains(normalize-space(.), 'Proceed')]"), timeout=settings.OTP_WAIT_TIMEOUT)
