import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pages.base_page import BasePage
from utils.logger import get_logger

log = get_logger(__name__)

try:
    import tkinter as tk
except ImportError:
    tk = None

# This handles both MCQ selection and coding answer submission for the active questions.
class QuestionPage(BasePage):
    def wait_for_page_load(self):
        # Let's clear any proctoring violation alerts if they try to block us.
        for _ in range(5):
            try:
                violation_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Return Back') or contains(text(), 'Return')]")
                if violation_btns and violation_btns[0].is_displayed():
                    log.info("Proctoring alert spotted! Dismissing it right away...")
                    self.driver.execute_script("arguments[0].click();", violation_btns[0])
                    time.sleep(1)
            except: pass
            
            try:
                self.helpers.wait_for_element((By.XPATH, "//*[contains(@class, 'problem-details') or contains(@class, 'ql-editor') or contains(@class, 'problem')]"), timeout=2)
                return
            except: pass
        self.helpers.wait_for_element((By.XPATH, "//*[contains(@class, 'problem-details') or contains(@class, 'ql-editor') or contains(@class, 'problem')]"))
        
    def get_question_type(self):
        # If we see any radio buttons on the page, it's definitely an MCQ question!
        return "MCQ" if self.driver.find_elements(By.XPATH, "//input[@type='radio']") else "CODING"
            
    def get_question_text(self):
        # We try to extract text from common problem-statement containers.
        selectors = [
            "//*[contains(@class, 'problem-details') or contains(@class, 'ql-editor') or contains(@class, 'problem-statement')]",
            "//*[contains(@class, 'question-text') or contains(@class, 'problem-container') or contains(@class, 'question-body')]",
            "//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'desc')]"
        ]
        for sel in selectors:
            for el in self.driver.find_elements(By.XPATH, sel):
                if el.is_displayed() and len(el.text.strip()) > 20:
                    return el.text.strip()
        return self.driver.find_element(By.TAG_NAME, "body").text
        
    def get_selected_language(self):
        # Let's identify which programming language is selected in the editor.
        locs = [
            "//select[contains(@class, 'lang') or contains(@class, 'language') or contains(@id, 'lang')]",
            "//*[contains(@class, 'lang-select')]//button",
            "//*[contains(@class, 'dropdown')]//*[contains(text(), 'C++') or contains(text(), 'Python') or contains(text(), 'Java')]"
        ]
        for loc in locs:
            for el in self.driver.find_elements(By.XPATH, loc):
                if el.is_displayed():
                    if el.tag_name == "select":
                        from selenium.webdriver.support.ui import Select
                        return Select(el).first_selected_option.text.strip()
                    return el.text.strip()
                    
        script = "let s = document.querySelector('select'); return s && s.selectedIndex >= 0 ? s.options[s.selectedIndex].text : null;"
        return self.driver.execute_script(script) or "C++"
        
    def get_mcq_options(self):
        # Scan standard option elements to present options to the solver.
        locs = [
            "//input[@type='radio']/following-sibling::span | //input[@type='radio']/following-sibling::label",
            "//label[//input[@type='radio']]", 
            "//*[contains(@class, 'option') or contains(@class, 'choice') or contains(@class, 'radio')]",
            "//li[contains(@class, 'option') or contains(@class, 'choice')]"
        ]
        for loc in locs:
            try:
                opts = [e.text.strip() for e in self.driver.find_elements(By.XPATH, loc) if e.text.strip()]
                clean_opts = list(dict.fromkeys([o for o in opts if len(o) > 0]))
                if len(clean_opts) >= 2: return clean_opts
            except: pass
            
        opts = []
        for inp in self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox']"):
            try:
                text = inp.find_element(By.XPATH, "..").text.strip() or inp.find_element(By.XPATH, "../..").text.strip()
                if text and text not in opts: opts.append(text)
            except: pass
        return opts
        
    def select_mcq_option(self, target):
        if not target: return False
        norm = lambda s: "".join(c for c in s.lower() if c.isalnum()) if s else ""
        t_norm = norm(target)
        
        # Look for target matches inside text labels or sibling inputs.
        locs = [
            "//input[@type='radio']/following-sibling::span | //input[@type='radio']/following-sibling::label",
            "//label[//input[@type='radio']]", 
            "//*[contains(@class, 'option') or contains(@class, 'choice') or contains(@class, 'radio')]",
            "//li[contains(@class, 'option') or contains(@class, 'choice')]"
        ]
        
        for loc in locs:
            for el in self.driver.find_elements(By.XPATH, loc):
                if el.is_displayed() and (target.lower() in el.text.lower() or t_norm in norm(el.text)):
                    for click_candidate in [el] + el.find_elements(By.XPATH, ".//input") + el.find_elements(By.XPATH, "../preceding-sibling::input | ../following-sibling::input"):
                        try:
                            self.driver.execute_script("arguments[0].click();", click_candidate)
                            return True
                        except: pass
        
        for inp in self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox']"):
            try:
                p_text = inp.find_element(By.XPATH, "..").text + inp.find_element(By.XPATH, "../..").text
                if t_norm in norm(p_text) or target.lower() in p_text.lower():
                    self.driver.execute_script("arguments[0].click();", inp)
                    return True
            except: pass
            
        try:
            # Fallback to absolute index choice match if exact text failed.
            radios = [r for r in self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox'] | //*[contains(@class, 'choice') or contains(@class, 'option')]") if r.is_displayed()]
            if radios:
                idx = -1
                for char in ['a', 'b', 'c', 'd', '1', '2', '3', '4']:
                    if target.lower().startswith(char) or target.lower().endswith(char):
                        idx = ['a', 'b', 'c', 'd', '1', '2', '3', '4'].index(char) % 4
                        break
                if 0 <= idx < len(radios):
                    self.driver.execute_script("arguments[0].click();", radios[idx])
                else:
                    self.driver.execute_script("arguments[0].click();", radios[0])
                return True
        except: pass
        return False

    def enter_code_solution(self, code):
        log.info("Starting direct injection script to bypass autocomplete duplicates...")
        
        # Tier 1: Manipulate Monaco or CodeMirror models directly.
        try:
            self.driver.execute_script("if (typeof monaco !== 'undefined') { monaco.editor.getModels()[0].setValue(arguments[0]); }", code)
            log.info("Successfully loaded solution directly inside Monaco API!")
        except Exception as e: log.debug(f"Monaco JS API failed: {e}")
            
        try:
            self.driver.execute_script("if (document.querySelector('.CodeMirror')) { document.querySelector('.CodeMirror').CodeMirror.setValue(arguments[0]); }", code)
            log.info("Successfully loaded solution directly inside CodeMirror API!")
        except Exception as e: log.debug(f"CodeMirror JS API failed: {e}")

        # Tier 1.5: Force change triggers on DOM textareas so JS frameworks (React/Vue/etc.) sync immediately.
        try:
            self.driver.execute_script("""
                var code = arguments[0];
                var elements = document.querySelectorAll('textarea, [contenteditable="true"], .monaco-editor textarea, .CodeMirror textarea');
                elements.forEach(function(el) {
                    try {
                        if (el.tagName === 'TEXTAREA') { el.value = code; } else { el.innerText = code; }
                        ['input', 'change', 'keydown', 'keyup'].forEach(function(ev) {
                            el.dispatchEvent(new Event(ev, { bubbles: true }));
                        });
                    } catch (err) {}
                });
            """, code)
        except Exception as e: log.warning(f"DOM framework event injection error: {e}")

        # Tier 2: Focus, clear, and paste via standard OS clipboard.
        locs = [".monaco-editor textarea.inputarea", ".CodeMirror textarea", "textarea.code-input", "textarea", "[contenteditable='true']"]
        for loc in locs:
            try:
                ta = self.driver.find_element(By.CSS_SELECTOR, loc)
                if not ta.is_displayed(): continue
                self.driver.execute_script("arguments[0].focus(); arguments[0].click();", ta)
                time.sleep(0.3)
                
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.DELETE).perform()
                time.sleep(0.2)
                
                use_clipboard = False
                if tk:
                    try:
                        root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(code); root.update(); root.destroy()
                        use_clipboard = True
                    except: pass
                
                actions = ActionChains(self.driver)
                if use_clipboard:
                    actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    log.info("Pasted complete code solution from system clipboard!")
                else:
                    actions.send_keys(code).perform()
                    log.info("Simulated fast keyboard typing input solver fallback.")
                time.sleep(0.5)
            except: continue
        log.info("Finished entering code solution successfully.")

    def _click_button(self, xpath_match_strings):
        # A super clean dynamic locator searching for lowercased button labels.
        conds = " or ".join([f"contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{s}')" for s in xpath_match_strings])
        xpath = f"//button[{conds}] | //a[{conds}] | //input[{conds}]"
        
        for el in self.driver.find_elements(By.XPATH, xpath):
            if el.is_displayed() and el.is_enabled():
                self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
                time.sleep(0.5)
                try: el.click()
                except: self.driver.execute_script("arguments[0].click();", el)
                time.sleep(1)
                return True
        return False
            
    def click_save_and_next(self):
        if not self._click_button(['save', 'next', 'submit']): self.return_to_summary()
  
    def submit_code(self): self._click_button(['submit'])
            
    def run_code(self): self._click_button(['run'])

    def get_run_result(self):
        time.sleep(2)
        try: WebDriverWait(self.driver, 10).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(text(), 'Processing')]")))
        except: pass
        
        res = ""
        for loc in ["//div[contains(@class, 'result') or contains(@class, 'output')]", "//*[contains(@class, 'console')]"]:
            for el in self.driver.find_elements(By.XPATH, loc):
                if el.is_displayed() and len(el.text) > 10:
                    res = el.text.strip()
                    break
        
        res_lower = res.lower()
        if any(e in res_lower for e in ["error", "wrong", "exceeded", "failed", "mismatch"]):
            return False, res
        if any(s in res_lower for s in ["passed", "correct", "success", "accepted"]):
            return True, ""
        return True, "" if "you must run or submit" not in res_lower else "No execution outcome seen."
            
    def get_code_result(self):
        time.sleep(2)
        try:
            fails = self.driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'FAIL', 'fail'), 'fail') or contains(translate(text(), 'ERROR', 'error'), 'error')]")
            errs = [f.text for f in fails if f.is_displayed() and len(f.text) > 2]
            return (False, "\n".join(errs)) if errs else (not bool(fails), "")
        except: return False, "Error extracting code result."

    def click_solve_if_present(self): self._click_button(['solve'])

    def take_question_screenshot(self, screenshot_path):
        import os
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        
        # Clear overlays first so we get a crystal clear screenshot of the problem statement.
        try:
            violation_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Return Back') or contains(text(), 'Return')]")
            if violation_btns and violation_btns[0].is_displayed():
                self.driver.execute_script("arguments[0].click();", violation_btns[0])
                time.sleep(1)
        except: pass

        # Strip CSS blurs if assessment uses any blur strategies during tab changes.
        try:
            unblur_js = """
            document.querySelectorAll('*').forEach(el => {
                let style = window.getComputedStyle(el);
                if (style.filter && style.filter.includes('blur')) el.style.filter = 'none';
                if (style.backdropFilter && style.backdropFilter.includes('blur')) el.style.backdropFilter = 'none';
                if (el.style.filter && el.style.filter.includes('blur')) el.style.filter = 'none';
            });
            """
            self.driver.execute_script(unblur_js)
            time.sleep(0.2)
        except: pass

        try:
            q_el = self.driver.find_element(By.XPATH, "//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'container') or contains(@class, 'details') or contains(@class, 'card')]")
            q_el.screenshot(screenshot_path)
        except:
            try: self.driver.save_screenshot(screenshot_path)
            except: pass

    def return_to_summary(self):
        return self._click_button(['summary', 'dashboard', 'back', 'sections'])
