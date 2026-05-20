import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pages.base_page import BasePage

try:
    import tkinter as tk
except ImportError:
    tk = None

class QuestionPage(BasePage):
    """Dynamic question space for MCQ and Coding interactions."""

    def wait_for_page_load(self):
        self.helpers.wait_for_element((By.XPATH, "//*[contains(@class, 'problem-details') or contains(@class, 'ql-editor') or contains(@class, 'problem')]"))
        
    def get_question_type(self):
        return "MCQ" if self.driver.find_elements(By.XPATH, "//input[@type='radio']") else "CODING"
            
    def get_question_text(self):
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
        locs = [
            "//input[@type='radio']/following-sibling::span | //input[@type='radio']/following-sibling::label",
            "//label[//input[@type='radio']]", "//div[contains(@class, 'option')]"
        ]
        for loc in locs:
            opts = [e.text.strip() for e in self.driver.find_elements(By.XPATH, loc) if e.text.strip()]
            if len(set(opts)) >= 2:
                return list(dict.fromkeys(opts))
        
        opts = []
        for inp in self.driver.find_elements(By.XPATH, "//input[@type='radio']"):
            try: opts.append(inp.find_element(By.XPATH, "..").text.strip() or inp.find_element(By.XPATH, "../..").text.strip())
            except: pass
        return list(dict.fromkeys(filter(None, opts)))
        
    def select_mcq_option(self, target):
        norm = lambda s: "".join(c for c in s.lower() if c.isalnum()) if s else ""
        t_norm = norm(target)
        
        for el in self.driver.find_elements(By.XPATH, "//*[contains(@class, 'option') or self::label or self::span]"):
            if el.is_displayed() and (target.lower() in el.text.lower() or t_norm in norm(el.text)):
                candidates = [el] + el.find_elements(By.XPATH, ".//input[@type='radio']") + el.find_elements(By.XPATH, "../preceding-sibling::input | ../following-sibling::input")
                for c in candidates:
                    try:
                        c.click() if c.is_displayed() else self.driver.execute_script("arguments[0].click();", c)
                        return True
                    except: pass
        
        for inp in self.driver.find_elements(By.XPATH, "//input[@type='radio']"):
            try:
                parent_text = inp.find_element(By.XPATH, "..").text + inp.find_element(By.XPATH, "../..").text
                if t_norm in norm(parent_text):
                    self.driver.execute_script("arguments[0].click();", inp)
                    return True
            except: pass
        return False

    def enter_code_solution(self, code):
        try:
            self.driver.execute_script("if (typeof monaco !== 'undefined') { monaco.editor.getModels()[0].setValue(arguments[0]); }", code)
            return
        except: pass
            
        try:
            self.driver.execute_script("if (document.querySelector('.CodeMirror')) { document.querySelector('.CodeMirror').CodeMirror.setValue(arguments[0]); }", code)
            return
        except: pass

        locs = [".monaco-editor textarea.inputarea", ".CodeMirror textarea", "textarea.code-input"]
        for loc in locs:
            try:
                ta = self.driver.find_element(By.CSS_SELECTOR, loc)
                self.driver.execute_script("arguments[0].focus(); arguments[0].click();", ta)
                time.sleep(0.5)
                
                actions = ActionChains(self.driver)
                actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.DELETE).perform()
                
                use_clipboard = False
                if tk:
                    try:
                        root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(code); root.update(); root.destroy()
                        use_clipboard = True
                    except: pass
                
                if use_clipboard:
                    actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    actions.send_keys(code).perform()
                time.sleep(1)
                return
            except: continue

    def _click_button(self, xpath_match_strings):
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
        if not self._click_button(['save', 'next', 'submit']):
            self.return_to_summary()
 
    def submit_code(self):
        self._click_button(['submit'])
            
    def run_code(self):
        self._click_button(['run'])

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
        except:
            return False, "Error extracting code result."

    def click_solve_if_present(self):
        self._click_button(['solve'])

    def return_to_summary(self):
        return self._click_button(['summary', 'dashboard', 'back', 'sections'])
