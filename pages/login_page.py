import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

class LoginPage(BasePage):
    """
    Step 3 & 4 - Login and OTP Handling
    """

    EMAIL_INPUT_LOCATOR = (By.NAME, "email")
    SEND_OTP_BTN_LOCATOR = (By.XPATH, "//button[contains(text(), 'Send OTP')]")
    SUCCESS_INDICATOR_LOCATOR = (By.XPATH, "//button[contains(normalize-space(.), 'Proceed')]")

    def wait_for_page_load(self):
        logger.info("Waiting for Login page...")
        self.helpers.wait_for_element(self.EMAIL_INPUT_LOCATOR)
        
    def login_with_email(self, email):
        """Enter email and click Send OTP."""
        self.helpers.enter_text(self.EMAIL_INPUT_LOCATOR, email)
        self.helpers.click_element(self.SEND_OTP_BTN_LOCATOR)
        logger.info(f"Entered email and clicked Send OTP for: {email}")
        
    def enter_otp_and_verify(self, otp_code):
        """
        Takes an OTP code and automatically enters it into the UI.
        """
        logger.info(f"Attempting to enter OTP automatically...")
        
        # Wait a moment for the OTP fields to appear
        time.sleep(1)
        
        # Try to find the OTP input fields broadly.
        inputs = self.driver.find_elements(By.XPATH, "//input")
        
        # Filter for visible, enabled inputs, excluding the email box and hidden types
        otp_inputs = [
            inp for inp in inputs 
            if inp.is_displayed() 
            and inp.is_enabled() 
            and inp.get_attribute("name") != "email" 
            and inp.get_attribute("type") not in ["button", "submit", "hidden", "checkbox", "radio"]
        ]
        
        try:
            if len(otp_inputs) > 1 and len(otp_inputs) >= len(otp_code):
                # Multiple boxes (e.g. 6 separate boxes)
                logger.info("Detected multiple OTP input boxes. Entering digit by digit...")
                for i, char in enumerate(otp_code):
                    if i < len(otp_inputs):
                        otp_inputs[i].send_keys(char)
                        time.sleep(0.05)
            elif len(otp_inputs) == 1:
                # Single box
                logger.info("Detected a single OTP input box. Entering full code...")
                otp_inputs[0].send_keys(otp_code)
            elif len(otp_inputs) > 0:
                 # Fallback: Just try typing it into the first input
                 logger.info("Could not determine exact OTP structure. Typing into the first available input...")
                 otp_inputs[0].send_keys(otp_code)
            else:
                logger.error("Could not find any OTP input fields on the page!")
                raise Exception("OTP fields not found.")
                
            # Click Verify/Proceed button if there is one explicitly for OTP (often it's 'Verify' or 'Submit')
            # But the SUCCESS_INDICATOR_LOCATOR is "Proceed", which might be the next page's button.
            # Usually, typing the 6th digit auto-submits, or there's a button.
            verify_btns = self.driver.find_elements(By.XPATH, "//button[contains(normalize-space(.), 'Verify') or contains(normalize-space(.), 'Submit')]")
            for btn in verify_btns:
                if btn.is_displayed():
                    btn.click()
                    logger.info("Clicked Verify button.")
                    break
                    
            logger.info("Waiting for successful authentication...")
            self.helpers.wait_for_element(self.SUCCESS_INDICATOR_LOCATOR, timeout=settings.OTP_WAIT_TIMEOUT)
            logger.info("OTP authentication detected as SUCCESSFUL! Continuing automation...")
            
        except Exception as e:
            logger.error(f"Failed during automated OTP entry: {e}")
            raise e
