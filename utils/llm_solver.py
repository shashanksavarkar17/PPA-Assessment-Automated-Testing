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
        for model in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']:
            for key in self._keys:
                for _ in range(2):
                    try:
                        genai.configure(api_key=key)
                        res = genai.GenerativeModel(model).generate_content(prompt).text
                        if res: return res.strip()
                    except Exception as e:
                        if "403" in str(e) or "leaked" in str(e).lower(): break
                        time.sleep(2)
        
        # IPC fallback
        ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        req_path, res_path = os.path.join(ws, "pending_request.json"), os.path.join(ws, "resolved_response.json")
        try:
            with open(req_path, "w") as f: json.dump({"type": req_type, "prompt": prompt}, f)
        except: return None

        for _ in range(60):
            if os.path.exists(res_path):
                try:
                    with open(res_path, "r") as f: data = json.load(f)
                    for p in [req_path, res_path]:
                        if os.path.exists(p): os.remove(p)
                    return data.get("response", "").strip()
                except: pass
            time.sleep(2)
        return None

    def _search(self, q):
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(q)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as r: html = r.read().decode('utf-8')
            snips = [re.sub(r'<[^>]+>', '', s).replace('\n', ' ').strip() for s in re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)[:4]]
            return "\n".join(f"- {s}" for s in snips if s)
        except: return ""

    def solve_mcq(self, q, opts):
        ctx = self._search(q[:200])
        prompt = f"Question: {q}\nOptions:\n" + "\n".join(f"{i+1}. {o}" for i, o in enumerate(opts))
        prompt += f"\nContext:\n{ctx}\nStrict format:\nREASONING: <text>\nANSWER: <exact string>"
        
        resp = self._gen_content(prompt, "mcq")
        if not resp: return "No response", None
        
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

    def solve_coding(self, q, prev=None, err=None, lang="C++"):
        return '#include <iostream>\nusing namespace std;\nint main() {\n    cout << "Hello World" << endl;\n    return 0;\n}'
