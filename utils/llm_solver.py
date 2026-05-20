import os, json, time, urllib.request, urllib.parse, re
from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

class GeminiSolver:
    def __init__(self, driver=None):
        self.driver = driver
        self.duck_window = None

    def solve_via_duck_ai(self, prompt, screenshot_path=None, is_coding=False):
        if not self.driver:
            return None
        from selenium.webdriver.common.by import By
        
        orig_handle = self.driver.current_window_handle
        
        # Open or switch to Duck.ai tab
        duck_handle = None
        # We search for any handle that is NOT the current assessment page. Since Yopmail also stays open, 
        # we check the URL of handles or uniquely store the Duck.ai handle on self.duck_handle.
        if getattr(self, 'duck_window', None) and self.duck_window in self.driver.window_handles:
            duck_handle = self.duck_window
        else:
            for h in self.driver.window_handles:
                if h != orig_handle:
                    # Switch to check URL
                    try:
                        self.driver.switch_to.window(h)
                        if "duck.ai" in self.driver.current_url or "duckduckgo.com/chat" in self.driver.current_url:
                            duck_handle = h
                            self.duck_window = h
                            break
                    except: pass
            self.driver.switch_to.window(orig_handle)
                
        if not duck_handle:
            log.info("Opening new tab for Duck.ai chat...")
            self.driver.execute_script("window.open('https://duck.ai/', '_blank');")
            time.sleep(1)
            for h in self.driver.window_handles:
                if h != orig_handle:
                    duck_handle = h
                    self.duck_window = h
                    break
                    
        if not duck_handle:
            log.error("Could not create/find Duck.ai tab")
            return None
            
        self.driver.switch_to.window(duck_handle)
        time.sleep(0.5)
        
        if "duckduckgo.com/chat" not in self.driver.current_url and "duck.ai" not in self.driver.current_url:
            log.info("Navigating to https://duck.ai/...")
            self.driver.get("https://duck.ai/")
            time.sleep(2)
        else:
            # Click "New Chat" to start a completely fresh context and avoid any code crosstalk!
            try:
                new_chat_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'New Chat') or contains(text(), 'New chat') or normalize-space(.)='New Chat']")
                if new_chat_btns:
                    for btn in new_chat_btns:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            log.info("Started a fresh 'New Chat' session on Duck.ai to prevent crosstalk!")
                            time.sleep(1)
                            break
            except Exception as e:
                log.warning(f"Could not click 'New Chat' button: {e}")
            
        # Agree and Continue
        try:
            btn = self.driver.find_elements(By.XPATH, "//button[contains(normalize-space(.), 'Agree') or contains(normalize-space(.), 'Continue')]")
            if btn and btn[0].is_displayed():
                self.driver.execute_script("arguments[0].click();", btn[0])
                time.sleep(1)
        except: pass
        
        # Clear textarea and submit prompt
        try:
            if screenshot_path and os.path.exists(screenshot_path):
                try:
                    file_input = self.driver.find_element(By.XPATH, "//input[@type='file']")
                    file_input.send_keys(screenshot_path)
                    log.info(f"Uploaded screenshot to Duck.ai: {screenshot_path}")
                    time.sleep(1.5)
                except Exception as e:
                    log.warning(f"Could not upload screenshot to Duck.ai: {e}")

            ta = self.driver.find_element(By.TAG_NAME, "textarea")
            self.driver.execute_script("arguments[0].focus(); arguments[0].click();", ta)
            ta.clear()
            time.sleep(0.2)
            
            # Copy to clipboard and paste using CTRL+V to instantly and fully enter the question prompt
            import tkinter as tk
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.keys import Keys
            
            pasted_via_clipboard = False
            try:
                root = tk.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(prompt)
                root.update()
                root.destroy()
                
                # Perform paste operation via action chains
                actions = ActionChains(self.driver)
                actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                log.info("Instantly pasted full prompt into textarea via system clipboard!")
                pasted_via_clipboard = True
                time.sleep(0.3)
            except Exception as clipboard_err:
                log.warning(f"Clipboard paste failed, falling back to event-driven JS value injection: {clipboard_err}")
                
            if not pasted_via_clipboard:
                # Fallback event injection for JS frameworks
                self.driver.execute_script("""
                    var ta = arguments[0];
                    ta.value = arguments[1];
                    var event = new Event('input', { bubbles: true });
                    ta.dispatchEvent(event);
                """, ta, prompt)
                log.info("Injected prompt into textarea via React-compatible event dispatcher.")
                time.sleep(0.3)
            
            btn_submit = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            self.driver.execute_script("arguments[0].click();", btn_submit)
            log.info("Prompt submitted to Duck.ai successfully!")
        except Exception as e:
            log.error(f"Error sending prompt to Duck.ai: {e}")
            self.driver.switch_to.window(orig_handle)
            return None
            
        # --- Robust Two-Phase Response Wait Loop ---
        # Phase 1: Wait for the response streaming to actually START (non-empty text)
        log.info("Waiting for Duck.ai response generation to start...")
        started = False
        for start_attempt in range(60 if screenshot_path else 30):
            time.sleep(0.5)
            try:
                mds = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'markdown') or contains(@class, 'message-content')]")
                if not mds:
                    mds = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'message') and not(contains(@class, 'user'))]")
                if mds and mds[-1].text.strip():
                    log.info("Duck.ai response streaming has successfully started!")
                    started = True
                    break
            except: pass
            
        if not started:
            log.warning("Duck.ai response generation failed to start in time.")

        # Phase 2: Wait for streaming response to finish generating and completely STABILIZE
        log.info("Waiting for Duck.ai response generation to complete and stabilize...")
        max_attempts = 60 if is_coding else 40
        last_text = ""
        stable_count = 0
        for _ in range(max_attempts):
            time.sleep(0.5)
            current_text = ""
            try:
                mds = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'markdown') or contains(@class, 'message-content')]")
                if not mds:
                    mds = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'message') and not(contains(@class, 'user'))]")
                if mds:
                    current_text = mds[-1].text.strip()
            except: pass
            
            if current_text and current_text == last_text:
                stable_count += 1
                required_stable = 4 if is_coding else 2
                if stable_count >= required_stable:
                    break
            else:
                if current_text:
                    last_text = current_text
                    stable_count = 0
                    
        log.info(f"Duck.ai response generation completely finished: {len(last_text)} chars")
        
        # If it is a coding question, wait fully and click the copy button from the code block
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
                        if btns:
                            copy_buttons = btns
                            break
                    except: pass
                
                if copy_buttons:
                    last_btn = copy_buttons[-1]
                    self.driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", last_btn)
                    log.info("Clicked Duck.ai code block copy button successfully!")
                    time.sleep(1)
                    
                    import tkinter as tk
                    r = tk.Tk()
                    r.withdraw()
                    copied_code = r.clipboard_get()
                    r.destroy()
                    if copied_code and len(copied_code.strip()) > 50:
                        log.info(f"Successfully copied code from system clipboard ({len(copied_code)} chars).")
                        last_text = copied_code
            except Exception as e:
                log.warning(f"Could not copy code block via clipboard fallback: {e}")

        self.driver.switch_to.window(orig_handle)
        time.sleep(0.5)
        
        if "please try again" in last_text.lower() or "attempts left" in last_text.lower():
            log.warning("Duck.ai rate-limited or blocked. Falling back to local heuristic/API solvers...")
            return None
            
        return last_text

    def _gen_content(self, prompt, req_type="coding", screenshot_path=None):
        # Try Duck.ai browser chat first
        if self.driver:
            res = self.solve_via_duck_ai(prompt, screenshot_path, is_coding=(req_type == "coding"))
            if res:
                return res.strip()
                

        
        # IPC fallback
        ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        req_path, res_path = os.path.join(ws, "pending_request.json"), os.path.join(ws, "resolved_response.json")
        try:
            with open(req_path, "w") as f: json.dump({"type": req_type, "prompt": prompt}, f)
        except: return None

        log.info("Waiting up to 15 seconds for resolved_response.json fallback...")
        for _ in range(15):
            if os.path.exists(res_path):
                try:
                    with open(res_path, "r") as f: data = json.load(f)
                    for p in [req_path, res_path]:
                        if os.path.exists(p): os.remove(p)
                    return data.get("response", "").strip()
                except: pass
            time.sleep(1)
        
        # Clean up files if we timeout
        for p in [req_path, res_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        return None

    def _search(self, q):
        try:
            url = "https://html.duckduckgo.com/html/"
            data = urllib.parse.urlencode({"q": q}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            with urllib.request.urlopen(req, timeout=5) as r: html = r.read().decode('utf-8')
            snips = [re.sub(r'<[^>]+>', '', s).replace('\n', ' ').strip() for s in re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)[:4]]
            return "\n".join(f"- {s}" for s in snips if s)
        except: return ""

    def solve_mcq(self, q, opts, screenshot_path=None):
        ctx = self._search(q[:200])
        prompt = f"Question: {q}\nOptions:\n" + "\n".join(f"{i+1}. {o}" for i, o in enumerate(opts))
        prompt += f"\nContext:\n{ctx}\nStrict format:\nREASONING: <text>\nANSWER: <exact string>"
        
        if screenshot_path:
            prompt = "I have uploaded a screenshot of the question and options. Solve this question and identify the correct option. Your answer MUST EXACTLY match one of the options shown.\n" + prompt
            
        resp = self._gen_content(prompt, "mcq", screenshot_path)
        if not resp:
            # Run the smart offline DDG heuristic match solver
            log.warning("Gemini API and IPC solver failed/timed out. Falling back to DuckDuckGo offline heuristic solver...")
            if ctx and opts:
                best_opt = None
                best_score = -1
                for o in opts:
                    # Clean the option string (remove prefix like 'A.', '1.', etc.)
                    o_clean = re.sub(r'^\s*[a-d1-4][\.\)\s]+', '', o, flags=re.I).strip()
                    # Calculate basic exact matches
                    exact_matches = ctx.lower().count(o_clean.lower())
                    # Calculate matching words
                    words = [w for w in re.split(r'\W+', o_clean.lower()) if len(w) > 2]
                    word_matches = sum(ctx.lower().count(w) for w in words) if words else 0
                    
                    total_score = exact_matches * 5 + word_matches
                    log.info(f"Offline heuristic score for option '{o}': {total_score}")
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_opt = o
                
                if best_opt and best_score > 0:
                    log.info(f"Offline solver selected option: '{best_opt}' with score {best_score}")
                    return "Answer resolved offline via DuckDuckGo heuristic matching.", best_opt
            
            # Ultimate fallback if no match
            ultimate = opts[0] if opts else None
            log.warning(f"Offline solver found no matching score. Ultimate fallback: '{ultimate}'")
            return "Ultimate fallback (first option)", ultimate
        
        clean = resp.replace("**", "").replace("`", "").strip()
        r_match = re.search(r'reasoning\s*:\s*(.*?)(?=answer\s*:|$)', clean, re.I | re.S)
        a_match = re.search(r'answer\s*:\s*(.*)', clean, re.I | re.S)
        
        reasoning = r_match.group(1).strip() if r_match else "None"
        ans = a_match.group(1).strip() if a_match else clean.split('\n')[-1]
        
        if ans:
            from difflib import SequenceMatcher as SM
            best = max(opts, key=lambda o: max(
                1.0 if o.lower() == ans.lower() or o.lower() in ans.lower() else 0.0,
                SM(None, o.lower(), ans.lower()).ratio()
            ), default=None)
            return reasoning, best
        return reasoning, None

    def solve_coding(self, q, lang="C++", screenshot_path=None):
        rules = "Write ONLY code. No markdown or explanation. Write a complete program."
        prompt = f"Write executable {lang} code.\nProblem: {q}\nRules: {rules}"
        if screenshot_path:
            prompt = f"I have uploaded a screenshot of the coding task. Solve the coding task and write executable {lang} code.\nRules: {rules}"
            
        code = self._gen_content(prompt, "coding", screenshot_path)
        if not code: return None
        code = re.sub(r'^```[a-zA-Z\+\#]*\n?', '', code, flags=re.I).strip()
        return re.sub(r'```$', '', code).strip()
