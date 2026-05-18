import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pages.base_page import BasePage
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    import tkinter as tk
except ImportError:
    tk = None

class QuestionPage(BasePage):
    """
    Handles dynamically answering MCQ and Coding questions.
    """

    # --- Locators ---
    QUESTION_TEXT_LOCATOR = (By.XPATH, "//div[contains(@class, 'problem-details')] | //div[contains(@class, 'ql-editor')]")
    
    # MCQ Specific
    RADIO_BUTTONS_LOCATOR = (By.XPATH, "//input[@type='radio']")
    OPTIONS_TEXT_LOCATOR = (By.XPATH, "//input[@type='radio']/following-sibling::span | //input[@type='radio']/following-sibling::label")
    
    # Coding Specific
    CODE_EDITOR_LOCATOR = (By.CSS_SELECTOR, ".monaco-editor, .CodeMirror, textarea.code-input")
    
    # Navigation
    SAVE_AND_NEXT_BTN_LOCATOR = (By.XPATH, "//button[contains(normalize-space(.), 'Save & Next') or contains(normalize-space(.), 'Submit')]")
    
    def wait_for_page_load(self):
        logger.info("Waiting for Question page to load...")
        self.helpers.wait_for_element(self.QUESTION_TEXT_LOCATOR)
        
    def get_question_type(self):
        """
        Determines if the current question is an MCQ or a Coding question.
        """
        # A simple heuristic: if there are radio buttons, it's an MCQ. Otherwise, it's Coding.
        radio_buttons = self.driver.find_elements(*self.RADIO_BUTTONS_LOCATOR)
        if len(radio_buttons) > 0:
            logger.info("Detected question type: MCQ")
            return "MCQ"
        else:
            logger.info("Detected question type: CODING")
            return "CODING"
            
    def get_question_text(self):
        """Extracts the main question text or problem statement."""
        text = self.helpers.get_text(self.QUESTION_TEXT_LOCATOR)
        return text
        
    def get_mcq_options(self):
        """Extracts the text of all available MCQ options with stale element protection."""
        for retry in range(3):
            try:
                elements = self.driver.find_elements(*self.OPTIONS_TEXT_LOCATOR)
                options = [elem.text.strip() for elem in elements if elem.text.strip()]
                return options
            except StaleElementReferenceException:
                logger.warning("Stale element reference while getting MCQ options. Retrying...")
                time.sleep(0.5)
        return []
        
    def select_mcq_option(self, target_option_text):
        """Finds the radio button corresponding to the target text and clicks it."""
        logger.info(f"Attempting to select option matching: {target_option_text}")
        
        # Try to find the radio button that is near the text
        # This XPath looks for a label or span containing the text, and finds the preceding radio button
        xpath = f"//*[contains(normalize-space(.), '{target_option_text}')]/preceding-sibling::input[@type='radio']"
        try:
            # Fallback 1: if the structure is <label><input type="radio"> Text</label>
            xpath_fallback = f"//label[contains(normalize-space(.), '{target_option_text}')]//input[@type='radio']"
            
            elements = self.driver.find_elements(By.XPATH, xpath)
            if not elements:
                elements = self.driver.find_elements(By.XPATH, xpath_fallback)
                
            if elements:
                self.driver.execute_script("arguments[0].click();", elements[0])
                logger.info("Successfully clicked the target option.")
                return True
            else:
                logger.warning("Could not find the radio button for the given option text.")
                return False
        except Exception as e:
            logger.error(f"Failed to select MCQ option: {e}")
            return False

    def enter_code_solution(self, code):
        """Injects the C++ code into the code editor."""
        logger.info("Attempting to enter code into the editor...")
        try:
            # Wait for editor container to be present
            self.helpers.wait_for_element(self.CODE_EDITOR_LOCATOR)
            
            # --- METHOD 1: Try setting Monaco/CodeMirror value directly via JS ---
            try:
                # Monaco Editor API
                self.driver.execute_script("if (typeof monaco !== 'undefined') { monaco.editor.getModels()[0].setValue(arguments[0]); }", code)
                logger.info("Successfully entered code via Monaco JS API.")
                time.sleep(1)
                return
            except Exception as e:
                logger.debug(f"Monaco JS API method not available or failed: {e}")
                
            try:
                # CodeMirror API
                self.driver.execute_script("if (document.querySelector('.CodeMirror')) { document.querySelector('.CodeMirror').CodeMirror.setValue(arguments[0]); }", code)
                logger.info("Successfully entered code via CodeMirror JS API.")
                time.sleep(1)
                return
            except Exception as e:
                logger.debug(f"CodeMirror JS API method not available or failed: {e}")

            # --- METHOD 2: Interact with Monaco Textarea via Selenium + Clipboard/Keyboard ---
            # Try to find the exact hidden textarea inside the editor
            textarea_locators = [
                (By.CSS_SELECTOR, ".monaco-editor textarea.inputarea"),
                (By.CSS_SELECTOR, ".CodeMirror textarea"),
                (By.CSS_SELECTOR, "textarea.code-input"),
                self.CODE_EDITOR_LOCATOR
            ]
            
            textarea = None
            for loc in textarea_locators:
                try:
                    textarea = self.driver.find_element(*loc)
                    if textarea.is_displayed() or loc[0] == By.CSS_SELECTOR: # Monaco textarea is technically 0px wide
                        break
                except Exception:
                    continue
                    
            if not textarea:
                raise Exception("Could not find focusable textarea inside the editor.")

            # Click & focus the textarea
            self.driver.execute_script("arguments[0].focus(); arguments[0].click();", textarea)
            time.sleep(0.5)
            
            # Clear all existing content
            actions = ActionChains(self.driver)
            actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.DELETE).perform()
            time.sleep(0.5)
            
            # Use clipboard paste to bypass Monaco's aggressive auto-complete (which duplicates brackets/braces)
            use_clipboard = False
            if tk:
                try:
                    root = tk.Tk()
                    root.withdraw()
                    root.clipboard_clear()
                    root.clipboard_append(code)
                    root.update()
                    root.destroy()
                    use_clipboard = True
                    logger.info("Code copied to clipboard for paste operation.")
                except Exception as clipboard_err:
                    logger.warning(f"Clipboard copy failed: {clipboard_err}. Falling back to typing.")
            else:
                logger.warning("Tkinter is not available. Falling back to typing.")
                
            actions = ActionChains(self.driver)
            if use_clipboard:
                # Perform paste operation
                actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                logger.info("Pasted code successfully via Clipboard Ctrl+V.")
            else:
                # Fallback to direct typing
                actions.send_keys(code).perform()
                logger.info("Typed code successfully (direct keyboard emulation).")
                
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to enter code solution: {e}")
            raise e
            
    def click_save_and_next(self):
        """Clicks the Save & Next button."""
        try:
            self.helpers.scroll_into_view(self.SAVE_AND_NEXT_BTN_LOCATOR)
            self.helpers.safe_click(self.SAVE_AND_NEXT_BTN_LOCATOR)
            logger.info("Clicked Save & Next.")
            time.sleep(2) # Wait for page transition
        except Exception as e:
            logger.error(f"Failed to click Save & Next: {e}")
            raise e

    def submit_code(self):
        """Clicks the specific Submit button for coding questions."""
        submit_btn_loc = (By.XPATH, "//button[contains(normalize-space(.), 'Submit')]")
        try:
            self.helpers.scroll_into_view(submit_btn_loc)
            self.helpers.safe_click(submit_btn_loc)
            logger.info("Clicked Code Submit button.")
        except Exception as e:
            logger.error(f"Failed to click Code Submit: {e}")
            
    def get_code_result(self):
        """
        Waits for 'Processing...' to finish and checks the result of the testcases.
        Returns a tuple (passed: bool, error_message: str).
        """
        logger.info("Waiting for testcases to finish processing...")
        
        # Wait until no element contains 'Processing...'
        processing_loc = (By.XPATH, "//*[contains(normalize-space(.), 'Processing...')]")
        
        # Wait up to 30 seconds for processing to finish
        try:
            WebDriverWait(self.driver, 30).until(
                EC.invisibility_of_element_located(processing_loc)
            )
        except Exception as e:
            logger.warning("Timeout or error waiting for processing to finish. Will try to extract result anyway.")
            
        time.sleep(1) # Give UI a moment to render the final state
        
        # Retry up to 3 times to prevent StaleElementReferenceException
        from selenium.common.exceptions import StaleElementReferenceException
        for retry in range(3):
            try:
                # Look for failure indicators
                failed_loc = (By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'fail') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'error')]")
                failed_elements = self.driver.find_elements(*failed_loc)
                
                # Filter out generic elements that might just be buttons or headers
                actual_errors = []
                for elem in failed_elements:
                    if elem.is_displayed():
                        text = elem.text.strip()
                        if text and len(text) > 2 and text.lower() not in ["failed", "error"]:
                            actual_errors.append(text)
                            
                if actual_errors:
                    error_msg = "\n".join(actual_errors)
                    logger.error(f"Code submission failed with errors: {error_msg}")
                    return False, error_msg
                else:
                    # Check if there's any visible failed text without extra text (e.g. just a red "Failed" badge)
                    just_failed = [e for e in failed_elements if e.is_displayed() and e.text.strip().lower() in ["failed", "error"]]
                    if just_failed:
                        logger.error("Code submission failed (found generic Failed/Error badge).")
                        # Try to grab the whole result container text for context
                        result_container = self.driver.find_elements(By.XPATH, "//div[contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'result')]")
                        if result_container:
                            return False, result_container[-1].text
                        return False, "Failed or Error badge found without specific error text."
                        
                    logger.info("No failure detected on this attempt. Code likely passed all testcases!")
                    return True, ""
            except StaleElementReferenceException:
                logger.warning("DOM changed while analyzing results. Retrying result extraction...")
                time.sleep(0.5)
                
        return False, "Stale element extraction loop failed."
