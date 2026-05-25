import os
import json
import time
from datetime import datetime
from utils.logger import get_logger

log = get_logger(__name__)

# This singleton class keeps track of our exam stats and exports everything into scanned_questions.html when complete!
class ReportGenerator:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ReportGenerator, cls).__new__(cls)
            cls._instance.data = {"meta": {}, "timeline": [], "questions": []}
        return cls._instance
        
    def initialize(self, email, name, mobile, roll_number, base_url):
        self.data["meta"] = {"start": time.time(), "user": email, "sections": 0, "questions": 0, "pass": 0, "fail": 0}
        self.add_timeline_event("Initialized telemetry.")
        
    def add_timeline_event(self, evt):
        self.data["timeline"].append({"t": datetime.now().strftime("%H:%M:%S"), "e": evt})
        log.info(evt)
        
    def set_scanned_structure(self, data):
        self.data["meta"].update({"sections": len(data), "questions": sum(data.values())})
        
    def _get_q(self, idx):
        for q in self.data["questions"]:
            if q["id"] == idx: return q
        q = {"id": idx, "attempts": [], "start": time.time(), "status": "UNSOLVED"}
        self.data["questions"].append(q)
        return q
        
    def start_question(self, idx, type, text=""):
        q = self._get_q(idx)
        q.update({"type": type, "text": text, "start": time.time()})
        self.add_timeline_event(f"Starting Q{idx} ({type})")
        self.save_scanned_questions_html()
        return q
        
    def start_coding_question(self, idx, title, text, constraints="None", example_input="N/A", example_output="N/A"):
        q = self._get_q(idx)
        q.update({
            "type": "CODING",
            "title": title,
            "text": text,
            "constraints": constraints,
            "example_input": example_input,
            "example_output": example_output,
            "start": time.time()
        })
        self.add_timeline_event(f"Scanning coding question Q{idx}: '{title}'...")
        self.save_scanned_questions_html()
        return q
        
    def set_mcq_result(self, idx, opts, reason, ans, status="PASSED"):
        q = self._get_q(idx)
        q.update({"opts": opts, "ans": ans, "status": status, "dur": time.time() - q["start"]})
        self.data["meta"]["pass" if status == "PASSED" else "fail"] += 1
        self.save_scanned_questions_html()
        
    def add_coding_attempt(self, idx, attempt, code, err=None, ss=None):
        self._get_q(idx)["attempts"].append({"attempt": attempt, "code": code, "err": err})
        
    def set_coding_final(self, idx, code, status, verdict=""):
        q = self._get_q(idx)
        q.update({
            "code": code,
            "status": status,
            "verdict": verdict,
            "dur": time.time() - q["start"]
        })
        self.data["meta"]["pass" if status == "PASSED" else "fail"] += 1
        self.save_scanned_questions_html()

    def save_scanned_questions_html(self):
        from config import settings
        file_path = os.path.join(settings.REPORTS_DIR, "scanned_questions.html")
        
        try:
            from html import escape
            
            html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scanned Assessment Questions & Solutions</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #131924;
            --accent-primary: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --border-color: #1f2937;
        }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            width: 100%;
            max-width: 1000px;
        }
        header {
            margin-bottom: 40px;
            text-align: center;
        }
        h1 {
            font-size: 2.5rem;
            margin: 0 0 10px 0;
            background: linear-gradient(135deg, #60a5fa, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        p.subtitle {
            color: var(--text-muted);
            font-size: 1.1rem;
            margin: 0;
        }
        .question-card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }
        .q-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
        .q-title {
            font-size: 1.6rem;
            font-weight: 600;
            margin: 0;
            color: #60a5fa;
        }
        .badge {
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .badge-solved {
            background-color: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .badge-failed {
            background-color: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        .badge-unsolved {
            background-color: rgba(156, 163, 175, 0.15);
            color: var(--text-muted);
            border: 1px solid rgba(156, 163, 175, 0.3);
        }
        .timestamp {
            font-size: 0.85rem;
            color: var(--text-muted);
        }
        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin: 20px 0 10px 0;
            color: var(--text-main);
            border-left: 3px solid var(--accent-primary);
            padding-left: 10px;
        }
        .problem-statement {
            white-space: pre-wrap;
            line-height: 1.6;
            color: #d1d5db;
            background-color: #0d1117;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #21262d;
            font-size: 0.95rem;
        }
        .metadata-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 15px;
        }
        .metadata-box {
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            padding: 15px;
            border-radius: 8px;
        }
        .metadata-label {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .metadata-value {
            font-size: 1rem;
            font-weight: 500;
            white-space: pre-wrap;
        }
        .code-container {
            font-family: 'Fira Code', monospace;
            background-color: #0d1117;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #21262d;
            overflow-x: auto;
            margin: 0;
            color: #e6edf3;
            font-size: 0.9rem;
        }
        .verdict-box {
            background-color: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            font-family: 'Fira Code', monospace;
            font-size: 0.9rem;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Scanned Assessment Questions</h1>
            <p class="subtitle">Autonomous execution records, example testcase outputs, and final verdicts</p>
        </header>
"""
            for q in self.data.get("questions", []):
                q_idx = q.get("id", "N/A")
                q_type = q.get("type", "N/A")
                q_status = q.get("status", "UNSOLVED")
                q_title = q.get("title", f"Question {q_idx}")
                q_text = q.get("text", "N/A")
                q_constraints = q.get("constraints", "None specified")
                q_ex_in = q.get("example_input", "N/A")
                q_ex_out = q.get("example_output", "N/A")
                q_code = q.get("code", "")
                q_verdict = q.get("verdict", "No run execution performed yet.")
                
                if q_status == "PASSED":
                    badge_class = "badge-solved"
                elif q_status == "FAILED":
                    badge_class = "badge-failed"
                else:
                    badge_class = "badge-unsolved"
                
                start_time_str = datetime.fromtimestamp(q.get("start", time.time())).strftime("%Y-%m-%d %H:%M:%S")
                
                html += f"""
        <div class="question-card">
            <div class="q-header">
                <div>
                    <h2 class="q-title">{escape(str(q_title))} ({escape(str(q_type))})</h2>
                    <span class="timestamp">Scanned at: {start_time_str}</span>
                </div>
                <span class="badge {badge_class}">{escape(str(q_status))}</span>
            </div>
            
            <div class="section-title">Problem Statement</div>
            <div class="problem-statement">{escape(str(q_text))}</div>
"""
                if q_type == "CODING":
                    html += f"""
            <div class="section-title">Constraints & Example Testcases</div>
            <div class="metadata-grid">
                <div class="metadata-box">
                    <div class="metadata-label">Constraints</div>
                    <div class="metadata-value">{escape(str(q_constraints))}</div>
                </div>
                <div class="metadata-box">
                    <div class="metadata-label">Example Testcase</div>
                    <div class="metadata-label" style="font-size: 0.75rem; margin-top: 5px;">Input:</div>
                    <pre style="margin: 2px 0; font-size: 0.85rem; color: #60a5fa;">{escape(str(q_ex_in))}</pre>
                    <div class="metadata-label" style="font-size: 0.75rem; margin-top: 5px;">Expected Output:</div>
                    <pre style="margin: 2px 0; font-size: 0.85rem; color: var(--accent-green);">{escape(str(q_ex_out))}</pre>
                </div>
            </div>
"""
                    if q_code:
                        html += f"""
            <div class="section-title">Generated C++ Attempt Code</div>
            <pre class="code-container"><code>{escape(str(q_code))}</code></pre>
            
            <div class="section-title">Execution Output & Verdict Details</div>
            <div class="verdict-box">{escape(str(q_verdict))}</div>
"""
                elif q_type == "MCQ":
                    q_opts = q.get("opts", [])
                    q_ans = q.get("ans", "N/A")
                    html += """
            <div class="section-title">Available Options</div>
            <ul>
"""
                    for opt in q_opts:
                        html += f"                <li>{escape(str(opt))}</li>\n"
                    html += f"""            </ul>
            <div class="section-title">Selected Answer Verdict</div>
            <div class="verdict-box" style="color: var(--accent-green);">Successfully selected MCQ option: "{escape(str(q_ans))}"</div>
"""
                html += "        </div>"
                
            html += """
    </div>
</body>
</html>"""
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
            log.info("Saved dynamic execution record to scanned_questions.html.")
        except Exception as e:
            log.error(f"Error compiling scanned_questions.html: {e}")

    def build_html_dashboard(self):
        # Build both reports at final finish
        self.save_scanned_questions_html()
        from config import settings
        try:
            with open(os.path.join(settings.REPORTS_DIR, "telemetry.json"), "w") as f:
                json.dump(self.data, f, indent=2)
            log.info("Saved telemetry.json")
        except: pass
