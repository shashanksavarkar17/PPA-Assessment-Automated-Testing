import time
import re
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

log = get_logger(__name__)

# Page Object class representing standard question panels for MCQ and coding problem types.
class QuestionPage(BasePage):
    def dismiss_reset_popup(self):
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            alert.accept()
            log.info(f"Dismissed system alert popup: '{alert_text}'")
            time.sleep(0.3)
            return True
        except: pass
        
        try:
            for el in self.driver.find_elements(By.XPATH, "//button | //a | //div[@role='button']"):
                try:
                    if el.is_displayed() and el.is_enabled():
                        text = (el.text or el.get_attribute("value") or "").lower()
                        if any(x in text for x in ["yes", "confirm", "reset", "ok", "change", "continue"]):
                            if not any(x in text for x in ["test", "assessment", "all", "final", "finish", "end"]):
                                self.driver.execute_script("arguments[0].click();", el)
                                log.info(f"Proactively dismissed code reset/confirmation popup by clicking: '{el.text.strip()}'")
                                time.sleep(0.3)
                                return True
                except: pass
        except: pass
        return False

    def wait_for_page_load(self):
        # Terminate any proactive proctoring notifications or dialogs.
        for _ in range(3):
            try:
                for btn in self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Return')]"):
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
            except: pass
        self.dismiss_reset_popup()
        self.helpers.wait_for_element((By.XPATH, "//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'editor')]"))
        
    def get_question_type(self):
        # Determine question category by scanning for standard option input components.
        if self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox'] | //*[contains(@class, 'option') or contains(@class, 'choice')]"):
            return "MCQ"
        return "CODING"
            
    def get_question_text(self):
        # Retrieve visible problem statement content.
        for sel in ["//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'ql-editor')]", "body"]:
            elements = self.driver.find_elements(By.XPATH, sel)
            if elements and elements[0].text.strip():
                return elements[0].text.strip()
        return "Unknown Question"
        
    def get_selected_language(self):
        # Extract currently designated compiler language.
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
                            self.dismiss_reset_popup()
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
                                        self.dismiss_reset_popup()
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
                        # Parse competitive programming test pattern template.
                        match = re.search(r'(?:input|sample input|example input):?\s*\n?(.*?)\s*\n?(?:output|sample output|example output):?\s*\n?(.*)', text, re.IGNORECASE | re.DOTALL)
                        if match:
                            inp = match.group(1).strip()
                            out = match.group(2).strip()
                            # Remove label prefixes from match boundaries.
                            inp = re.sub(r'^(?:input|sample input|example input):?\s*', '', inp, flags=re.I).strip()
                            out = re.sub(r'^(?:output|sample output|example output):?\s*', '', out, flags=re.I).strip()
                            log.info(f"Parsed example from <pre> tag. Input: {repr(inp)}, Output: {repr(out)}")
                            return inp, out
            except Exception as e:
                log.warning(f"Error checking pre tag: {e}")
                
        # Fallback analysis using generic regular expression parsing on page text.
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
        
        # 1. Search for explicit input checkboxes targeting custom input/test
        checkboxes_xpath = "//input[@type='checkbox'][contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom') or contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom') or contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom') or contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom') or contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'input') or contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'input') or contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'input') or contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'input')]"
        for inp in self.driver.find_elements(By.XPATH, checkboxes_xpath):
            try:
                if inp.is_displayed():
                    if not inp.is_selected():
                        self.driver.execute_script("arguments[0].click();", inp)
                        log.info("Enabled custom input checkbox via direct element click.")
                        time.sleep(0.3)
                    return True
            except: pass
            
        # 2. Scan label text content for custom input/test tags.
        labels_xpath = "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom input') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom test')]"
        for label in self.driver.find_elements(By.XPATH, labels_xpath):
            try:
                if label.is_displayed():
                    self.driver.execute_script("arguments[0].click();", label)
                    log.info("Clicked label containing 'Custom Input' text.")
                    time.sleep(0.3)
                    return True
            except: pass
            
        # 3. Scan button/input elements containing "custom"
        buttons_xpath = "//*[self::button or self::a or self::input][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom') or contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom') or contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom')]"
        for el in self.driver.find_elements(By.XPATH, buttons_xpath):
            try:
                if el.is_displayed():
                    self.driver.execute_script("arguments[0].click();", el)
                    log.info("Clicked element to enable custom input.")
                    time.sleep(0.3)
                    return True
            except: pass
            
        log.warning("Could not find any obvious element to enable custom input.")
        return False

    def set_custom_input_value(self, input_text):
        """
        Type the parsed example input into the custom input textarea.
        """
        log.info(f"Setting custom input value: {repr(input_text)}")
        
        # Locate target input fields.
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
                
        # Fallback evaluation of rich-text contenteditable boundaries.
        for ce in self.driver.find_elements(By.XPATH, "//*[@contenteditable='true']"):
            try:
                if ce.is_displayed():
                    self.driver.execute_script("arguments[0].innerText = arguments[1];", ce, input_text)
                    log.info("Entered custom input into contenteditable element.")
                    return True
            except: pass
            
        log.warning("Could not find any visible custom input textarea/input element.")
        return False
        
    def _find_option_elements(self):
        inputs = self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox']")
        if inputs:
            clickables = []
            for inp in inputs:
                added = False
                for xpath in ["./following-sibling::label", "./preceding-sibling::label", "..", "."]:
                    try:
                        el = inp.find_element(By.XPATH, xpath)
                        if el and el.is_displayed() and el not in clickables:
                            # Verify the element has text or contains the input
                            clickables.append(el)
                            added = True
                            break
                    except: pass
                if not added:
                    clickables.append(inp)
            return clickables
            
        lis = self.driver.find_elements(By.XPATH, "//li[contains(@class, 'option') or contains(@class, 'choice') or contains(@class, 'radio-label')]")
        if lis:
            return lis
            
        candidates = []
        for el in self.driver.find_elements(By.XPATH, "//li | //div[contains(@class, 'option') or contains(@class, 'choice') or contains(@class, 'item') or @role='radio']"):
            try:
                if el.is_displayed():
                    text = el.text.strip()
                    if text and len(text) < 150 and not any(h in text.lower() for h in ["question", "section", "instructions", "summary"]):
                        candidates.append(el)
            except: pass
        return candidates

    def get_mcq_options(self):
        elements = self._find_option_elements()
        opts = []
        for el in elements:
            try:
                text = el.text.strip()
                if not text:
                    text = el.find_element(By.XPATH, "..").text.strip() or el.find_element(By.XPATH, "../..").text.strip()
                if text and text not in opts:
                    opts.append(text)
            except: pass
            
        cleaned_opts = []
        for opt in opts:
            cleaned = re.sub(r'^[A-D]\.\s*|^[a-d]\)\s*', '', opt).strip()
            if cleaned and cleaned not in cleaned_opts:
                cleaned_opts.append(cleaned)
                
        if len(cleaned_opts) >= 2:
            return cleaned_opts
        return ["A", "B", "C", "D"]
        
    def select_mcq_option(self, target):
        if not target: return False
        elements = self._find_option_elements()
        norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
        target_norm = norm(target)
        
        def try_click_element(el):
            candidates = [el]
            for xpath in ["..", "../label", "./following-sibling::label", "./preceding-sibling::label", "./ancestor::label", "../.."]:
                try:
                    c = el.find_element(By.XPATH, xpath)
                    if c and c not in candidates:
                        candidates.append(c)
                except: pass
            
            for c in candidates:
                try:
                    if c.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", c)
                        time.sleep(0.1)
                        self.driver.execute_script("arguments[0].click();", c)
                        log.info(f"Clicked candidate element: <{c.tag_name} class='{c.get_attribute('class')}'>")
                        time.sleep(0.3)
                        return True
                except: pass
            return False

        # 1. Text-based direct matching
        for el in elements:
            try:
                if el.is_displayed():
                    text = el.text.strip()
                    if not text:
                        text = el.find_element(By.XPATH, "..").text.strip() or el.find_element(By.XPATH, "../..").text.strip()
                    
                    if target.lower() in text.lower() or target_norm in norm(text) or norm(text) in target_norm:
                        if try_click_element(el):
                            return True
            except: pass
            
        # 2. Index-based matching
        opts = self.get_mcq_options()
        match_idx = -1
        for idx, opt in enumerate(opts):
            if target.lower() in opt.lower() or norm(opt) in target_norm or target_norm in norm(opt):
                match_idx = idx
                break
                
        if match_idx == -1 and len(target) == 1 and target.upper() in ["A", "B", "C", "D"]:
            match_idx = ["A", "B", "C", "D"].index(target.upper())
            
        if match_idx != -1 and match_idx < len(elements):
            target_el = elements[match_idx]
            if try_click_element(target_el):
                return True
            
        # 3. Fallback to click first visible option element
        if elements:
            if try_click_element(elements[0]):
                return True
            
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
        # Build an optimized XPath to find only buttons, links, or inputs containing any target label
        conditions = " or ".join([f"contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label.lower()}')" for label in labels])
        val_conditions = " or ".join([f"contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label.lower()}')" for label in labels])
        xpath_query = f"//button[{conditions}] | //a[{conditions}] | //input[{val_conditions}]"
        
        elements = self.driver.find_elements(By.XPATH, xpath_query)
        for el in elements:
            try:
                if el.is_displayed() and el.is_enabled():
                    text = (el.text or el.get_attribute("value") or "").lower()
                    if not any(x in text for x in ["test", "assessment", "all", "final", "finish", "end"]):
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                        time.sleep(0.1)
                        self.driver.execute_script("arguments[0].click();", el)
                        return True
            except: pass
        return False
             
    def is_next_button_disabled(self):
        try:
            xpath = "//button | //a"
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        text = el.text.lower()
                        if "next" in text:
                            disabled = el.get_attribute("disabled")
                            aria_disabled = el.get_attribute("aria-disabled")
                            classes = (el.get_attribute("class") or "").lower()
                            if disabled == "true" or aria_disabled == "true" or "disabled" in classes or not el.is_enabled():
                                return True
                except: pass
            return False
        except:
            return False

    def click_save_and_next(self):
        return self._click_button(['save', 'next', 'submit'])
   
    def clear_outputs_on_page(self):
        pass

    def submit_mcq_answer(self):
        return self._click_button(["submit", "save", "lock"])
        
    def submit_code(self):
        self.clear_outputs_on_page()
        return self._click_button(['submit'])
             
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
            conditions = " and ".join([f"contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{k}')" for k in keywords])
            xpath_query = f"//*[starts-with(name(), 'h') or name()='div' or name()='span' or name()='p' or name()='label' or name()='strong'][{conditions}]"
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
            xpath_query = "//*[starts-with(name(), 'h') or name()='div' or name()='span' or name()='p' or name()='label' or name()='strong'][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'output') and not(contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'expected'))]"
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
        # Wait for processing state to complete.
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        time.sleep(1.5)
        processing_loc = (By.XPATH, "//*[contains(normalize-space(.), 'Processing...')]")
        try:
            WebDriverWait(self.driver, 20).until(
                EC.invisibility_of_element_located(processing_loc)
            )
            time.sleep(1) # Block for UI rendering stability.
        except:
            log.warning("Timeout waiting for processing to finish.")
            
        # Wait until output refresh completes.
        start_time = time.time()
        while time.time() - start_time < 8:
            expected, actual = self.get_run_outputs()
            if actual and actual.strip():
                if old_actual and actual.strip() == old_actual.strip():
                    time.sleep(0.5)
                    continue
                break
            time.sleep(0.5)

        # Analyze page elements for compiler or runtime error codes.
        error_flags = [
            "wrong answer", "time limit exceeded", "time limit exceed", "tle", 
            "runtime error", "rte", "compilation error", "failed", "partially correct"
        ]
        try:
            # Build an optimized XPath to query only elements that actually contain the error flags
            xpath_conditions = " or ".join([f"contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{flag}')" for flag in error_flags])
            elements = self.driver.find_elements(By.XPATH, f"//*[self::div or self::span or self::p or self::strong or self::h3 or self::h4 or self::h5][{xpath_conditions}]")
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
        
        # Extract and compare expected versus actual program outputs.
        try:
            expected, actual = self.get_run_outputs()
            if expected or actual:
                log.info(f"Extracted Expected Output: {repr(expected)}")
                log.info(f"Extracted Your Output: {repr(actual)}")
                

                # Identify integer groups from text.
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
            
        # Retrieve fallback compilation diagnostic messages.
        console_err = self.get_console_errors()
        if console_err:
            return False, console_err
            
        # Perform a generic DOM inquiry for failed validation logs.
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
            for xpath in ["//*[contains(text(), 'Overall Summary')]", "//*[contains(text(), 'Summary')]", "//*[contains(text(), 'QUESTIONS')]"]:
                for el in self.driver.find_elements(By.XPATH, xpath):
                    if el.is_displayed() and el.rect['x'] > (self.driver.execute_script("return window.innerWidth;") * 0.5):
                        return True
            for el in self.driver.find_elements(By.XPATH, "//div[contains(@class, 'sidebar') or contains(@class, 'drawer')]//*[contains(text(), 'Q')]"):
                if el.is_displayed() and el.rect['x'] > (self.driver.execute_script("return window.innerWidth;") * 0.5):
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
        
        # High-fidelity debug dump of the sidebar element
        try:
            import os
            debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
            os.makedirs(debug_dir, exist_ok=True)
            debug_path = os.path.join(debug_dir, "sidebar_debug.html")
            if not os.path.exists(debug_path) and sidebar_el:
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(sidebar_el.get_attribute("outerHTML") or "")
                log.info(f"✔ Successfully dumped sidebar HTML structure to {debug_path}")
        except Exception as dump_err:
            log.warning(f"Failed to dump sidebar HTML: {dump_err}")
            
        items = container.find_elements(By.XPATH, ".//a | .//button | .//div[@role='button'] | .//*[contains(@class, 'question-item') or contains(@class, 'question-link') or contains(@class, 'Q')]")
        
        for el in items:
            try:
                if el.is_displayed():
                    raw_text = el.text.strip()
                    text = " ".join([line.strip() for line in raw_text.splitlines() if line.strip()])
                    if not text or len(text) < 3:
                        continue
                        
                    # Filter out non-question utility elements
                    lower_text = text.lower()
                    if any(u in lower_text for u in ["overall summary", "next question", "previous question", "instructions", "review", "submit", "section:", "coding section", "mcq section"]):
                        continue
                        
                    # Enforce strict digit check so we only match real question nodes (e.g. "Q1", "Question 1", "1.")
                    match = re.search(r'\b(?:Q|Question\s*)?(\d+)\b', text, re.IGNORECASE)
                    if not match:
                        continue
                        
                    q_idx = int(match.group(1))
                    if any(q['index'] == q_idx for q in questions):
                        continue
                        
                    if any(q['name'] == text for q in questions):
                        continue
                        
                    is_solved = False
                    html = el.get_attribute("outerHTML") or ""
                    
                    badge_els = el.find_elements(By.XPATH, ".//*[contains(@class, 'badge') or contains(@class, 'status') or contains(@class, 'circle')]")
                    if not badge_els:
                        badge_els = [el]
                        
                    for badge in badge_els:
                        bg_color = badge.value_of_css_property("background-color") or ""
                        if "rgb" in bg_color or "rgba" in bg_color:
                            nums = [int(s) for s in re.findall(r'\d+', bg_color)]
                            if len(nums) >= 3:
                                r, g, b = nums[0], nums[1], nums[2]
                                if g > r * 1.4 and g > b * 1.4 and g > 110:
                                    is_solved = True
                                    break
                                    
                        classes = (badge.get_attribute("class") or "").lower()
                        if any(x in classes for x in ["success", "passed", "solved", "badge-success", "q-solved"]):
                            if not any(x in classes for x in ["partial", "warning", "unsolved", "failed"]):
                                is_solved = True
                                break
                            
                    if not is_solved:
                        if any(marker in html.lower() for marker in ["status-success", "q-solved", "badge-success", "solved-badge", "class=\"solved\""]):
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

    def switch_sidebar_section(self, section_name, section_idx=None):
        """
        Locate and click the sidebar section header/accordion to switch to the target section.
        """
        self.open_sidebar()
        time.sleep(0.3)
        
        # Clean section name to target parts
        clean_name = section_name.replace("Section:", "").strip()
        log.info(f"Attempting to switch sidebar section to: '{clean_name}'")
        
        # Search for sidebar container to inspect current state
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
        
        # First, check if the target section is already expanded/visible.
        # We can detect this by checking if any question elements belonging to this section are already visible.
        current_visible_questions = []
        try:
            items = container.find_elements(By.XPATH, ".//a | .//button | .//div[@role='button'] | .//*[contains(@class, 'question-item') or contains(@class, 'question-link') or contains(@class, 'Q')]")
            for el in items:
                if el.is_displayed():
                    txt = el.text.strip()
                    if re.search(r'\b(?:Q|Question\s*)?(\d+)\b', txt, re.IGNORECASE):
                        q_type = "CODING"
                        html = el.get_attribute("outerHTML") or ""
                        try:
                            parent_text = el.find_element(By.XPATH, "./ancestor::*[contains(text(), 'MCQ') or contains(text(), 'mcq')]").text
                            if "mcq" in parent_text.lower():
                                q_type = "MCQ"
                        except: pass
                        if "mcq" in txt.lower() or "mcq" in html.lower():
                            q_type = "MCQ"
                        current_visible_questions.append(q_type)
        except: pass
        
        target_type = "CODING"
        if any(x in clean_name.lower() for x in ["mcq", "multiple choice"]):
            target_type = "MCQ"
            
        if target_type in current_visible_questions:
            log.info(f"✔ Section '{clean_name}' is already expanded in the sidebar (found visible {target_type} questions). Skipping click toggle.")
            return True
        
        # Build candidates to search for in order of specificity
        keywords = [clean_name]
        parts = [p.strip() for p in re.split(r'[\s\-:]+', clean_name) if p.strip()]
        
        # Add non-generic specific sub-parts
        for p in parts:
            if p.lower() not in ["section", "part", "questions", "question"] and p not in keywords:
                keywords.append(p)
                
        # Perform acronym expansion (e.g., MCQ -> Multiple Choice)
        expanded_keywords = []
        for kw in keywords:
            expanded_keywords.append(kw)
            if kw.lower() == "mcq" or kw.lower() == "mcqs":
                expanded_keywords.extend(["multiple choice", "multiple choice questions", "mcqs", "mcq"])
            elif "multiple choice" in kw.lower():
                expanded_keywords.extend(["mcq", "mcqs"])
                
        # Filter duplicates while maintaining prioritized order
        unique_keywords = []
        for kw in expanded_keywords:
            if kw not in unique_keywords:
                unique_keywords.append(kw)
        keywords = unique_keywords
        
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
        
        for kw in keywords:
            if not kw or len(kw) < 2: continue
            log.info(f"Searching sidebar for section element containing: '{kw}'")
            xpath = f".//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw.lower()}')]"
            elements = container.find_elements(By.XPATH, xpath)
            for el in elements:
                try:
                    if el.is_displayed():
                        tag = el.tag_name.lower()
                        if tag in ["div", "span", "button", "h3", "h4", "h5", "a", "p"]:
                            # Find the closest clickable parent container (up to 3 levels up)
                            click_target = el
                            curr = el
                            for _ in range(3):
                                try:
                                    curr = curr.find_element(By.XPATH, "./parent::*")
                                    classes = (curr.get_attribute("class") or "").lower()
                                    if "cursor-pointer" in classes or curr.tag_name.lower() in ["button", "a"]:
                                        click_target = curr
                                        if "cursor-pointer" in classes:
                                            break
                                except:
                                    break
                            
                            log.info(f"Found candidate section element in sidebar: <{tag}> '{el.text[:30]}'. Clicking target <{click_target.tag_name}> (Class: '{click_target.get_attribute('class')}')")
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", click_target)
                            time.sleep(0.2)
                            try:
                                self.driver.execute_script("arguments[0].click();", click_target)
                                log.info("Successfully toggled sidebar section accordion via JS click.")
                            except Exception as js_err:
                                log.warning(f"JS click failed: {js_err}. Trying native click...")
                                click_target.click()
                                log.info("Natively clicked sidebar section target.")
                            time.sleep(0.5)
                            return True
                except: pass
                
        # Index-based section header fallback in sidebar if text matching failed
        if section_idx is not None:
            log.info(f"Name-based section switch failed. Attempting index-based switch for section index: {section_idx}")
            headers_xpath = ".//button | .//h3 | .//h4 | .//h5 | .//div[contains(@class, 'header') or contains(@class, 'title') or contains(@class, 'accordion')]"
            headers = container.find_elements(By.XPATH, headers_xpath)
            candidates = []
            for h in headers:
                try:
                    if h.is_displayed() and h.text.strip():
                        txt = h.text.lower()
                        # Strictly filter out non-header utility elements
                        if not any(x in txt for x in ["q1", "q2", "q3", "question", "overall summary", "next", "prev", "previous", "submit", "run", "test", "clear", "save", "cancel", "back", "next question"]):
                            if h not in candidates:
                                candidates.append(h)
                except: pass
                
            log.info(f"Found {len(candidates)} potential section headers in sidebar.")
            if candidates and section_idx - 1 < len(candidates):
                target_header = candidates[section_idx - 1]
                log.info(f"Clicking header at index {section_idx - 1}: '{target_header.text}'")
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_header)
                    time.sleep(0.2)
                    target_header.click()
                    time.sleep(0.5)
                    return True
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", target_header)
                        time.sleep(0.5)
                        return True
                    except: pass
        
        log.warning(f"Could not find or switch to sidebar section: '{clean_name}'")
        return False
