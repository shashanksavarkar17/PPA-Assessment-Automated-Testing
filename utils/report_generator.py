import os
import json
import time
from datetime import datetime
from utils.logger import get_logger

log = get_logger(__name__)

# Singleton class for monitoring assessment telemetry and exporting results to HTML format.
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
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #333333;
            background-color: #ffffff;
            line-height: 1.5;
            margin: 0;
            padding: 24px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        header {
            border-bottom: 2px solid #eaeaea;
            padding-bottom: 16px;
            margin-bottom: 24px;
            text-align: left;
        }
        h1 {
            font-size: 26px;
            font-weight: 700;
            margin: 0 0 8px 0;
            color: #111111;
        }
        .subtitle {
            color: #666666;
            font-size: 15px;
            margin: 0;
        }
        .question-card {
            border: 1px solid #dddddd;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 24px;
            background-color: #f9f9f9;
        }
        .q-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #eaeaea;
            padding-bottom: 12px;
            margin-bottom: 16px;
        }
        .q-title {
            font-size: 18px;
            font-weight: 600;
            margin: 0;
            color: #222222;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            border: 1px solid #ccc;
        }
        .badge-solved {
            background-color: #e6f4ea;
            color: #137333;
            border-color: #c2e7cd;
        }
        .badge-failed {
            background-color: #fce8e6;
            color: #c5221f;
            border-color: #fad2cf;
        }
        .badge-unsolved {
            background-color: #f1f3f4;
            color: #5f6368;
            border-color: #dadce0;
        }
        .timestamp {
            font-size: 12px;
            color: #777777;
        }
        .section-title {
            font-size: 13px;
            font-weight: 700;
            margin: 16px 0 8px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #555555;
        }
        .problem-statement {
            white-space: pre-wrap;
            background-color: #ffffff;
            padding: 12px;
            border-radius: 4px;
            border: 1px solid #eaeaea;
            font-size: 14px;
            color: #333333;
        }
        .metadata-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 12px;
        }
        .metadata-box {
            background-color: #ffffff;
            border: 1px solid #eaeaea;
            padding: 12px;
            border-radius: 4px;
        }
        .metadata-label {
            font-size: 10px;
            font-weight: 600;
            color: #777777;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .metadata-value {
            font-size: 13px;
            white-space: pre-wrap;
        }
        .code-container {
            font-family: Consolas, Monaco, monospace;
            background-color: #f4f4f4;
            padding: 12px;
            border-radius: 4px;
            border: 1px solid #eaeaea;
            overflow-x: auto;
            margin: 0;
            color: #333333;
            font-size: 13px;
        }
        .verdict-box {
            background-color: #ffffff;
            padding: 12px;
            border-radius: 4px;
            border: 1px solid #eaeaea;
            font-family: Consolas, Monaco, monospace;
            font-size: 13px;
            white-space: pre-wrap;
        }
        ul {
            margin: 8px 0;
            padding-left: 20px;
        }
        li {
            font-size: 14px;
            margin-bottom: 4px;
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
        # Compile both analytical reports upon execution completion.
        self.save_scanned_questions_html()
        from config import settings
        
        # Save telemetry data first
        try:
            with open(os.path.join(settings.REPORTS_DIR, "telemetry.json"), "w") as f:
                json.dump(self.data, f, indent=2)
            log.info("Saved telemetry.json")
        except: pass
        
        # Load raw log text for embedding
        log_content = "Log file not found."
        try:
            log_path = os.path.join(settings.REPORTS_DIR, "execution_log.txt")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    log_content = f.read()
        except Exception as e:
            log_content = f"Error reading log file: {e}"
            
        file_path = os.path.join(settings.REPORTS_DIR, "assessment_dashboard.html")
        try:
            from html import escape
            
            meta = self.data.get("meta", {})
            timeline = self.data.get("timeline", [])
            questions = self.data.get("questions", [])
            
            total_sec = meta.get("sections", 0)
            total_q = meta.get("questions", 0)
            passed = meta.get("pass", 0)
            failed = meta.get("fail", 0)
            unsolved = max(0, total_q - (passed + failed))
            
            start_time = meta.get("start", time.time())
            start_time_str = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")
            duration_str = f"{int(time.time() - start_time)} seconds"
                
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Assessment Execution Dashboard</title>
    <style>
        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #ffffff;
            color: #333333;
            margin: 0;
            padding: 24px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 24px;
            text-align: left;
            border-bottom: 2px solid #eaeaea;
            padding-bottom: 16px;
        }}
        h1 {{
            font-size: 26px;
            font-weight: 700;
            margin: 0 0 8px 0;
            color: #111111;
        }}
        .subtitle {{
            color: #666666;
            font-size: 15px;
            margin: 0;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background-color: #f9f9f9;
            border: 1px solid #dddddd;
            border-radius: 6px;
            padding: 20px;
        }}
        .card-title {{
            font-size: 12px;
            font-weight: 700;
            color: #666666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
            border-bottom: 1px solid #eaeaea;
            padding-bottom: 6px;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: 700;
            color: #111111;
            margin-bottom: 8px;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }}
        .stat-item {{
            background-color: #ffffff;
            border: 1px solid #eaeaea;
            padding: 8px;
            border-radius: 4px;
            text-align: center;
        }}
        .stat-item-label {{
            font-size: 11px;
            color: #777777;
        }}
        .stat-item-value {{
            font-size: 14px;
            font-weight: 600;
        }}
        .timeline-section {{
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 16px;
            color: #222222;
            border-bottom: 1px solid #dddddd;
            padding-bottom: 6px;
        }}
        .timeline-container {{
            background-color: #f9f9f9;
            border: 1px solid #dddddd;
            border-radius: 6px;
            padding: 16px;
            max-height: 350px;
            overflow-y: auto;
        }}
        .timeline-item {{
            display: flex;
            padding: 10px 0;
            border-bottom: 1px solid #eaeaea;
        }}
        .timeline-item:last-child {{
            border-bottom: none;
        }}
        .timeline-time {{
            font-family: Consolas, Monaco, monospace;
            width: 80px;
            color: #0066cc;
            font-weight: 600;
            font-size: 13px;
        }}
        .timeline-desc {{
            flex: 1;
            color: #333333;
            font-size: 13px;
        }}
        .log-section {{
            margin-bottom: 30px;
        }}
        .log-viewer {{
            font-family: Consolas, Monaco, monospace;
            background-color: #f4f4f4;
            padding: 16px;
            border-radius: 6px;
            border: 1px solid #eaeaea;
            max-height: 350px;
            overflow-y: auto;
            white-space: pre-wrap;
            color: #333333;
            font-size: 13px;
            line-height: 1.4;
        }}
        .footer {{
            text-align: center;
            color: #777777;
            font-size: 12px;
            margin-top: 40px;
            border-top: 1px solid #eaeaea;
            padding-top: 16px;
        }}
        .link-btn {{
            display: inline-block;
            background-color: #0066cc;
            color: #ffffff;
            padding: 8px 16px;
            border-radius: 4px;
            text-decoration: none;
            font-weight: 600;
            font-size: 13px;
            margin-top: 12px;
            text-align: center;
            border: 1px solid #0052a3;
        }}
        .link-btn:hover {{
            background-color: #0052a3;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Assessment Traversal & Execution Dashboard</h1>
            <p class="subtitle">Complete telemetry, real-time logs, and question statements with code solutions</p>
        </header>
        
        <div class="grid">
            <div class="card" style="display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div class="card-title">Portal & Candidate Information</div>
                    <div style="margin-bottom: 8px;"><strong style="color: var(--text-muted);">Candidate:</strong> {escape(str(meta.get("user", "BOT")))}</div>
                    <div style="margin-bottom: 8px;"><strong style="color: var(--text-muted);">Started At:</strong> {escape(start_time_str)}</div>
                    <div style="margin-bottom: 8px;"><strong style="color: var(--text-muted);">Execution Duration:</strong> {escape(duration_str)}</div>
                </div>
                <a href="scanned_questions.html" class="link-btn">View Scanned Questions</a>
            </div>
            
            <div class="card">
                <div class="card-title">Assessment Question Stats</div>
                <div class="stat-value">{escape(str(total_q))}</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-item-label">Passed / Solved</div>
                        <div class="stat-item-value" style="color: var(--accent-green);">{escape(str(passed))}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-item-label">Failed / Partial</div>
                        <div class="stat-item-value" style="color: var(--accent-red);">{escape(str(failed))}</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">Structure Summary</div>
                <div style="margin-bottom: 12px;"><strong style="color: var(--text-muted);">Total Sections Scanned:</strong> {escape(str(total_sec))}</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-item-label">Unsolved Remaining</div>
                        <div class="stat-item-value" style="color: var(--text-muted);">{escape(str(unsolved))}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-item-label">Success Rate</div>
                        <div class="stat-item-value" style="color: var(--accent-green);">{escape(str(int(passed * 100 / total_q) if total_q > 0 else 0))}%</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="timeline-section">
            <div class="section-title">Execution Event Timeline</div>
            <div class="timeline-container">
"""
            for evt in timeline:
                html += f"""
                <div class="timeline-item">
                    <div class="timeline-time">{escape(str(evt.get("t", "")))}</div>
                    <div class="timeline-desc">{escape(str(evt.get("e", "")))}</div>
                </div>
"""
            html += f"""
            </div>
        </div>
        
        <div class="log-section">
            <div class="section-title">Raw Execution Console Logs</div>
            <pre class="log-viewer"><code>{escape(log_content)}</code></pre>
        </div>
        
        <div class="footer">
            Generated autonomously by Antigravity Automation Solver • {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
</body>
</html>"""
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
            log.info("Saved integrated telemetry dashboard to assessment_dashboard.html.")
        except Exception as e:
            log.error(f"Error compiling assessment_dashboard.html: {e}")
