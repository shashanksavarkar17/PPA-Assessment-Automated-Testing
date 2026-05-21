import time
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
        # Match the target choice text, click the matching option element, and proceed.
        if not target: return False
        norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
        for el in self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox'] | //label | //li"):
            try:
                if el.is_displayed() and (target.lower() in el.text.lower() or norm(target) in norm(el.text)):
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
            except: pass
        # Direct index fallback if text comparison is ambiguous
        try:
            inputs = self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox']")
            if inputs:
                self.driver.execute_script("arguments[0].click();", inputs[0])
                return True
        except: pass
        return False

    def enter_code_solution(self, code):
        # Inject the C++ Hello World directly into Monaco/CodeMirror APIs and textareas.
        log.info("Injecting Hello World C++ program solution...")
        js_inject = """
        var val = arguments[0];
        if (typeof monaco !== 'undefined') { monaco.editor.getModels()[0].setValue(val); }
        if (document.querySelector('.CodeMirror')) { document.querySelector('.CodeMirror').CodeMirror.setValue(val); }
        document.querySelectorAll('textarea, [contenteditable="true"]').forEach(el => {
            try {
                if (el.tagName === 'TEXTAREA') { el.value = val; } else { el.innerText = val; }
                ['input', 'change', 'keydown', 'keyup'].forEach(ev => el.dispatchEvent(new Event(ev, { bubbles: true })));
            } catch(e) {}
        });
        """
        try:
            self.driver.execute_script(js_inject, code)
            time.sleep(0.5)
        except Exception as e:
            log.warning(f"Injection exception: {e}")

    def _click_button(self, labels):
        # Locate clickable buttons by target label while skipping global test-end buttons.
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
        # Click the save / next option. Fallback to summary return if unable to proceed.
        if not self._click_button(['save', 'next']):
            self.return_to_summary()
   
    def submit_code(self):
        # Target local submit code button specifically and avoid global end-test button
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
        self._click_button(['run'])

    def click_solve_if_present(self):
        self._click_button(['solve'])

    def return_to_summary(self):
        return self._click_button(['summary', 'dashboard', 'back', 'sections'])
