import time
import re
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

log = get_logger(__name__)

class QuestionPage(BasePage):
    def dismiss_reset_popup(self):
        try:
            alert = self.driver.switch_to.alert
            log.info(f"Dismissed alert: '{alert.text}'")
            alert.accept()
            time.sleep(0.3)
            return True
        except: pass
        try:
            for el in self.driver.find_elements(By.XPATH, "//button | //a | //div[@role='button']"):
                if el.is_displayed() and el.is_enabled():
                    text = (el.text or el.get_attribute("value") or "").lower()
                    if any(x in text for x in ["yes", "confirm", "reset", "ok", "change", "continue"]) and not any(x in text for x in ["test", "assessment", "all", "final", "finish", "end"]):
                        self.driver.execute_script("arguments[0].click();", el)
                        log.info(f"Dismissed reset/confirmation popup: '{text}'")
                        time.sleep(0.3)
                        return True
        except: pass
        return False

    def wait_for_page_load(self):
        for _ in range(2):
            try:
                for btn in self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Return')]"):
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
            except: pass
        self.dismiss_reset_popup()
        self.helpers.wait_for_element((By.XPATH, "//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'editor')]"))
        
    def get_question_type(self):
        if self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox'] | //*[contains(@class, 'option') or contains(@class, 'choice')]"):
            return "MCQ"
        return "CODING"
            
    def get_question_text(self):
        for sel in ["//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'ql-editor')]", "body"]:
            elements = self.driver.find_elements(By.XPATH, sel)
            if elements and elements[0].text.strip():
                return elements[0].text.strip()
        return "Unknown Question"
        
    def get_selected_language(self):
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
        log.info("Ensuring C++ language...")
        current_lang = self.get_selected_language()
        if "c++" in current_lang.lower() or "cpp" in current_lang.lower():
            return True
        for sel in self.driver.find_elements(By.XPATH, "//select"):
            try:
                if sel.is_displayed():
                    from selenium.webdriver.support.ui import Select
                    s = Select(sel)
                    for opt in s.options:
                        if "c++" in opt.text.lower() or "cpp" in opt.text.lower():
                            s.select_by_visible_text(opt.text)
                            time.sleep(0.5)
                            self.dismiss_reset_popup()
                            return True
            except: pass
        for toggle in self.driver.find_elements(By.XPATH, "//button | //div[@role='button'] | //span[contains(@class, 'dropdown') or contains(@class, 'select')]"):
            try:
                if toggle.is_displayed() and any(x in toggle.text.lower() for x in ["c++", "cpp", "select", "lang"]):
                    self.driver.execute_script("arguments[0].click();", toggle)
                    time.sleep(0.5)
                    for item in self.driver.find_elements(By.XPATH, "//li | //a | //div[contains(@class, 'option') or contains(@class, 'item')]"):
                        if item.is_displayed() and any(x in item.text.lower() for x in ["c++", "cpp"]):
                            self.driver.execute_script("arguments[0].click();", item)
                            time.sleep(0.5)
                            self.dismiss_reset_popup()
                            return True
            except: pass
        return False

    def get_example_input_output(self):
        log.info("Parsing example testcases...")
        for pre in self.driver.find_elements(By.XPATH, "//pre | //code"):
            try:
                if pre.is_displayed() and pre.text.strip():
                    text = pre.text.strip()
                    if "input" in text.lower() and "output" in text.lower():
                        match = re.search(r'(?:input|sample input|example input):?\s*\n?(.*?)\s*\n?(?:output|sample output|example output):?\s*\n?(.*)', text, re.IGNORECASE | re.DOTALL)
                        if match:
                            inp = re.sub(r'^(?:input|sample input|example input):?\s*', '', match.group(1).strip(), flags=re.I).strip()
                            out = re.sub(r'^(?:output|sample output|example output):?\s*', '', match.group(2).strip(), flags=re.I).strip()
                            return inp, out
            except: pass
        try:
            match = re.search(r'(?:input|sample input|example input):?\s*\n?(.*?)\n?(?:output|sample output|example output):?\s*\n?(.*?)(?:\n\n|\n[A-Z]|\Z)', self.get_question_text(), re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip(), match.group(2).strip()
        except: pass
        return "", ""

    def enable_custom_input(self):
        for xpath in [
            "//input[@type='checkbox'][contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom') or contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'input')]",
            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom input') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom test')]",
            "//*[self::button or self::a or self::input][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'custom')]"
        ]:
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        if el.tag_name == "input" and el.get_attribute("type") == "checkbox" and el.is_selected():
                            return True
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.3)
                        return True
                except: pass
        return False

    def set_custom_input_value(self, input_text):
        candidates = []
        for ta in self.driver.find_elements(By.XPATH, "//textarea"):
            try:
                if ta.is_displayed():
                    score = sum(5 for attr in ["id", "class", "name", "placeholder"] if "input" in (ta.get_attribute(attr) or "").lower())
                    score += sum(10 for attr in ["id", "class", "name", "placeholder"] if "custom" in (ta.get_attribute(attr) or "").lower())
                    candidates.append((score, ta))
            except: pass
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            target = candidates[0][1]
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
                time.sleep(0.2)
                target.clear()
                target.send_keys(input_text)
                return True
            except:
                try:
                    self.driver.execute_script("arguments[0].value = arguments[1];", target, input_text)
                    return True
                except: pass
        for ce in self.driver.find_elements(By.XPATH, "//*[@contenteditable='true']"):
            try:
                if ce.is_displayed():
                    self.driver.execute_script("arguments[0].innerText = arguments[1];", ce, input_text)
                    return True
            except: pass
        return False
        
    def _find_option_elements(self):
        inputs = self.driver.find_elements(By.XPATH, "//input[@type='radio'] | //input[@type='checkbox']")
        if inputs:
            clickables = []
            for inp in inputs:
                for xpath in ["./following-sibling::label", "./preceding-sibling::label", "..", "."]:
                    try:
                        el = inp.find_element(By.XPATH, xpath)
                        if el and el.is_displayed() and el not in clickables:
                            clickables.append(el)
                            break
                    except: pass
            return clickables
        lis = self.driver.find_elements(By.XPATH, "//li[contains(@class, 'option') or contains(@class, 'choice') or contains(@class, 'radio-label')]")
        if lis: return lis
        return [el for el in self.driver.find_elements(By.XPATH, "//li | //div[contains(@class, 'option') or contains(@class, 'choice') or contains(@class, 'item') or @role='radio']") if el.is_displayed() and el.text.strip() and len(el.text.strip()) < 150]

    def get_mcq_options(self):
        opts = []
        for el in self._find_option_elements():
            try:
                text = el.text.strip() or el.find_element(By.XPATH, "..").text.strip()
                if text and text not in opts: opts.append(text)
            except: pass
        cleaned = []
        for opt in opts:
            cl = re.sub(r'^[A-D]\.\s*|^[a-d]\)\s*', '', opt).strip()
            if cl and cl not in cleaned: cleaned.append(cl)
        return cleaned if len(cleaned) >= 2 else ["A", "B", "C", "D"]
        
    def select_mcq_option(self, target):
        if not target: return False
        elements = self._find_option_elements()
        norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
        target_norm = norm(target)
        
        def click_el(el):
            for xpath in [".", "..", "../label", "./following-sibling::label", "./preceding-sibling::label", "../.."]:
                try:
                    c = el.find_element(By.XPATH, xpath) if xpath != "." else el
                    if c.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", c)
                        self.driver.execute_script("arguments[0].click();", c)
                        time.sleep(0.3)
                        return True
                except: pass
            return False

        for el in elements:
            try:
                if el.is_displayed():
                    text = el.text.strip() or el.find_element(By.XPATH, "..").text.strip()
                    if target.lower() in text.lower() or target_norm in norm(text) or norm(text) in target_norm:
                        if click_el(el): return True
            except: pass
            
        opts = self.get_mcq_options()
        match_idx = next((i for i, opt in enumerate(opts) if target.lower() in opt.lower() or norm(opt) in target_norm or target_norm in norm(opt)), -1)
        if match_idx == -1 and len(target) == 1 and target.upper() in "ABCD":
            match_idx = "ABCD".index(target.upper())
            
        if match_idx != -1 and match_idx < len(elements):
            if click_el(elements[match_idx]): return True
        return click_el(elements[0]) if elements else False

    def enter_code_solution(self, code):
        log.info("Injecting C++ code solution...")
        js_inject = """
        var val = arguments[0];
        try { if (typeof monaco !== 'undefined' && monaco.editor && monaco.editor.getModels && monaco.editor.getModels()[0]) { monaco.editor.getModels()[0].setValue(val); } } catch(e) {}
        try { var cm = document.querySelector('.CodeMirror'); if (cm && cm.CodeMirror) { cm.CodeMirror.setValue(val); } } catch(e) {}
        try { document.querySelectorAll('textarea, [contenteditable="true"]').forEach(el => {
            if (el.tagName === 'TEXTAREA') { el.value = val; } else { el.innerText = val; }
            ['input', 'change', 'keydown', 'keyup'].forEach(ev => el.dispatchEvent(new Event(ev, { bubbles: true })));
        }); } catch(e) {}
        """
        try:
            self.driver.execute_script(js_inject, code)
            time.sleep(0.5)
        except Exception as e:
            log.warning(f"Injection failed: {e}")

    def _click_button(self, labels):
        conditions = " or ".join([f"contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{l.lower()}')" for l in labels])
        val_conds = " or ".join([f"contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{l.lower()}')" for l in labels])
        for el in self.driver.find_elements(By.XPATH, f"//button[{conditions}] | //a[{conditions}] | //input[{val_conds}]"):
            try:
                if el.is_displayed() and el.is_enabled():
                    text = (el.text or el.get_attribute("value") or "").lower()
                    if not any(x in text for x in ["test", "assessment", "all", "final", "finish", "end"]):
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                        self.driver.execute_script("arguments[0].click();", el)
                        return True
            except: pass
        return False

    def is_next_button_disabled(self):
        try:
            for el in self.driver.find_elements(By.XPATH, "//button | //a"):
                if el.is_displayed() and "next" in el.text.lower():
                    classes = (el.get_attribute("class") or "").lower()
                    if el.get_attribute("disabled") == "true" or el.get_attribute("aria-disabled") == "true" or "disabled" in classes or not el.is_enabled():
                        return True
        except: pass
        return False

    def click_save_and_next(self): return self._click_button(['save', 'next', 'submit'])
    def submit_mcq_answer(self): return self._click_button(["submit", "save", "lock"])
    def submit_code(self): return self._click_button(['submit'])
    def run_code(self): return self._click_button(['run'])
    def click_solve_if_present(self): self._click_button(['solve'])

    def get_run_outputs(self):
        def is_prob_panel(el):
            try:
                curr = el
                for _ in range(5):
                    if not curr: break
                    cls = (curr.get_attribute("class") or "").lower()
                    id_val = (curr.get_attribute("id") or "").lower()
                    if any(x in cls or x in id_val for x in ["problem", "desc", "instruction", "statement", "left-pane", "col-md-6"]):
                        return True
                    curr = curr.find_element(By.XPATH, "./..")
            except: pass
            return False

        def find_output(keywords):
            conds = " and ".join([f"contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{k}')" for k in keywords])
            for el in self.driver.find_elements(By.XPATH, f"//*[starts-with(name(), 'h') or name()='div' or name()='span' or name()='p' or name()='label' or name()='strong'][{conds}]"):
                try:
                    if el.is_displayed() and not is_prob_panel(el):
                        parent = el.find_element(By.XPATH, "./..")
                        for sub in parent.find_elements(By.XPATH, ".//pre | .//code | .//textarea | .//div[contains(@class, 'output') or contains(@class, 'console')]"):
                            if sub.is_displayed() and sub != el:
                                val = sub.text.strip() or sub.get_attribute("value") or ""
                                if val: return val.strip()
                        sib = el.find_element(By.XPATH, "./following-sibling::*[1]")
                        val = sib.text.strip() or sib.get_attribute("value") or ""
                        if val: return val.strip()
                except: pass
            return ""

        expected = find_output(["expected"])
        actual = find_output(["your", "output"]) or find_output(["actual", "output"])
        if not actual:
            for el in self.driver.find_elements(By.XPATH, "//*[starts-with(name(), 'h') or name()='div' or name()='span' or name()='p' or name()='label'][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'output') and not(contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'expected'))]"):
                try:
                    if el.is_displayed() and not is_prob_panel(el):
                        for sub in el.find_element(By.XPATH, "./..").find_elements(By.XPATH, ".//pre | .//code | .//textarea"):
                            if sub.is_displayed() and sub != el:
                                val = sub.text.strip() or sub.get_attribute("value") or ""
                                if val: return expected, val.strip()
                except: pass
        return expected, actual

    def get_console_errors(self):
        found = []
        for xpath in ["//*[contains(@class, 'error') or contains(@id, 'error') or contains(@class, 'compile') or contains(@class, 'terminal')]", "//pre[contains(text(), 'Error') or contains(text(), 'error') or contains(text(), 'Exception')]"]:
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed() and el.text.strip() and len(el.text.strip()) > 10 and not any(f in el.text.lower() for f in ["loading", "processing"]):
                        if el.text.strip() not in found: found.append(el.text.strip())
                except: pass
        return "\n".join(found)

    def get_code_result(self, old_actual=None):
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        time.sleep(1.5)
        try:
            WebDriverWait(self.driver, 20).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(normalize-space(.), 'Processing...')]")))
            time.sleep(1)
        except: pass
        
        start = time.time()
        while time.time() - start < 8:
            expected, actual = self.get_run_outputs()
            if actual and actual.strip() and (not old_actual or actual.strip() != old_actual.strip()):
                break
            time.sleep(0.5)

        err_flags = ["wrong answer", "time limit exceeded", "tle", "runtime error", "rte", "compilation error", "failed"]
        try:
            conds = " or ".join([f"contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{f}')" for f in err_flags])
            found_errors = []
            for el in self.driver.find_elements(By.XPATH, f"//*[self::div or self::span or self::p or self::strong][{conds}]"):
                if el.is_displayed() and len(el.text.strip()) < 150 and el.text.strip() not in found_errors and len(el.text.strip()) > 2:
                    found_errors.append(el.text.strip())
            if found_errors:
                return False, "\n".join(found_errors)
        except: pass

        try:
            expected, actual = self.get_run_outputs()
            if expected or actual:
                exp_ints = re.findall(r'-?\d+', expected)
                act_ints = re.findall(r'-?\d+', actual)
                if exp_ints and act_ints and exp_ints == act_ints:
                    return True, ""
                return False, f"Output Mismatch!\nExpected Output:\n{expected}\n\nYour Output:\n{actual}"
        except: pass
        
        console_err = self.get_console_errors()
        if console_err: return False, console_err
        return False, "Validation output mismatch or execution failure."

    def return_to_summary(self): return self._click_button(['summary', 'dashboard', 'back', 'sections'])

    def is_sidebar_open(self):
        try:
            for xpath in ["//*[contains(text(), 'Overall Summary')]", "//*[contains(text(), 'Summary')]", "//*[contains(text(), 'QUESTIONS')]"]:
                for el in self.driver.find_elements(By.XPATH, xpath):
                    if el.is_displayed() and el.rect['x'] > (self.driver.execute_script("return window.innerWidth;") * 0.5):
                        return True
        except: pass
        return False

    def open_sidebar(self): return True if self.is_sidebar_open() else self._click_sidebar_arrow()
    def close_sidebar(self): return True if not self.is_sidebar_open() else self._click_sidebar_arrow()

    def _click_sidebar_arrow(self):
        w = self.driver.execute_script("return window.innerWidth;")
        for el in self.driver.find_elements(By.XPATH, "//button | //div[@role='button'] | //span[@role='button'] | //a[contains(@class, 'toggle') or contains(@class, 'sidebar') or contains(@class, 'arrow')]"):
            try:
                if el.is_displayed() and el.is_enabled() and el.rect['x'] > (w * 0.5) and el.rect['width'] < 80:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", el)
                    time.sleep(0.8)
                    return True
            except: pass
        return False

    def click_overall_summary(self):
        for xpath in ["//*[contains(text(), 'Overall Summary')]", "//*[contains(text(), 'Summary')]"]:
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(1.0)
                        return True
                except: pass
        return False

    def get_sidebar_questions(self):
        log.info("Scanning sidebar...")
        sidebar_el = None
        for sel in ["//*[contains(@class, 'sidebar') or contains(@class, 'drawer')]", "//div[contains(@class, 'right')]"]:
            for el in self.driver.find_elements(By.XPATH, sel):
                try:
                    if el.is_displayed() and el.rect['x'] > (self.driver.execute_script("return window.innerWidth;") * 0.5):
                        sidebar_el = el
                        break
                except: pass
            if sidebar_el: break
            
        container = sidebar_el if sidebar_el else self.driver
        questions = []
        items = container.find_elements(By.XPATH, ".//a | .//button | .//div[@role='button'] | .//*[contains(@class, 'question-item') or contains(@class, 'Q')]")
        
        for el in items:
            try:
                if el.is_displayed() and el.text.strip():
                    text = " ".join([line.strip() for line in el.text.splitlines() if line.strip()])
                    if len(text) < 3 or any(u in text.lower() for u in ["summary", "next", "previous", "instructions", "submit"]):
                        continue
                    match = re.search(r'\b(?:Q|Question\s*)?(\d+)\b', text, re.IGNORECASE)
                    if not match: continue
                    q_idx = int(match.group(1))
                    if any(q['index'] == q_idx for q in questions): continue
                    
                    is_solved = False
                    badge_els = el.find_elements(By.XPATH, ".//*[contains(@class, 'badge') or contains(@class, 'status') or contains(@class, 'circle')]") or [el]
                    for badge in badge_els:
                        bg = badge.value_of_css_property("background-color") or ""
                        if "rgb" in bg:
                            nums = [int(s) for s in re.findall(r'\d+', bg)]
                            if len(nums) >= 3 and nums[1] > nums[0] * 1.4 and nums[1] > 110:
                                is_solved = True
                                break
                        classes = (badge.get_attribute("class") or "").lower()
                        if any(x in classes for x in ["success", "passed", "solved", "q-solved"]) and not any(x in classes for x in ["unsolved", "failed"]):
                            is_solved = True
                            break
                    
                    html = el.get_attribute("outerHTML") or ""
                    if not is_solved and any(m in html.lower() for m in ["status-success", "q-solved", "badge-success"]):
                        is_solved = True
                        
                    q_type = "MCQ" if "mcq" in text.lower() or "mcq" in html.lower() else "CODING"
                    questions.append({'index': q_idx, 'name': text, 'type': q_type, 'is_solved': is_solved, 'element': el})
            except: pass
        questions.sort(key=lambda q: q['index'])
        return questions

    def switch_sidebar_section(self, section_name, section_idx=None):
        self.open_sidebar()
        time.sleep(0.3)
        clean_name = section_name.replace("Section:", "").strip().lower()
        
        for q in self.get_sidebar_questions():
            if q['element'].is_displayed():
                q_type = q['type']
                if ("mcq" in clean_name and q_type == "MCQ") or ("mcq" not in clean_name and q_type == "CODING"):
                    return True
                    
        for kw in [clean_name, "mcq" if "mcq" in clean_name else "coding", "multiple choice" if "mcq" in clean_name else "questions"]:
            for el in self.driver.find_elements(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]"):
                try:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", el)
                        time.sleep(0.5)
                        return True
                except: pass
        if section_idx is not None:
            headers = [h for h in self.driver.find_elements(By.XPATH, "//button | //h3 | //h4 | //div[contains(@class, 'header') or contains(@class, 'accordion')]") if h.is_displayed() and h.text.strip() and not any(x in h.text.lower() for x in ["q1", "question", "summary", "submit", "run"])]
            if section_idx - 1 < len(headers):
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", headers[section_idx - 1])
                    time.sleep(0.5)
                    return True
                except: pass
        return False

    def click_sidebar_question(self, q_idx):
        self.open_sidebar()
        for q in self.get_sidebar_questions():
            if q['index'] == q_idx:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", q['element'])
                    time.sleep(1.0)
                    self.dismiss_reset_popup()
                    return True
                except: pass
        return False
