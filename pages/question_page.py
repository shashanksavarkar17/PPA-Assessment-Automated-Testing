import time
import re
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

log = get_logger(__name__)

# Highly minimized and robust QuestionPage handling MCQs and coding injections.
class QuestionPage(BasePage):
    def wait_for_page_load(self):
        # Dismiss any proctoring/tab-switch block warnings if they appear.
        for _ in range(3):
            try:
                for btn in self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Return')]"):
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
            except: pass
        self.helpers.wait_for_element((By.XPATH, "//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'editor')]"))
        
    def get_question_type(self):
        # Return MCQ if radio buttons are found, otherwise CODING.
        return "MCQ" if self.driver.find_elements(By.XPATH, "//input[@type='radio']") else "CODING"
            
    def get_question_text(self):
        # Extract problem text from standard container elements.
        for sel in ["//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'ql-editor')]", "body"]:
            elements = self.driver.find_elements(By.XPATH, sel)
            if elements and elements[0].text.strip():
                return elements[0].text.strip()
        return "Unknown Question"
        
    def get_selected_language(self):
        # Identify the selected language dropdown option.
        try:
            for sel in ["select", "[class*='lang']", "[id*='lang']"]:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.tag_name == "select":
                    from selenium.webdriver.support.ui import Select
                    return Select(el).first_selected_option.text.strip()
                return el.text.strip()
        except: pass
        return "C++"

    def ensure_cpp_language(self):
        """
        Find the language selection dropdown and ensure 'C++' is selected.
        """
        log.info("Checking language selector to ensure C++ is selected...")
        current_lang = self.get_selected_language()
        if "c++" in current_lang.lower() or "cpp" in current_lang.lower():
            log.info(f"C++ language is already selected (Current: '{current_lang}').")
            return True
            
        # Look for select dropdown elements
        selects = self.driver.find_elements(By.XPATH, "//select")
        for sel in selects:
            try:
                if sel.is_displayed():
                    from selenium.webdriver.support.ui import Select
                    s = Select(sel)
                    for opt in s.options:
                        txt = opt.text.lower()
                        if "c++" in txt or "cpp" in txt:
                            s.select_by_visible_text(opt.text)
                            log.info(f"Selected language option '{opt.text}' via dropdown Select.")
                            time.sleep(0.5)
                            return True
            except: pass
            
        # Look for custom dropdown toggle elements containing 'c++' or 'language'
        for toggle in self.driver.find_elements(By.XPATH, "//button | //div[@role='button'] | //span[contains(@class, 'dropdown') or contains(@class, 'select')]"):
            try:
                if toggle.is_displayed():
                    text = toggle.text.lower()
                    if "c++" in text or "cpp" in text or "select" in text or "lang" in text:
                        self.driver.execute_script("arguments[0].click();", toggle)
                        time.sleep(0.5)
                        # Look for active dropdown menu items
                        for item in self.driver.find_elements(By.XPATH, "//li | //a | //div[contains(@class, 'option') or contains(@class, 'item')]"):
                            try:
                                if item.is_displayed():
                                    item_txt = item.text.lower()
                                    if "c++" in item_txt or "cpp" in item_txt:
                                        self.driver.execute_script("arguments[0].click();", item)
                                        log.info(f"Selected language option '{item.text}' from custom dropdown item list.")
                                        time.sleep(0.5)
                                        return True
                            except: pass
            except: pass
            
        log.warning("Could not explicitly select C++ from dropdown option elements.")
        return False

    def get_example_input_output(self):
        """
        Resiliently extract example input and output text from the question statement.
        """
        log.info("Parsing example testcases from the question statement...")
        
        # Method 1: Scan all <pre> tags
        pre_elements = self.driver.find_elements(By.XPATH, "//pre | //code")
        for pre in pre_elements:
            try:
                if pre.is_displayed():
                    text = pre.text.strip()
                    if not text:
                        continue
                    
                    if "input" in text.lower() and "output" in text.lower():
                        # Try parsing standard CP pattern: "Input: ... Output: ..."
                        match = re.search(r'(?:input|sample input|example input):?\s*\n?(.*?)\s*\n?(?:output|sample output|example output):?\s*\n?(.*)', text, re.IGNORECASE | re.DOTALL)
                        if match:
                            inp = match.group(1).strip()
                            out = match.group(2).strip()
                            # Clean label prefixes inside match
                            inp = re.sub(r'^(?:input|sample input|example input):?\s*', '', inp, flags=re.I).strip()
                            out = re.sub(r'^(?:output|sample output|example output):?\s*', '', out, flags=re.I).strip()
                            log.info(f"Parsed example from <pre> tag. Input: {repr(inp)}, Output: {repr(out)}")
                            return inp, out
            except Exception as e:
                log.warning(f"Error checking pre tag: {e}")
                
        # Method 2: Fallback to scanning page content text directly via regex
        try:
            full_text = self.get_question_text()
            match = re.search(r'(?:input|sample input|example input):?\s*\n?(.*?)\n?(?:output|sample output|example output):?\s*\n?(.*?)(?:\n\n|\n[A-Z]|\Z)', full_text, re.IGNORECASE | re.DOTALL)
            if match:
                inp = match.group(1).strip()
                out = match.group(2).strip()
                log.info(f"Parsed example from page text regex. Input: {repr(inp)}, Output: {repr(out)}")
                return inp, out
        except Exception as e:
            log.warning(f"Error parsing example via regex: {e}")
            
        log.warning("Could not parse example input/output from the page.")
        return "", ""

    def enable_custom_input(self):
        """
        Locate and click the 'Custom Input' checkbox or toggle button.
        """
        log.info("Attempting to locate and enable 'Custom Input' checkbox/toggle...")
        
        # 1. Search for standard checkbox input elements with 'custom' in their attributes
        for inp in self.driver.find_elements(By.XPATH, "//input[@type='checkbox']"):
            try:
                for attr in ["id", "class", "name", "value"]:
                    val = (inp.get_attribute(attr) or "").lower()
                    if "custom" in val or "input" in val:
                        if inp.is_displayed():
                            if not inp.is_selected():
                                self.driver.execute_script("arguments[0].click();", inp)
                                log.info("Enabled custom input checkbox via direct element click.")
                                time.sleep(0.5)
                            return True
            except: pass
            
        # 2. Search for label elements containing text 'custom input'
        for label in self.driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom input') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom test')]"):
            try:
                if label.is_displayed():
                    self.driver.execute_script("arguments[0].click();", label)
                    log.info("Clicked label containing 'Custom Input' text.")
                    time.sleep(0.5)
                    return True
            except: pass
            
        # 3. Search for any buttons or checkboxes with labels containing 'custom'
        for el in self.driver.find_elements(By.XPATH, "//button | //a | //input"):
            try:
                if el.is_displayed():
                    text = (el.text or el.get_attribute("value") or "").lower()
                    if "custom" in text:
                        self.driver.execute_script("arguments[0].click();", el)
                        log.info(f"Clicked button/element '{text}' to enable custom input.")
                        time.sleep(0.5)
                        return True
            except: pass
            
        log.warning("Could not find any obvious element to enable custom input.")
        return False

    def set_custom_input_value(self, input_text):
        """
        Type the parsed example input into the custom input textarea.
        """
        log.info(f"Setting custom input value: {repr(input_text)}")
        
        # Locate target textareas
        candidates = []
        for ta in self.driver.find_elements(By.XPATH, "//textarea"):
            try:
                if ta.is_displayed():
                    score = 0
                    for attr in ["id", "class", "name", "placeholder"]:
                        val = (ta.get_attribute(attr) or "").lower()
                        if "input" in val: score += 5
                        if "custom" in val: score += 10
                        if "test" in val: score += 3
                    candidates.append((score, ta))
            except: pass
            
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            target_ta = candidates[0][1]
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_ta)
                time.sleep(0.2)
                target_ta.clear()
                target_ta.send_keys(input_text)
                log.info("Successfully entered custom input into textarea via SendKeys.")
                return True
            except Exception as e:
                log.warning(f"Error entering input via selenium send_keys: {e}")
                try:
                    self.driver.execute_script("arguments[0].value = arguments[1];", target_ta, input_text)
                    log.info("Entered custom input via direct JS value script.")
                    return True
                except: pass
                
        # Fallback check for contenteditable elements
        for ce in self.driver.find_elements(By.XPATH, "//*[@contenteditable='true']"):
            try:
                if ce.is_displayed():
                    self.driver.execute_script("arguments[0].innerText = arguments[1];", ce, input_text)
                    log.info("Entered custom input into contenteditable element.")
                    return True
            except: pass
            
        log.warning("Could not find any visible custom input textarea/input element.")
        return False
        
    def get_mcq_options(self):
        # Extract all text options adjacent to radio button choice selectors.
        opts = []
        for inp in self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox']"):
            try:
                text = inp.find_element(By.XPATH, "..").text.strip() or inp.find_element(By.XPATH, "../..").text.strip()
                if text and text not in opts: opts.append(text)
            except: pass
        return opts if len(opts) >= 2 else ["A", "B", "C", "D"]
        
    def select_mcq_option(self, target):
        if not target: return False
        norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
        for el in self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox'] | //label | //li"):
            try:
                if el.is_displayed() and (target.lower() in el.text.lower() or norm(target) in norm(el.text)):
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
            except: pass
        try:
            inputs = self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox']")
            if inputs:
                self.driver.execute_script("arguments[0].click();", inputs[0])
                return True
        except: pass
        return False

    def enter_code_solution(self, code):
        log.info("Injecting C++ code solution...")
        js_inject = """
        var val = arguments[0];
        try {
            if (typeof monaco !== 'undefined' && monaco.editor && monaco.editor.getModels && monaco.editor.getModels()[0]) {
                monaco.editor.getModels()[0].setValue(val);
            }
        } catch(e) {}
        try {
            var cmEl = document.querySelector('.CodeMirror');
            if (cmEl && cmEl.CodeMirror) {
                cmEl.CodeMirror.setValue(val);
            }
        } catch(e) {}
        try {
            document.querySelectorAll('textarea, [contenteditable="true"]').forEach(el => {
                try {
                    if (el.tagName === 'TEXTAREA') { el.value = val; } else { el.innerText = val; }
                    ['input', 'change', 'keydown', 'keyup'].forEach(ev => el.dispatchEvent(new Event(ev, { bubbles: true })));
                } catch(e) {}
            });
        } catch(e) {}
        """
        try:
            self.driver.execute_script(js_inject, code)
            time.sleep(0.5)
        except Exception as e:
            log.warning(f"Injection exception: {e}")

    def _click_button(self, labels):
        conds = " or ".join([f"contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{s}')" for s in labels])
        for el in self.driver.find_elements(By.XPATH, f"//button[{conds}] | //a[{conds}] | //input[{conds}]"):
            try:
                if el.is_displayed() and el.is_enabled():
                    text = (el.text or el.get_attribute("value") or "").lower()
                    if any(x in text for x in ["test", "assessment", "all", "final", "finish", "end"]):
                        continue
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
                    time.sleep(0.3)
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
            except: pass
        return False
             
    def click_save_and_next(self):
        if not self._click_button(['save', 'next']):
            self.return_to_summary()
   
    def clear_outputs_on_page(self):
        pass

    def submit_code(self):
        self.clear_outputs_on_page()
        for el in self.driver.find_elements(By.XPATH, "//button | //a | //input"):
            try:
                if el.is_displayed() and el.is_enabled():
                    text = (el.text or el.get_attribute("value") or "").lower()
                    if "submit" in text and not any(x in text for x in ["test", "assessment", "all", "final", "finish", "end"]):
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
                        time.sleep(0.3)
                        self.driver.execute_script("arguments[0].click();", el)
                        return True
            except: pass
        self._click_button(['submit'])
             
    def run_code(self):
        self.clear_outputs_on_page()
        self._click_button(['run'])

    def click_solve_if_present(self):
        self._click_button(['solve'])

    def get_run_outputs(self):
        expected_text = ""
        actual_text = ""
        
        def is_in_problem_panel(element):
            try:
                curr = element
                for _ in range(5):
                    if not curr: break
                    cls = (curr.get_attribute("class") or "").lower()
                    id_val = (curr.get_attribute("id") or "").lower()
                    if any(x in cls or x in id_val for x in ["problem", "desc", "instruction", "statement", "left-pane", "col-md-6"]):
                        return True
                    curr = curr.find_element(By.XPATH, "./..")
            except:
                pass
            return False
        
        def find_output_for_label(keywords):
            xpath_query = "//*[starts-with(name(), 'h') or name()='div' or name()='span' or name()='p' or name()='label' or name()='strong']"
            for el in self.driver.find_elements(By.XPATH, xpath_query):
                try:
                    if el.is_displayed():
                        if is_in_problem_panel(el):
                            continue
                        txt = el.text.strip().lower()
                        if all(k in txt for k in keywords):
                            parent = el.find_element(By.XPATH, "./..")
                            for sub in parent.find_elements(By.XPATH, ".//pre | .//code | .//textarea | .//div[contains(@class, 'output') or contains(@class, 'console')]"):
                                if sub.is_displayed() and sub != el:
                                    content = sub.text.strip() or sub.get_attribute("value") or ""
                                    if content:
                                        return content.strip()
                            
                            sibling = el.find_element(By.XPATH, "./following-sibling::*[1]")
                            content = sibling.text.strip() or sibling.get_attribute("value") or ""
                            if content:
                                return content.strip()
                except: pass
            return ""

        expected_text = find_output_for_label(["expected"])
        actual_text = find_output_for_label(["your", "output"])
        
        if not actual_text:
            actual_text = find_output_for_label(["actual", "output"])
            
        if not actual_text:
            # Fallback to output keyword excluding expected
            xpath_query = "//*[starts-with(name(), 'h') or name()='div' or name()='span' or name()='p' or name()='label' or name()='strong']"
            for el in self.driver.find_elements(By.XPATH, xpath_query):
                try:
                    if el.is_displayed():
                        if is_in_problem_panel(el):
                            continue
                        txt = el.text.strip().lower()
                        if "output" in txt and "expected" not in txt:
                            parent = el.find_element(By.XPATH, "./..")
                            for sub in parent.find_elements(By.XPATH, ".//pre | .//code | .//textarea"):
                                if sub.is_displayed() and sub != el:
                                    content = sub.text.strip() or sub.get_attribute("value") or ""
                                    if content:
                                        actual_text = content.strip()
                                        break
                            if actual_text:
                                break
                except: pass
                    
        return expected_text, actual_text

    def get_console_errors(self):
        """
        Locate and extract any compilation or runtime errors printed in the terminal.
        """
        log.info("Searching for compilation or runtime errors in the output panel...")
        error_containers = [
            "//*[contains(@class, 'error') or contains(@id, 'error') or contains(@class, 'compile') or contains(@class, 'terminal')]",
            "//pre[contains(text(), 'Error') or contains(text(), 'error') or contains(text(), 'Exception') or contains(text(), 'Compilation')]"
        ]
        
        found_errors = []
        for xpath in error_containers:
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        text = el.text.strip()
                        if text and len(text) > 10 and not any(flag in text.lower() for flag in ["loading", "processing"]):
                            if text not in found_errors:
                                found_errors.append(text)
                except: pass
                
        if found_errors:
            err_text = "\n".join(found_errors)
            log.info(f"Extracted console error trace: {err_text[:200]}...")
            return err_text
        return ""

    def get_code_result(self, old_actual=None):
        # 1. Wait for processing to complete
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        time.sleep(1.5)
        processing_loc = (By.XPATH, "//*[contains(normalize-space(.), 'Processing...')]")
        try:
            WebDriverWait(self.driver, 20).until(
                EC.invisibility_of_element_located(processing_loc)
            )
            time.sleep(1) # Render wait
        except:
            log.warning("Timeout waiting for processing to finish.")
            
        # 2. Wait until the actual output is loaded and has changed from old stale output
        start_time = time.time()
        while time.time() - start_time < 8:
            expected, actual = self.get_run_outputs()
            if actual and actual.strip():
                if old_actual and actual.strip() == old_actual.strip():
                    time.sleep(0.5)
                    continue
                break
            time.sleep(0.5)

        # 3. Check for specific failure/error flags on screen
        error_flags = [
            "wrong answer", "time limit exceeded", "time limit exceed", "tle", 
            "runtime error", "rte", "compilation error", "failed", "partially correct"
        ]
        try:
            elements = self.driver.find_elements(By.XPATH, "//*[self::div or self::span or self::p or self::h3 or self::h4 or self::h5 or self::strong]")
            found_errors = []
            for el in elements:
                try:
                    if el.is_displayed():
                        txt = el.text.strip().lower()
                        for flag in error_flags:
                            if flag in txt and len(txt) < 150:
                                val = el.text.strip()
                                if val and val not in found_errors and len(val) > 2:
                                    found_errors.append(val)
                except: pass
            if found_errors:
                err_summary = "\n".join(found_errors)
                log.info(f"Detected failure/error flags on page: {err_summary}")
                return False, err_summary
        except Exception as e:
            log.warning(f"Error checking error flags: {e}")
        
        # 4. Extract expected vs actual outputs
        try:
            expected, actual = self.get_run_outputs()
            if expected or actual:
                log.info(f"Extracted Expected Output: {repr(expected)}")
                log.info(f"Extracted Your Output: {repr(actual)}")
                

                # Extract all integers (including negative numbers)
                exp_ints = re.findall(r'-?\d+', expected)
                act_ints = re.findall(r'-?\d+', actual)
                
                if exp_ints and act_ints and exp_ints == act_ints:
                    log.info(f"Expected integers {exp_ints} and actual integers {act_ints} MATCH perfectly!")
                    return True, ""
                else:
                    mismatch_err = f"Output Mismatch!\nExpected Output:\n{expected}\n\nYour Output:\n{actual}"
                    return False, mismatch_err
        except Exception as e:
            log.warning(f"Error executing output validation check: {e}")
            
        # 5. Fallback check for compiler or execution errors
        console_err = self.get_console_errors()
        if console_err:
            return False, console_err
            
        # 6. Fallback to general DOM search for fail/error text
        failed_loc = (By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'fail') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'error')]")
        try:
            failed_elements = self.driver.find_elements(*failed_loc)
            actual_errors = []
            for elem in failed_elements:
                if elem.is_displayed():
                    text = elem.text.strip()
                    if text and len(text) > 2 and text.lower() not in ["failed", "error"]:
                        actual_errors.append(text)
            if actual_errors:
                return False, "\n".join(actual_errors)
        except Exception as e:
            log.warning(f"Error checking fallback code result: {e}")
            
        log.warning("No matching expected/actual outputs found. Flagging validation as failed.")
        return False, "Validation output mismatch or execution failure (expected/actual outputs not found or empty)."

    def return_to_summary(self):
        return self._click_button(['summary', 'dashboard', 'back', 'sections'])

    def is_sidebar_open(self):
        try:
            for xpath in ["//*[contains(text(), 'Overall Summary')]", "//*[contains(text(), 'CODING QUESTIONS')]", "//*[contains(text(), 'MCQ QUESTIONS')]"]:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed():
                        return True
        except: pass
        return False

    def open_sidebar(self):
        if self.is_sidebar_open():
            log.info("Sidebar is already open.")
            return True
        log.info("Sidebar is closed. Attempting to open sidebar...")
        return self._click_sidebar_arrow()

    def close_sidebar(self):
        if not self.is_sidebar_open():
            log.info("Sidebar is already closed.")
            return True
        log.info("Sidebar is open. Attempting to close sidebar...")
        return self._click_sidebar_arrow()

    def _click_sidebar_arrow(self):
        viewport_width = self.driver.execute_script("return window.innerWidth;")
        candidates = []
        for el in self.driver.find_elements(By.XPATH, "//button | //div[@role='button'] | //span[@role='button'] | //a[contains(@class, 'toggle') or contains(@class, 'sidebar') or contains(@class, 'arrow')]"):
            try:
                if el.is_displayed() and el.is_enabled():
                    rect = el.rect
                    if rect['x'] > (viewport_width * 0.5):
                        if rect['width'] < 80 and rect['height'] < 120:
                            candidates.append((rect['x'], el))
            except: pass
            
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            for x, el in candidates:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.3)
                    self.driver.execute_script("arguments[0].click();", el)
                    time.sleep(1.0)
                    return True
                except: pass
                
        for xpath in [
            "//*[local-name()='svg' and (contains(@class, 'arrow') or contains(@class, 'sidebar'))]",
            "//button[contains(@class, 'sidebar') or contains(@class, 'drawer')]"
        ]:
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        rect = el.rect
                        if rect['x'] > (viewport_width * 0.5):
                            self.driver.execute_script("arguments[0].click();", el)
                            time.sleep(1.0)
                            return True
                except: pass
        return False

    def click_overall_summary(self):
        log.info("Clicking Overall Summary button in sidebar...")
        for xpath in ["//*[contains(text(), 'Overall Summary')]", "//*[contains(text(), 'overall summary')]", "//*[contains(text(), 'Summary')]"]:
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(1.0)
                        return True
                except: pass
        return False

    def get_sidebar_questions(self):
        log.info("Scanning sidebar for assessment questions...")
        questions = []
        
        sidebar_el = None
        for sel in ["//*[contains(@class, 'sidebar') or contains(@class, 'drawer') or contains(@class, 'panel')]", "//div[contains(@class, 'right')]"]:
            elements = self.driver.find_elements(By.XPATH, sel)
            for el in elements:
                try:
                    if el.is_displayed() and el.rect['x'] > (self.driver.execute_script("return window.innerWidth;") * 0.5):
                        sidebar_el = el
                        break
                except: pass
            if sidebar_el: break
            
        container = sidebar_el if sidebar_el else self.driver
        items = container.find_elements(By.XPATH, ".//a | .//button | .//div[@role='button'] | .//*[contains(@class, 'question-item') or contains(@class, 'question-link') or contains(@class, 'Q')]")
        
        for el in items:
            try:
                if el.is_displayed():
                    text = el.text.strip()
                    match = re.search(r'\b(?:Q|Question\s*)?(\d+)\b', text, re.IGNORECASE)
                    if match:
                        q_idx = int(match.group(1))
                        if any(q['index'] == q_idx for q in questions):
                            continue
                            
                        is_solved = False
                        html = el.get_attribute("outerHTML") or ""
                        
                        badge_els = el.find_elements(By.XPATH, ".//*[contains(@class, 'badge') or contains(@class, 'status') or contains(@class, 'circle') or contains(text(), 'Q')]")
                        if not badge_els:
                            badge_els = [el]
                            
                        for badge in badge_els:
                            bg_color = badge.value_of_css_property("background-color") or ""
                            if "rgb" in bg_color or "rgba" in bg_color:
                                nums = [int(s) for s in re.findall(r'\d+', bg_color)]
                                if len(nums) >= 3:
                                    r, g, b = nums[0], nums[1], nums[2]
                                    if g > r * 1.2 and g > b * 1.2 and g > 80:
                                        is_solved = True
                                        break
                                        
                            classes = (badge.get_attribute("class") or "").lower()
                            if any(x in classes for x in ["success", "passed", "solved", "green", "bg-emerald", "bg-teal"]):
                                if "partial" not in classes and "warning" not in classes:
                                    is_solved = True
                                    break
                                
                        is_html_solved = False
                        if "success" in html.lower() or ("solved" in html.lower() and "partially" not in html.lower() and "partial" not in html.lower()):
                            if "wrong" not in html.lower() and "fail" not in html.lower():
                                is_html_solved = True
                                
                        if not is_solved and ("green" in html.lower() or is_html_solved):
                            is_solved = True
                            
                        q_type = "CODING"
                        try:
                            parent_text = el.find_element(By.XPATH, "./ancestor::*[contains(text(), 'MCQ') or contains(text(), 'mcq')]").text
                            if "mcq" in parent_text.lower():
                                q_type = "MCQ"
                        except: pass
                        
                        if "mcq" in text.lower() or "mcq" in html.lower():
                            q_type = "MCQ"
                            
                        questions.append({
                            'index': q_idx,
                            'name': text,
                            'type': q_type,
                            'is_solved': is_solved,
                            'element': el
                        })
            except: pass
                
        questions.sort(key=lambda q: q['index'])
        log.info(f"Sidebar scan complete: found {len(questions)} questions.")
        for q in questions:
            log.info(f" - Q{q['index']}: {q['name'][:30]} | Type: {q['type']} | Solved: {q['is_solved']}")
        return questions
