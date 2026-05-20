import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from config import settings

class LoginPage(BasePage):
    """Step 3 & 4 - Login and OTP Handling"""

    def wait_for_page_load(self):
        self.helpers.wait_for_element((By.NAME, "email"))
        
    def login_with_email(self, email):
        self.helpers.enter_text((By.NAME, "email"), email)
        self.helpers.click_element((By.XPATH, "//button[contains(text(), 'Send OTP')]"))
        
    def enter_otp_and_verify(self, otp_code):
        time.sleep(1)
        inputs = [i for i in self.driver.find_elements(By.XPATH, "//input") if i.is_displayed() and i.is_enabled() and i.get_attribute("name") != "email" and i.get_attribute("type") not in ["button", "submit", "hidden", "checkbox", "radio"]]
        
        if len(inputs) >= len(otp_code):
            for i, char in enumerate(otp_code): inputs[i].send_keys(char)
        elif inputs:
            inputs[0].send_keys(otp_code)
            
        for btn in self.driver.find_elements(By.XPATH, "//button[contains(normalize-space(.), 'Verify') or contains(normalize-space(.), 'Submit')]"):
            if btn.is_displayed():
                btn.click()
                break
                
        self.helpers.wait_for_element((By.XPATH, "//button[contains(normalize-space(.), 'Proceed')]"), timeout=settings.OTP_WAIT_TIMEOUT)
