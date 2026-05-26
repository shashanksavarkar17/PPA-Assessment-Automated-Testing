import re, time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Automates Yopmail interface interaction to retrieve dynamic 6-digit verification codes.
class YopmailOTPFetcher:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 15)

    def fetch_latest_otp(self, username="narumodi", timeout=60):
        # Open a secondary browser tab for Yopmail access, preserving the primary assessment tab.
        main_win = self.driver.current_window_handle
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        
        try:
            self.driver.get("https://yopmail.com/en/wm")
            time.sleep(2)
            # Dismiss active consent and cookie dialogs.
            for sel in ["//button[@id='accept']", "//button[contains(text(), 'Agree')]", "//button[contains(text(), 'Accept')]"]:
                try: self.driver.find_element(By.XPATH, sel).click(); break
                except: pass
            
            # Input candidate inbox identifier and submit inquiry.
            login = self.wait.until(EC.visibility_of_element_located((By.ID, "login")))
            login.clear(); login.send_keys(username + Keys.ENTER)
            
            start = time.time()
            while time.time() - start < timeout:
                self.driver.switch_to.default_content()
                # Switch context to the inbox iframe to access recent messages.
                try:
                    self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ifinbox")))
                    emails = self.driver.find_elements(By.CLASS_NAME, "m")
                    if emails: emails[0].click()
                except: pass
                
                self.driver.switch_to.default_content()
                # Switch context to the message body iframe to parse the OTP.
                try:
                    self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ifmail")))
                    match = re.search(r'\b\d{6}\b', self.driver.find_element(By.TAG_NAME, "body").text)
                    if match: return match.group(0)
                except: pass
                
                # Refresh the inbox and pause before retrying the fetch cycle.
                self.driver.switch_to.default_content()
                try: self.driver.find_element(By.ID, "refresh").click()
                except: self.driver.refresh()
                time.sleep(5)
                
            raise TimeoutError("Failed to retrieve OTP from Yopmail.")
        finally:
            # Ensure the secondary tab is closed and restore focus to the primary assessment window.
            try:
                self.driver.close()
            except: pass
            self.driver.switch_to.window(main_win)
