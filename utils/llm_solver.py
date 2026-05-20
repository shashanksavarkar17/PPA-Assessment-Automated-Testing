import os, json, time, urllib.request, urllib.parse, re
from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

# This class handles prompt generation, browser-based Duck.ai automated solving, and offline fallbacks.
class GeminiSolver:
    def __init__(self, driver=None):
        self.driver = driver
        self.duck_window = None

    def solve_via_duck_ai(self, prompt, screenshot_path=None, is_coding=False):
        if not self.driver: return None
        from selenium.webdriver.common.by import By
        
        orig_handle = self.driver.current_window_handle
        duck_handle = None
        
        # Check if we already have a Duck.ai window open in the background.
        if getattr(self, 'duck_window', None) and self.duck_window in self.driver.window_handles:
            duck_handle = self.duck_window
        else:
            for h in self.driver.window_handles:
                if h != orig_handle:
                    try:
                        self.driver.switch_to.window(h)
                        if "duck.ai" in self.driver.current_url or "duckduckgo.com/chat" in self.driver.current_url:
                            duck_handle = h
                            self.duck_window = h
                            break
                    except: pass
            self.driver.switch_to.window(orig_handle)
                
        # If we couldn't find an open Duck.ai tab, let's open one!
        if not duck_handle:
            log.info("Spawning a brand-new tab to automate Duck.ai free solver...")
            self.driver.execute_script("window.open('https://duck.ai/', '_blank');")
            time.sleep(1)
            for h in self.driver.window_handles:
                if h != orig_handle:
                    duck_handle = h
                    self.duck_window = h
                    break
                    
        if not duck_handle:
            log.error("Could not find or create a Duck.ai tab.")
            return None
            
        self.driver.switch_to.window(duck_handle)
        time.sleep(0.5)
        
        # Navigate or click "New Chat" button to avoid any old session crosstalk.
        if "duckduckgo.com/chat" not in self.driver.current_url and "duck.ai" not in self.driver.current_url:
            log.info("Directly loading https://duck.ai/...")
            self.driver.get("https://duck.ai/")
            time.sleep(2)
        else:
            try:
                new_chat_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'New Chat') or contains(text(), 'New chat') or normalize-space(.)='New Chat']")
                if new_chat_btns:
                    for btn in new_chat_btns:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            log.info("Resetting solver context via 'New Chat'!")
                            time.sleep(1)
                            break
            except Exception as e: log.warning(f"Failed to reset chat context: {e}")
            
        # Click past terms and agreements popup if it appears.
        try:
            btn = self.driver.find_elements(By.XPATH, "//button[contains(normalize-space(.), 'Agree') or contains(normalize-space(.), 'Continue')]")
            if btn and btn[0].is_displayed():
                self.driver.execute_script("arguments[0].click();", btn[0])
                time.sleep(1)
        except: pass
        
        try:
            # Upload screenshot of the question if it's available.
            if screenshot_path and os.path.exists(screenshot_path):
                try:
                    self.driver.find_element(By.XPATH, "//input[@type='file']").send_keys(screenshot_path)
                    log.info("Uploaded question screenshot successfully!")
                    time.sleep(1.5)
                except Exception as e: log.warning(f"Screenshot upload failed: {e}")

            # Focus the chat textarea.
            ta = self.driver.find_element(By.TAG_NAME, "textarea")
            self.driver.execute_script("arguments[0].focus(); arguments[0].click();", ta)
            ta.clear()
            time.sleep(0.2)
            
            # Copy prompt and instantly paste it to avoid long keyboard typing lags.
            import tkinter as tk
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.keys import Keys
            
            pasted_via_clipboard = False
            try:
                root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(prompt); root.update(); root.destroy()
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                pasted_via_clipboard = True
                time.sleep(0.3)
            except Exception as clipboard_err:
                log.warning(f"Clipboard paste failed: {clipboard_err}. Falling back to React input dispatcher...")
                
            if not pasted_via_clipboard:
                self.driver.execute_script("""
                    var ta = arguments[0]; ta.value = arguments[1];
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                """, ta, prompt)
                time.sleep(0.3)
            
            # Submit prompt!
            self.driver.execute_script("arguments[0].click();", self.driver.find_element(By.XPATH, "//button[@type='submit']"))
            log.info("Prompt sent successfully!")
        except Exception as e:
            log.error(f"Failed to submit prompt to Duck.ai: {e}")
            self.driver.switch_to.window(orig_handle)
            return None
            
        # Wait until the response stream actually begins.
        log.info("Waiting for solver to begin responding...")
        started = False
        for _ in range(60 if screenshot_path else 30):
            time.sleep(0.5)
            try:
                mds = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'markdown') or contains(@class, 'message-content')]")
                if not mds: mds = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'message') and not(contains(@class, 'user'))]")
                if mds and mds[-1].text.strip():
                    started = True
                    break
            except: pass
            
        if not started: log.warning("Response took too long to start.")

        # Wait until the streaming response stabilizes and completes.
        log.info("Waiting for solver to finish streaming...")
        last_text, stable_count = "", 0
        for _ in range(60 if is_coding else 40):
            time.sleep(0.5)
            current_text = ""
            try:
                mds = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'markdown') or contains(@class, 'message-content')]")
                if not mds: mds = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'message') and not(contains(@class, 'user'))]")
                if mds: current_text = mds[-1].text.strip()
            except: pass
            
            if current_text and current_text == last_text:
                stable_count += 1
                if stable_count >= (4 if is_coding else 2): break
            else:
                if current_text: last_text, stable_count = current_text, 0
                    
        log.info(f"Response streaming finished: {len(last_text)} chars")
        
        # If it is a coding task, click the copy code block button to retrieve solution cleanly.
        if is_coding:
            try:
                time.sleep(1)
                copy_buttons = []
                for loc in [
                    "//pre/parent::div//button[contains(@title, 'Copy') or contains(text(), 'Copy') or contains(@class, 'copy') or .//svg]",
                    "//pre/parent::div//button",
                    "//button[contains(@class, 'copy') or contains(@title, 'Copy') or @aria-label='Copy']"
                ]:
                    try:
                        btns = self.driver.find_elements(By.XPATH, loc)
                        if btns: copy_buttons = btns; break
                    except: pass
                
                if copy_buttons:
                    self.driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", copy_buttons[-1])
                    time.sleep(1)
                    
                    import tkinter as tk
                    root = tk.Tk(); root.withdraw(); copied_code = root.clipboard_get(); root.destroy()
                    if copied_code and len(copied_code.strip()) > 50:
                        log.info(f"Successfully fetched code via clipboard copy button ({len(copied_code)} chars).")
                        last_text = copied_code
            except Exception as e: log.warning(f"Could not click block copy button: {e}")

        # Always switch back to the assessment window when done!
        self.driver.switch_to.window(orig_handle)
        time.sleep(0.5)
        
        if "please try again" in last_text.lower() or "attempts left" in last_text.lower():
            log.warning("Duck.ai has rate limited us.")
            return None
        return last_text

    def _gen_content(self, prompt, req_type="coding", screenshot_path=None):
        # First, attempt Duck.ai free solver since it handles screenshots perfectly!
        if self.driver:
            res = self.solve_via_duck_ai(prompt, screenshot_path, is_coding=(req_type == "coding"))
            if res: return res.strip()
                
        # Inter-process communication fallback check for dynamic local runner connections.
        ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        req_path, res_path = os.path.join(ws, "pending_request.json"), os.path.join(ws, "resolved_response.json")
        try:
            with open(req_path, "w") as f: json.dump({"type": req_type, "prompt": prompt}, f)
        except: return None

        log.info("Checking for resolved fallback responses...")
        for _ in range(15):
            if os.path.exists(res_path):
                try:
                    with open(res_path, "r") as f: data = json.load(f)
                    for path in [req_path, res_path]:
                        if os.path.exists(path): os.remove(path)
                    return data.get("response", "").strip()
                except: pass
            time.sleep(1)
        
        # Clean up files if we timeout.
        for path in [req_path, res_path]:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        return None

    def _search(self, query):
        # A super clean, offline fallback search using duckduckgo HTML version without dependencies.
        try:
            url = "https://html.duckduckgo.com/html/"
            data = urllib.parse.urlencode({"q": query}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=5) as r: html = r.read().decode('utf-8')
            snippets = [re.sub(r'<[^>]+>', '', s).replace('\n', ' ').strip() for s in re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)[:4]]
            return "\n".join(f"- {s}" for s in snippets if s)
        except: return ""

    def solve_mcq(self, question, options, screenshot_path=None):
        ctx = self._search(question[:200])
        prompt = f"Question: {question}\nOptions:\n" + "\n".join(f"{i+1}. {o}" for i, o in enumerate(options))
        prompt += f"\nContext:\n{ctx}\nStrict format:\nREASONING: <text>\nANSWER: <exact string>"
        
        if screenshot_path:
            prompt = "I have uploaded a screenshot of the question and options. Solve this question and identify the correct option. Your answer MUST EXACTLY match one of the options shown.\n" + prompt
            
        resp = self._gen_content(prompt, "mcq", screenshot_path)
        if not resp:
            # Fallback heuristic option matcher if offline or rate limited.
            log.warning("Solver failed. Running offline keyword-matching heuristic...")
            if ctx and options:
                best_opt, best_score = None, -1
                for opt in options:
                    clean_opt = re.sub(r'^\s*[a-d1-4][\.\)\s]+', '', opt, flags=re.I).strip()
                    exact_matches = ctx.lower().count(clean_opt.lower())
                    words = [w for w in re.split(r'\W+', clean_opt.lower()) if len(w) > 2]
                    word_matches = sum(ctx.lower().count(w) for w in words) if words else 0
                    
                    total_score = exact_matches * 5 + word_matches
                    log.info(f"Heuristic score for '{opt}': {total_score}")
                    if total_score > best_score: best_score, best_opt = total_score, opt
                
                if best_opt and best_score > 0:
                    log.info(f"Heuristic matched option: '{best_opt}'")
                    return "Answer resolved offline via DuckDuckGo heuristic matching.", best_opt
            
            # Ultimate default fallback is always the very first option.
            ultimate = options[0] if options else None
            log.warning(f"Ultimate first-option fallback selection: '{ultimate}'")
            return "Ultimate fallback (first option)", ultimate
        
        clean = resp.replace("**", "").replace("`", "").strip()
        r_match = re.search(r'reasoning\s*:\s*(.*?)(?=answer\s*:|$)', clean, re.I | re.S)
        a_match = re.search(r'answer\s*:\s*(.*)', clean, re.I | re.S)
        
        reasoning = r_match.group(1).strip() if r_match else "None"
        ans = a_match.group(1).strip() if a_match else clean.split('\n')[-1]
        
        if ans:
            # Use SequenceMatcher to find the closest string match out of available options.
            from difflib import SequenceMatcher as SM
            best = max(options, key=lambda o: max(
                1.0 if o.lower() == ans.lower() or o.lower() in ans.lower() else 0.0,
                SM(None, o.lower(), ans.lower()).ratio()
            ), default=None)
            return reasoning, best
        return reasoning, None

    def solve_coding(self, question, lang="C++", screenshot_path=None):
        rules = "Write ONLY code. No markdown or explanation. Write a complete program."
        prompt = f"Write executable {lang} code.\nProblem: {question}\nRules: {rules}"
        if screenshot_path:
            prompt = f"I have uploaded a screenshot of the coding task. Solve the coding task and write executable {lang} code.\nRules: {rules}"
            
        code = self._gen_content(prompt, "coding", screenshot_path)
        if not code: return None
        # Strip out code block wrappers (e.g. ```cpp ... ```) so we have a completely clean program.
        code = re.sub(r'^```[a-zA-Z\+\#]*\n?', '', code, flags=re.I).strip()
        return re.sub(r'```$', '', code).strip()
