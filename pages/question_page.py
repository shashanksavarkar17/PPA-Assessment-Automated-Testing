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
    Page Object representing the dynamic Question space, supporting MCQ scanning,
    Monaco/CodeMirror interactions, and run/submit result assertions.
    """

    QUESTION_TEXT_LOCATOR = (By.XPATH, "//div[contains(@class, 'problem-details')] | //div[contains(@class, 'ql-editor')]")
    RADIO_BUTTONS_LOCATOR = (By.XPATH, "//input[@type='radio']")
    CODE_EDITOR_LOCATOR = (By.CSS_SELECTOR, ".monaco-editor, .CodeMirror, textarea.code-input")

    def wait_for_page_load(self):
        logger.info("Waiting for Question page to load...")
        self.helpers.wait_for_element(self.QUESTION_TEXT_LOCATOR)
        
    def get_question_type(self):
        radio_buttons = self.driver.find_elements(*self.RADIO_BUTTONS_LOCATOR)
        if len(radio_buttons) > 0:
            logger.info("Detected MCQ question structure.")
            return "MCQ"
        logger.info("Detected Coding question workspace.")
        return "CODING"
            
    def get_question_text(self):
        return self.helpers.get_text(self.QUESTION_TEXT_LOCATOR)
        
    def get_selected_language(self):
        """
        Dynamically detects the language selected in the assessment editor using dropdown selectors and JS scans.
        """
        logger.info("Scanning for selected coding language...")
        
        # 1. Standard dropdown, select elements and language-specific buttons/labels
        locators = [
            (By.XPATH, "//select[contains(@class, 'lang') or contains(@class, 'language') or contains(@id, 'lang') or contains(@id, 'language')]"),
            (By.XPATH, "//*[contains(@class, 'lang-select') or contains(@class, 'language-select')]//button"),
            (By.XPATH, "//*[contains(@class, 'dropdown') or contains(@class, 'select')]//*[contains(text(), 'C++') or contains(text(), 'Python') or contains(text(), 'Java') or contains(text(), 'C') or contains(text(), 'JavaScript')]")
        ]
        
        for loc in locators:
            try:
                elements = self.driver.find_elements(*loc)
                for elem in elements:
                    if elem.is_displayed():
                        # If standard SELECT, read the active option value/text
                        if elem.tag_name == "select":
                            from selenium.webdriver.support.ui import Select
                            select = Select(elem)
                            selected_lang = select.first_selected_option.text.strip()
                            if selected_lang:
                                logger.info(f"Language auto-detected via select dropdown: {selected_lang}")
                                return selected_lang
                        # Otherwise return the inner text directly
                        text = elem.text.strip()
                        if text:
                            logger.info(f"Language auto-detected via element text: {text}")
                            return text
            except Exception:
                pass
                
        # 2. Resilient dynamic browser DOM-tree JS fallback
        try:
            js_script = """
            let select = document.querySelector('select');
            if (select && select.selectedIndex >= 0) {
                return select.options[select.selectedIndex].text.trim();
            }
            // Search all elements containing common coding language text
            let active = Array.from(document.querySelectorAll('*')).find(el => {
                if (!el.children.length && el.innerText) {
                    let text = el.innerText.trim();
                    return /^(C\\+\\+|Python|Java|JavaScript|C|Ruby|Go)$/i.test(text);
                }
                return false;
            });
            return active ? active.innerText.trim() : null;
            """
            detected = self.driver.execute_script(js_script)
            if detected:
                logger.info(f"Language auto-detected via dynamic DOM JS fallback: {detected}")
                return detected
        except Exception as e:
            logger.warning(f"DOM JS language scan failed: {e}")
            
        logger.warning("Could not auto-detect language. Falling back to default C++.")
        return "C++"
        
    def get_mcq_options(self):
        option_locators = [
            (By.XPATH, "//input[@type='radio']/following-sibling::span | //input[@type='radio']/following-sibling::label"),
            (By.XPATH, "//label[//input[@type='radio']]"),
            (By.XPATH, "//div[contains(@class, 'option')]"),
            (By.XPATH, "//input[@type='radio']/parent::*"),
            (By.XPATH, "//input[@type='radio']/ancestor::label")
        ]
        
        for loc in option_locators:
            for retry in range(3):
                try:
                    elements = self.driver.find_elements(*loc)
                    options = [elem.text.strip() for elem in elements if elem.text.strip()]
                    options = list(dict.fromkeys(options))  # Deduplicate while preserving order
                    if options and len(options) >= 2:
                        return options
                except StaleElementReferenceException:
                    time.sleep(0.5)
                    
        # DOM traversal fallback for structured elements without standard inline siblings
        try:
            inputs = self.driver.find_elements(By.XPATH, "//input[@type='radio']")
            options = []
            for ipt in inputs:
                parent = ipt.find_element(By.XPATH, "..")
                parent_text = parent.text.strip()
                if parent_text:
                    options.append(parent_text)
                else:
                    grandparent = parent.find_element(By.XPATH, "..")
                    grandparent_text = grandparent.text.strip()
                    if grandparent_text:
                        options.append(grandparent_text)
            return list(dict.fromkeys(options))
        except Exception:
            pass
            
        return []
        
    def select_mcq_option(self, target_option_text):
        logger.info(f"Selecting option: {target_option_text}")
        
        xpaths = [
            f"//label[contains(normalize-space(.), '{target_option_text}')]//input[@type='radio' or @type='checkbox']",
            f"//*[contains(normalize-space(.), '{target_option_text}')]/preceding-sibling::input[@type='radio' or @type='checkbox']",
            f"//*[contains(normalize-space(.), '{target_option_text}')]/preceding::input[@type='radio' or @type='checkbox'][1]",
            f"//*[contains(normalize-space(.), '{target_option_text}')]//input[@type='radio' or @type='checkbox']",
            f"//input[@type='radio' or @type='checkbox']/following-sibling::*[contains(normalize-space(.), '{target_option_text}')]"
        ]
        
        for xpath in xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for elem in elements:
                    if elem.is_displayed():
                        self.driver.execute_script("arguments[0].click();", elem)
                        return True
            except Exception:
                pass
                
        # Contextual parent-child proximity scan
        try:
            inputs = self.driver.find_elements(By.XPATH, "//input[@type='radio' or @type='checkbox']")
            for ipt in inputs:
                parent = ipt.find_element(By.XPATH, "..")
                parent_text = parent.text or ""
                grandparent = parent.find_element(By.XPATH, "..")
                grandparent_text = grandparent.text or ""
                sibling_text = ""
                try:
                    siblings = ipt.find_elements(By.XPATH, "following-sibling::*")
                    sibling_text = " ".join([s.text for s in siblings])
                except Exception:
                    pass
                
                combined_text = f"{parent_text} {grandparent_text} {sibling_text}".lower()
                if target_option_text.lower() in combined_text:
                    self.driver.execute_script("arguments[0].click();", ipt)
                    return True
        except Exception:
            pass
            
        logger.warning(f"Unable to find radio button matching: {target_option_text}")
        return False

    def enter_code_solution(self, code):
        logger.info("Injecting solution into code editor...")
        try:
            self.helpers.wait_for_element(self.CODE_EDITOR_LOCATOR)
            
            # Monaco Editor direct API value assignment
            try:
                self.driver.execute_script("if (typeof monaco !== 'undefined') { monaco.editor.getModels()[0].setValue(arguments[0]); }", code)
                logger.info("Injected via Monaco API.")
                time.sleep(1)
                return
            except Exception:
                pass
                
            # CodeMirror value assignment
            try:
                self.driver.execute_script("if (document.querySelector('.CodeMirror')) { document.querySelector('.CodeMirror').CodeMirror.setValue(arguments[0]); }", code)
                logger.info("Injected via CodeMirror API.")
                time.sleep(1)
                return
            except Exception:
                pass

            # Fallback: physical focus & paste (bypasses auto-brace auto-completion)
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
                    if textarea.is_displayed() or loc[0] == By.CSS_SELECTOR:
                        break
                except Exception:
                    continue
                    
            if not textarea:
                raise Exception("Editor textarea element not resolved.")

            self.driver.execute_script("arguments[0].focus(); arguments[0].click();", textarea)
            time.sleep(0.5)
            
            # Clear editor workspace
            actions = ActionChains(self.driver)
            actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.DELETE).perform()
            time.sleep(0.5)
            
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
                except Exception:
                    pass
                
            actions = ActionChains(self.driver)
            if use_clipboard:
                actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                logger.info("Injected via Clipboard.")
            else:
                actions.send_keys(code).perform()
                logger.info("Injected via physical keystroke emulator.")
                
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Injections failed: {e}")
            raise e
            
    def click_save_and_next(self):
        logger.info("Transitioning to the next question...")
        resilient_locators = [
            (By.XPATH, "//button[contains(normalize-space(.), 'Save') or contains(normalize-space(.), 'Submit') or contains(normalize-space(.), 'Next')]"),
            (By.XPATH, "//a[contains(normalize-space(.), 'Save') or contains(normalize-space(.), 'Submit') or contains(normalize-space(.), 'Next')]"),
            (By.XPATH, "//*[contains(@class, 'btn') or contains(@class, 'button') or @role='button'][contains(normalize-space(.), 'Save') or contains(normalize-space(.), 'Submit') or contains(normalize-space(.), 'Next')]"),
            (By.XPATH, "//input[@type='button' or @type='submit'][contains(translate(@value, 'SAVENEXTSUBMIT', 'savenextsubmit'), 'save') or contains(translate(@value, 'SAVENEXTSUBMIT', 'savenextsubmit'), 'submit') or contains(translate(@value, 'SAVENEXTSUBMIT', 'savenextsubmit'), 'next')]")
        ]
        
        for loc in resilient_locators:
            try:
                elements = self.driver.find_elements(*loc)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        text = elem.text.strip() or elem.get_attribute("value") or ""
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(2)
                        return True
            except Exception:
                pass
                
        self.helpers.take_screenshot("click_save_and_next_failed")
        raise Exception("Save/Submit/Next button not found on the page.")

    def submit_code(self):
        submit_btn_loc = (By.XPATH, "//button[contains(normalize-space(.), 'Submit')]")
        try:
            self.helpers.scroll_into_view(submit_btn_loc)
            self.helpers.safe_click(submit_btn_loc)
            logger.info("Clicked Code Submit button.")
        except Exception as e:
            logger.error(f"Failed to click Code Submit: {e}")
            
    def run_code(self):
        run_btn_loc = (By.XPATH, "//button[contains(normalize-space(.), 'Run')]")
        try:
            self.helpers.scroll_into_view(run_btn_loc)
            self.helpers.safe_click(run_btn_loc)
            logger.info("Clicked Code Run button.")
        except Exception as e:
            logger.error(f"Failed to click Code Run: {e}")
            try:
                run_btn = self.driver.find_element(*run_btn_loc)
                self.driver.execute_script("arguments[0].click();", run_btn)
                logger.info("Clicked Code Run button via JS fallback.")
            except Exception as js_err:
                logger.error(f"JS fallback click on Run failed: {js_err}")
                raise e

    def get_run_result(self):
        logger.info("Waiting for run execution to complete...")
        time.sleep(2)
        
        processing_loc = (By.XPATH, "//*[contains(text(), 'Processing') or contains(text(), 'Running') or contains(text(), 'Compiling') or contains(text(), 'Evaluating')]")
        try:
            WebDriverWait(self.driver, 30).until(EC.invisibility_of_element_located(processing_loc))
        except Exception:
            logger.warning("Timeout waiting for run processing indicators to disappear.")
            
        time.sleep(1.5)
        
        area_locators = [
            (By.XPATH, "//div[contains(@class, 'result-container') or contains(@class, 'output-container') or contains(@class, 'console')]"),
            (By.XPATH, "//*[contains(@class, 'tab-content') or contains(@class, 'pane')]"),
            (By.XPATH, "//*[contains(@class, 'result') or contains(@class, 'output') or contains(@class, 'compile')]"),
            (By.XPATH, "//div[contains(normalize-space(.), 'Result')]/parent::*")
        ]
        
        result_text = ""
        for loc in area_locators:
            try:
                elements = self.driver.find_elements(*loc)
                for elem in elements:
                    if elem.is_displayed():
                        text = elem.text.strip()
                        if text and len(text) > 10:
                            result_text = text
                            break
                if result_text:
                    break
            except Exception:
                continue
                
        if not result_text:
            try:
                result_text = self.driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                result_text = ""
                
        logger.info(f"Run console results loaded: {len(result_text)} characters.")
        lower_text = result_text.lower()
        
        failure_keywords = [
            "compilation error", "compile error", "wrong answer", "runtime error", 
            "time limit exceeded", "memory limit exceeded", "failed", "error", "exception",
            "mismatch", "expected:", "got:"
        ]
        
        detected_failures = [kw.upper() for kw in failure_keywords if kw in lower_text]
        if detected_failures:
            logger.error(f"Console errors detected: {detected_failures}")
            return False, result_text
            
        success_keywords = ["passed", "correct", "success", "accepted", "all test cases passed"]
        if any(sk in lower_text for sk in success_keywords):
            return True, ""
            
        if "you must run or submit" not in lower_text:
            return True, ""
            
        return False, f"Could not determine run outcome. Text seen: {result_text[:300]}"
            
    def get_code_result(self):
        logger.info("Waiting for submissions validation...")
        processing_loc = (By.XPATH, "//*[contains(normalize-space(.), 'Processing...')]")
        try:
            WebDriverWait(self.driver, 30).until(EC.invisibility_of_element_located(processing_loc))
        except Exception:
            pass
            
        time.sleep(1)
        
        from selenium.common.exceptions import StaleElementReferenceException
        for retry in range(3):
            try:
                failed_loc = (By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'fail') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'error')]")
                failed_elements = self.driver.find_elements(*failed_loc)
                
                actual_errors = [e.text.strip() for e in failed_elements if e.is_displayed() and e.text.strip() and len(e.text.strip()) > 2 and e.text.strip().lower() not in ["failed", "error"]]
                if actual_errors:
                    error_msg = "\n".join(actual_errors)
                    return False, error_msg
                else:
                    just_failed = [e for e in failed_elements if e.is_displayed() and e.text.strip().lower() in ["failed", "error"]]
                    if just_failed:
                        result_container = self.driver.find_elements(By.XPATH, "//div[contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'result')]")
                        if result_container:
                            return False, result_container[-1].text
                        return False, "Failed or Error status badge observed in results pane."
                    return True, ""
            except StaleElementReferenceException:
                time.sleep(0.5)
                
        return False, "Unable to extract submission results due to stale DOM state."

    def click_solve_if_present(self):
        solve_btn_locators = [
            (By.XPATH, "//button[contains(normalize-space(.), 'Solve')]"),
            (By.XPATH, "//a[contains(normalize-space(.), 'Solve')]")
        ]
        for loc in solve_btn_locators:
            try:
                elements = self.driver.find_elements(*loc)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(2)
                        return True
            except Exception:
                pass
        return False

    def return_to_summary(self):
        """Resiliently clicks the button to go back to the assessment summary page."""
        logger.info("Attempting to return to the summary/sections dashboard...")
        locators = [
            (By.XPATH, "//*[contains(text(), 'Summary') or contains(text(), 'Dashboard') or contains(text(), 'Back') or contains(text(), 'Sections') or contains(text(), 'End Test')]"),
            (By.XPATH, "//a[contains(@href, 'summary') or contains(@href, 'dashboard') or contains(@href, 'assessment')]"),
            (By.CSS_SELECTOR, ".back-btn, .summary-btn, .dashboard-link, .sections-btn")
        ]
        for loc in locators:
            try:
                elements = self.driver.find_elements(*loc)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(2)
                        return True
            except Exception:
                pass
        return False
