import os
import json
import time
import urllib.request
import urllib.parse
import re
from difflib import SequenceMatcher
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from config import settings
from utils.logger import get_logger

try:
    import tkinter as tk
except ImportError:
    tk = None

log = get_logger(__name__)

class GeminiSolver:
    def __init__(self, driver=None):
        self.driver = driver
        self.duck_window = None

    def solve_via_duck_ai(self, prompt, screenshot_path=None, is_coding=False):
        if not self.driver:
            return None

        try:
            orig_handle = self.driver.current_window_handle
        except Exception as e:
            log.error(f"Browser session is dead: {e}")
            return None

        # Resolve or reuse Duck.ai window handle
        duck_handle = None
        if self.duck_window and self.duck_window in self.driver.window_handles:
            duck_handle = self.duck_window
        else:
            self.duck_window = None
            for h in self.driver.window_handles:
                if h != orig_handle:
                    try:
                        self.driver.switch_to.window(h)
                        if "duck.ai" in self.driver.current_url or "duckduckgo.com/chat" in self.driver.current_url:
                            duck_handle = h
                            self.duck_window = h
                            break
                    except: pass
            try: self.driver.switch_to.window(orig_handle)
            except: pass

        if not duck_handle:
            log.info("Opening background Duck.ai tab...")
            self.driver.execute_script("window.open('about:blank', '_blank');")
            time.sleep(0.5)
            for h in self.driver.window_handles:
                if h != orig_handle and h != self.duck_window:
                    duck_handle = h
                    self.duck_window = h
                    break

        if not duck_handle:
            log.error("Could not resolve Duck.ai tab.")
            return None

        self.driver.switch_to.window(duck_handle)
        time.sleep(0.3)

        # Load page or reset chat state
        if "duck.ai" not in self.driver.current_url and "duckduckgo.com/chat" not in self.driver.current_url:
            self.driver.get("https://duck.ai/")
            for _ in range(20):
                time.sleep(0.5)
                if self.driver.find_elements(By.TAG_NAME, "textarea"):
                    break
        else:
            try:
                for btn in self.driver.find_elements(By.XPATH, "//button[contains(text(),'New Chat') or contains(text(),'New chat') or contains(normalize-space(.),'New Chat')]"):
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
                        break
            except: pass

        # Handle onboarding, terms, and initial popups
        for xpath in [
            "//button[contains(normalize-space(.),'Agree') or contains(normalize-space(.),'Continue') or contains(normalize-space(.),'Get Started')]",
            "//button[contains(normalize-space(.),'Chat')]"
        ]:
            try:
                for btn in self.driver.find_elements(By.XPATH, xpath):
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
            except: pass

        try:
            if screenshot_path and os.path.exists(screenshot_path):
                self.driver.find_element(By.XPATH, "//input[@type='file']").send_keys(screenshot_path)
                time.sleep(1.5)

            ta = None
            for _ in range(16):
                tas = self.driver.find_elements(By.TAG_NAME, "textarea")
                if tas:
                    ta = tas[0]
                    break
                time.sleep(0.5)

            if not ta:
                log.error("Duck.ai textarea missing.")
                self._safe_switch(orig_handle)
                return None

            self.driver.execute_script("arguments[0].focus(); arguments[0].click();", ta)
            ta.clear()
            time.sleep(0.2)

            # Paste prompt via OS clipboard or DOM fallback
            pasted = False
            if tk:
                try:
                    root = tk.Tk()
                    root.withdraw()
                    root.clipboard_clear()
                    root.clipboard_append(prompt)
                    root.update()
                    root.destroy()
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    pasted = True
                    time.sleep(0.3)
                except: pass

            if not pasted:
                self.driver.execute_script("""
                    var ta = arguments[0]; ta.value = arguments[1];
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                """, ta, prompt)
                time.sleep(0.3)

            # Submit prompt
            submitted = False
            for xpath in ["//button[@aria-label='Send']", "//button[@type='submit']"]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    self.driver.execute_script("arguments[0].click();", btn)
                    submitted = True
                    break
                except: pass

            if not submitted:
                try:
                    ta.send_keys(Keys.RETURN)
                    submitted = True
                except: pass

            if submitted:
                log.info("Prompt sent successfully!")
            else:
                log.error("Could not send prompt.")
                self._safe_switch(orig_handle)
                return None

        except Exception as e:
            log.error(f"Failed to submit to Duck.ai: {e}")
            self._safe_switch(orig_handle)
            return None

        # Wait for response to begin
        log.info("Waiting for response to start...")
        started = False
        wait_cycles = 60 if screenshot_path else 30
        for _ in range(wait_cycles):
            time.sleep(0.5)
            try:
                msg_el = self.driver.find_elements(By.XPATH, "//*[contains(@id, 'assistant-message')]")
                if msg_el:
                    txt = msg_el[-1].text.strip()
                    if txt and not any(p in txt.lower() for p in ["generating response", "thinking"]):
                        started = True
                        break
            except: pass

        if not started:
            log.warning("Response never started.")
            self._safe_switch(orig_handle)
            return None

        # Wait for response to finish (text stabilizes)
        log.info("Waiting for response to finish...")
        last_text, stable = "", 0
        max_wait = 120 if is_coding else 60
        for _ in range(max_wait):
            time.sleep(0.5)
            txt = ""
            try:
                msg_el = self.driver.find_elements(By.XPATH, "//*[contains(@id, 'assistant-message')]")
                if msg_el:
                    txt = msg_el[-1].text.strip()
            except: pass

            if any(p in txt.lower() for p in ["generating response", "thinking"]):
                stable = 0
                continue

            if txt and txt == last_text:
                stable += 1
                if stable >= (6 if is_coding else 3):
                    break
            else:
                if txt:
                    last_text, stable = txt, 0

        log.info(f"Response complete: {len(last_text)} chars")

        # Copy clean block for coding
        if is_coding and last_text:
            try:
                time.sleep(0.5)
                for loc in [
                    "//pre/parent::div//button[contains(@title,'Copy') or contains(@class,'copy') or .//svg]",
                    "//button[contains(@class,'copy') or contains(@title,'Copy') or @aria-label='Copy']",
                ]:
                    btns = self.driver.find_elements(By.XPATH, loc)
                    if btns:
                        self.driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", btns[-1])
                        time.sleep(0.8)
                        if tk:
                            try:
                                root = tk.Tk()
                                root.withdraw()
                                code = root.clipboard_get()
                                root.destroy()
                                if code and len(code.strip()) > 50:
                                    last_text = code
                            except: pass
                        break
            except: pass

        self._safe_switch(orig_handle)

        if not last_text:
            return None
        if "please try again" in last_text.lower() or "attempts left" in last_text.lower():
            log.warning("Duck.ai rate limited.")
            return None
        return last_text

    def _safe_switch(self, handle):
        try:
            if handle in self.driver.window_handles:
                self.driver.switch_to.window(handle)
                time.sleep(0.3)
            else:
                handles = self.driver.window_handles
                if handles:
                    self.driver.switch_to.window(handles[0])
                    log.warning("Original tab lost, switched to fallback tab.")
        except Exception as e:
            log.error(f"Failed to switch back safely: {e}")

    def _gen_content(self, prompt, req_type="coding", screenshot_path=None):
        if self.driver:
            res = self.solve_via_duck_ai(prompt, screenshot_path, is_coding=(req_type == "coding"))
            if res:
                return res.strip()

        # IPC Fallback
        ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        req_path = os.path.join(ws, "pending_request.json")
        res_path = os.path.join(ws, "resolved_response.json")
        try:
            with open(req_path, "w") as f:
                json.dump({"type": req_type, "prompt": prompt}, f)
        except:
            return None

        log.info("Checking for resolved fallback responses...")
        for _ in range(15):
            if os.path.exists(res_path):
                try:
                    with open(res_path, "r") as f:
                        data = json.load(f)
                    for p in [req_path, res_path]:
                        if os.path.exists(p):
                            os.remove(p)
                    return data.get("response", "").strip()
                except: pass
            time.sleep(1)

        for p in [req_path, res_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        return None

    def _search(self, query):
        try:
            url = "https://html.duckduckgo.com/html/"
            data = urllib.parse.urlencode({"q": query}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=5) as r:
                html = r.read().decode('utf-8')
            snippets = [re.sub(r'<[^>]+>', '', s).replace('\n', ' ').strip() for s in re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)[:4]]
            return "\n".join(f"- {s}" for s in snippets if s)
        except:
            return ""

    def solve_mcq(self, question, options, screenshot_path=None):
        ctx = self._search(question[:200])
        prompt = f"Question: {question}\nOptions:\n" + "\n".join(f"{i+1}. {o}" for i, o in enumerate(options))
        prompt += f"\nContext:\n{ctx}\nStrict format:\nREASONING: <text>\nANSWER: <exact string>"

        if screenshot_path:
            prompt = "I have uploaded a screenshot of the question and options. Solve this question and identify the correct option. Your answer MUST EXACTLY match one of the options shown.\n" + prompt

        resp = self._gen_content(prompt, "mcq", screenshot_path)
        if not resp:
            log.warning("Running offline keyword-matching heuristic...")
            if ctx and options:
                best_opt, best_score = None, -1
                for opt in options:
                    clean_opt = re.sub(r'^\s*[a-d1-4][\.)\s]+', '', opt, flags=re.I).strip()
                    exact = ctx.lower().count(clean_opt.lower())
                    words = [w for w in re.split(r'\W+', clean_opt.lower()) if len(w) > 2]
                    word_score = sum(ctx.lower().count(w) for w in words) if words else 0
                    score = exact * 5 + word_score
                    if score > best_score:
                        best_score, best_opt = score, opt

                if best_opt and best_score > 0:
                    return "Offline heuristic match", best_opt

            return "Fallback (first option)", options[0] if options else None

        clean = resp.replace("**", "").replace("`", "").strip()
        r_match = re.search(r'reasoning\s*:\s*(.*?)(?=answer\s*:|$)', clean, re.I | re.S)
        a_match = re.search(r'answer\s*:\s*(.*)', clean, re.I | re.S)

        reasoning = r_match.group(1).strip() if r_match else "None"
        ans = a_match.group(1).strip() if a_match else clean.split('\n')[-1]

        if ans and options:
            best = max(options, key=lambda o: max(
                1.0 if o.lower() == ans.lower() or o.lower() in ans.lower() else 0.0,
                SequenceMatcher(None, o.lower(), ans.lower()).ratio()
            ), default=None)
            return reasoning, best
        return reasoning, None

    def solve_coding(self, question, lang="C++", screenshot_path=None):
        rules = "Write ONLY code. No markdown or explanation. Write a complete program."
        prompt = f"Write executable {lang} code.\nProblem: {question}\nRules: {rules}"
        if screenshot_path:
            prompt = f"I have uploaded a screenshot of the coding task. Solve the coding task and write executable {lang} code.\nRules: {rules}"

        code = self._gen_content(prompt, "coding", screenshot_path)
        if not code:
            return None
        code = re.sub(r'^```[a-zA-Z\+\#]*\n?', '', code, flags=re.I).strip()
        return re.sub(r'```$', '', code).strip()
