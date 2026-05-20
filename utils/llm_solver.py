import os, json, time, urllib.request, urllib.parse, re
import google.generativeai as genai
from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

class GeminiSolver:
    def __init__(self):
        self._keys = getattr(settings, "GEMINI_API_KEYS", []) or [settings.GEMINI_API_KEY]
        if not self._keys or not self._keys[0]: raise ValueError("No GEMINI_API_KEY")
        self.model_name = 'gemini-1.5-flash'
        genai.configure(api_key=self._keys[0])

    def _gen_content(self, prompt, req_type="coding"):
        for model in ['gemini-1.5-flash', 'gemini-1.5-pro']:
            for key in self._keys:
                for attempt in range(2):
                    try:
                        genai.configure(api_key=key)
                        res = genai.GenerativeModel(model).generate_content(prompt).text
                        if res: return res.strip()
                    except Exception as e:
                        err = str(e).lower()
                        log.warning(f"Gemini API error (model={model}, key={key[:8]}...): {e}")
                        if "429" in err or "quota" in err or "exhausted" in err:
                            if attempt == 0:
                                time.sleep(5)
                                continue
                            break
                        if "403" in err or "leaked" in err:
                            break
                        time.sleep(1)
        
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

    def solve_mcq(self, q, opts):
        ctx = self._search(q[:200])
        prompt = f"Question: {q}\nOptions:\n" + "\n".join(f"{i+1}. {o}" for i, o in enumerate(opts))
        prompt += f"\nContext:\n{ctx}\nStrict format:\nREASONING: <text>\nANSWER: <exact string>"
        
        resp = self._gen_content(prompt, "mcq")
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

    def solve_coding(self, q, lang="C++"):
        rules = "Write ONLY code. No markdown or explanation. Write a complete program."
        prompt = f"Write executable {lang} code.\nProblem: {q}\nRules: {rules}"
        code = self._gen_content(prompt, "coding")
        if not code: return None
        code = re.sub(r'^```[a-zA-Z\+\#]*\n?', '', code, flags=re.I).strip()
        return re.sub(r'```$', '', code).strip()
