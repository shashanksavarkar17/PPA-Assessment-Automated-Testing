import os
import json
import time
import urllib.request
import urllib.parse
import re
import google.generativeai as genai
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class GeminiSolver:
    def __init__(self):
        self._api_keys = getattr(settings, "GEMINI_API_KEYS", []) or [settings.GEMINI_API_KEY]
        if not self._api_keys or not self._api_keys[0]:
            raise ValueError("No GEMINI_API_KEY found in config/settings.py")
        
        self.model_name = 'gemini-1.5-flash'
        
        for idx, k in enumerate(self._api_keys):
            if k == "AIzaSyB1VPCVN9F238N_XNcnVkuKCAnDTftSfzE":
                logger.error(f"WARNING: Key[{idx}] in config/settings.py is the known leaked default key. "
                             f"This key is blocked by Google and will fail with a 403 Forbidden error. "
                             f"Please set your own valid GEMINI_API_KEY environment variable!")
                             
        genai.configure(api_key=self._api_keys[0])
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"GeminiSolver initialized (Model: {self.model_name}, Keys: {len(self._api_keys)})")

    def _generate_content_with_fallback(self, prompt, req_type="coding"):
        models = ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']
        
        for model_name in models:
            for key_idx, api_key in enumerate(self._api_keys):
                for attempt in range(2):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel(model_name)
                        result = model.generate_content(prompt).text
                        if result:
                            return result.strip()
                    except Exception as e:
                        err = str(e).lower()
                        if "leaked" in err or "403" in err:
                            logger.error(f"CRITICAL API ERROR: Key[{key_idx}] leaked/blocked (403).")
                            break
                        elif any(x in err for x in ["429", "quota", "rate", "resource_exhausted"]):
                            if attempt == 0:
                                logger.warning(f"Key[{key_idx}] quota hit on {model_name}. Rotating...")
                            else:
                                time.sleep(5)
                        else:
                            logger.warning(f"Model {model_name} error: {e}")
                            break
        
        logger.warning("All LLM attempts exhausted. Activating local IPC bridge.")
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        req_path = os.path.join(workspace, "pending_request.json")
        res_path = os.path.join(workspace, "resolved_response.json")
        
        try:
            with open(req_path, "w") as f:
                json.dump({"type": req_type, "prompt": prompt}, f)
        except Exception as e:
            logger.error(f"Failed to write IPC request: {e}")
            return None

        logger.info("Waiting up to 120s for manual input in 'resolved_response.json'...")
        for _ in range(60):
            if os.path.exists(res_path):
                try:
                    with open(res_path, "r") as f:
                        data = json.load(f)
                    for path in [req_path, res_path]:
                        if os.path.exists(path): os.remove(path)
                    logger.info("IPC response successfully loaded.")
                    return data.get("response", "").strip()
                except Exception as e:
                    logger.warning(f"IPC read error: {e}")
            time.sleep(2)
            
        logger.error("IPC bridge timed out. Skipping question.")
        return None

    def _search_web(self, query):
        logger.info(f"Searching Web: {query}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Safari/537.36'}
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                html = response.read().decode('utf-8')
            
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            clean_snippets = []
            for s in snippets[:4]:
                clean = re.sub(r'<[^>]+>', '', s).replace('\n', ' ').strip()
                if clean:
                    clean_snippets.append(clean)
            return "\n".join(f"- {s}" for s in clean_snippets)
        except Exception as e:
            logger.warning(f"Web search skipped: {e}")
            return ""

    def solve_mcq(self, question, options):
        search_ctx = self._search_web(question.strip()[:200])
        
        prompt = f"""You are taking a programming test. Select the correct option.
Question: {question}

Options:
"""
        for i, opt in enumerate(options):
            prompt += f"{i+1}. {opt}\n"
            
        if search_ctx:
            prompt += f"\nReference context:\n{search_ctx}\n"

        prompt += """
Strictly output in this exact format:
REASONING: <short step-by-step logic>
ANSWER: <exact matching option string from list above, character for character>
"""
        try:
            resp = self._generate_content_with_fallback(prompt, "mcq")
            if not resp:
                return "No reasoning (solver quota hit).", None
            
            logger.info(f"MCQ response: {resp}")
            
            clean_resp = resp.replace("**", "").replace("*", "").replace("__", "").replace("_", "").replace("`", "").strip()
            
            reasoning, answer = "No reasoning.", None
            
            r_match = re.search(r'reasoning\s*:\s*(.*?)(?=answer\s*:|$)', clean_resp, re.IGNORECASE | re.DOTALL)
            a_match = re.search(r'answer\s*:\s*(.*)', clean_resp, re.IGNORECASE | re.DOTALL)
            
            if r_match:
                reasoning = r_match.group(1).strip()
            if a_match:
                answer = a_match.group(1).strip()
            else:
                lines = [l.strip() for l in clean_resp.split("\n") if l.strip()]
                for l in reversed(lines):
                    clean_line = re.sub(r'^(answer|reasoning)\s*:\s*', '', l, flags=re.IGNORECASE).strip()
                    if clean_line in options:
                        answer = clean_line
                        break
                if not answer and lines:
                    answer = re.sub(r'^(answer|reasoning)\s*:\s*', '', lines[-1], flags=re.IGNORECASE).strip()
            
            if answer:
                for opt in options:
                    if opt.lower() == answer.lower():
                        return reasoning, opt
                
                for opt in options:
                    if opt.lower() in answer.lower() or answer.lower() in opt.lower():
                        return reasoning, opt
                
                clean_ans = re.sub(r'^[a-zA-Z0-9][\.\)\-\s]+', '', answer).strip()
                for opt in options:
                    clean_opt = re.sub(r'^[a-zA-Z0-9][\.\)\-\s]+', '', opt).strip()
                    if clean_opt.lower() == clean_ans.lower() or clean_opt.lower() in clean_ans.lower():
                        return reasoning, opt
                
                from difflib import SequenceMatcher
                best_ratio = 0.0
                best_opt = None
                for opt in options:
                    ratio = SequenceMatcher(None, opt.lower(), answer.lower()).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_opt = opt
                if best_ratio > 0.6:
                    return reasoning, best_opt
                    
            return reasoning, answer
        except Exception as e:
            logger.error(f"MCQ solving error: {e}")
            return "Resolution error.", None

    def solve_coding(self, question, previous_code=None, error_message=None, language="C++"):
        lang = language.lower()
        
        if "python" in lang:
            lang_rules = "Write ONLY valid Python 3 code. Read standard input (sys.stdin) and write to standard output. Do not include markdown wraps."
        elif "java" in lang:
            lang_rules = "Write ONLY valid Java code. Public class MUST be 'Main'. Include standard main method. Read from standard input, print to standard output."
        elif "javascript" in lang or "js" in lang:
            lang_rules = "Write ONLY valid Node.js code. Read from standard input, print to standard output."
        else:
            lang_rules = "Write ONLY valid C++ code. Include necessary libraries like <iostream>, <vector>, <algorithm>. Use namespace std. Provide int main()."

        prompt = f"""You are a competitive programmer. Write complete executable code in {language}.
Problem:
{question}
"""
        if previous_code and error_message:
            prompt += f"""
Previous Code:
{previous_code}

Execution/Compilation Error:
{error_message}

Correct this code to be fast and correct.
"""
        prompt += f"\nRules:\n{lang_rules}\nReturn ONLY executable code without comments or explanation. No markdown syntax wrapper."

        try:
            code = self._generate_content_with_fallback(prompt, "coding")
            if not code:
                return None
            
            for wrap in ["cpp", "c++", "python", "py", "java", "javascript", "js"]:
                for prefix in [f"``` {wrap}", f"```{wrap}"]:
                    if code.lower().startswith(prefix):
                        code = code[len(prefix):]
                        break
            if code.startswith("```"): code = code[3:]
            if code.endswith("```"): code = code[:-3]
            
            cleaned = code.strip()
            return cleaned if cleaned else None
        except Exception as e:
            logger.error(f"Coding resolution error: {e}")
            return None
