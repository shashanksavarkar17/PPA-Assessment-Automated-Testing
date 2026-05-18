import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.logger import get_logger

logger = get_logger("YopmailOTPFetcher")

class YopmailOTPFetcher:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 15)

    def fetch_latest_otp(self, username="narumodi", timeout=60):
        """
        Opens a secondary tab, visits Yopmail, retrieves the latest 6-digit OTP,
        closes the secondary tab, and returns the OTP.
        """
        logger.info(f"Opening secondary tab to fetch OTP for mailbox '{username}'...")
        main_window = self.driver.current_window_handle
        
        # Open a new blank tab
        self.driver.execute_script("window.open('');")
        
        # Switch to the new tab
        self.driver.switch_to.window(self.driver.window_handles[-1])
        
        try:
            self.driver.get("https://yopmail.com/en/wm")
            
            # Dismiss cookie consent/GDPR popups if they appear
            time.sleep(2)
            try:
                consent_selectors = [
                    "//button[@id='accept']",
                    "//button[contains(text(), 'Agree')]",
                    "//button[contains(text(), 'Accept')]",
                    "//div[contains(text(), 'Agree')]"
                ]
                for selector in consent_selectors:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        elements[0].click()
                        logger.info("Dismissed Yopmail consent popup.")
                        break
            except Exception:
                pass
            
            # Find the inbox login input
            login_input = self.wait.until(EC.visibility_of_element_located((By.ID, "login")))
            login_input.clear()
            login_input.send_keys(username)
            login_input.send_keys(Keys.ENTER)
            
            start_time = time.time()
            otp = None
            
            while time.time() - start_time < timeout:
                logger.info("Checking Yopmail inbox for dynamic OTP email...")
                
                # Switch to default content to ensure frame switches are absolute
                self.driver.switch_to.default_content()
                
                try:
                    # Switch to the inbox list iframe
                    self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ifinbox")))
                    
                    # Find all list elements inside the inbox
                    emails = self.driver.find_elements(By.CLASS_NAME, "m")
                    if emails:
                        # Click the latest/topmost email
                        emails[0].click()
                        logger.info("Selected the latest email in the inbox list.")
                except Exception as e:
                    logger.warning(f"Unable to read or click the email list: {e}")
                
                # Switch back to the main document context
                self.driver.switch_to.default_content()
                
                try:
                    # Switch to the email body content iframe
                    self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ifmail")))
                    
                    # Read all body text inside the email
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    
                    # Extract the 6-digit OTP code using regex
                    match = re.search(r'\b\d{6}\b', body_text)
                    if match:
                        otp = match.group(0)
                        logger.info(f"Successfully located OTP: {otp}")
                        break
                except Exception as e:
                    logger.warning(f"Unable to extract OTP from email body: {e}")
                
                # Switch back to the main document context to trigger refresh
                self.driver.switch_to.default_content()
                
                try:
                    # Attempt to click Yopmail's built-in refresh button in the header
                    refresh_btn = self.driver.find_element(By.ID, "refresh")
                    refresh_btn.click()
                    logger.info("Clicked Yopmail inbox refresh button.")
                except Exception:
                    # Fallback to standard driver refresh if button is obscured
                    self.driver.refresh()
                    logger.info("Refreshed the browser tab.")
                
                time.sleep(5)
            
            if not otp:
                raise TimeoutError("Failed to retrieve OTP from Yopmail within the timeout limit.")
                
            return otp
            
        finally:
            # Safely close the secondary tab and restore active focus to the main window
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver.switch_to.window(main_window)
