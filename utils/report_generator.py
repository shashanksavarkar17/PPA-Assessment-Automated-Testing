import os
import json
import time
from datetime import datetime
from utils.logger import get_logger

log = get_logger(__name__)

class ReportGenerator:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ReportGenerator, cls).__new__(cls)
            cls._instance.data = {"meta": {}, "timeline": [], "questions": []}
        return cls._instance
        
    def initialize(self, email, name, mobile, roll_number, base_url):
        self.data["meta"] = {
            "start": time.time(), "user": email, "name": name, 
            "mobile": mobile, "roll_number": roll_number, "base_url": base_url,
            "sections": 0, "questions": 0, "pass": 0, "fail": 0
        }
        self.add_timeline_event("Initialized telemetry report system.")
        
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
        self.add_timeline_event(f"Starting Question {idx} ({type})")
        return q
        
    def start_coding_question(self, idx, title, text, constraints="None", example_input="N/A", example_output="N/A"):
        q = self._get_q(idx)
        q.update({
            "type": "CODING", "title": title, "text": text, "constraints": constraints,
            "example_input": example_input, "example_output": example_output, "start": time.time()
        })
        self.add_timeline_event(f"Scanning coding question Q{idx}: '{title}'...")
        return q
        
    def set_mcq_result(self, idx, opts, reason, ans, status="PASSED"):
        q = self._get_q(idx)
        q.update({"opts": opts, "ans": ans, "status": status, "reasoning": reason, "dur": time.time() - q["start"]})
        self.data["meta"]["pass" if status == "PASSED" else "fail"] += 1
        
    def add_coding_attempt(self, idx, attempt, code, err=None):
        self._get_q(idx)["attempts"].append({"attempt": attempt, "code": code, "err": err})
        
    def set_coding_final(self, idx, code, status, verdict=""):
        q = self._get_q(idx)
        q.update({"code": code, "status": status, "verdict": verdict, "dur": time.time() - q["start"]})
        self.data["meta"]["pass" if status == "PASSED" else "fail"] += 1

    def build_html_dashboard(self):
        from config import settings
        
        # Save telemetry details first
        try:
            with open(os.path.join(settings.REPORTS_DIR, "telemetry.json"), "w") as f:
                json.dump(self.data, f, indent=2)
        except: pass
        
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
            success_rate = int(passed * 100 / total_q) if total_q > 0 else 0
            
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Assessment Execution Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --success: #10b981;
            --success-bg: #ecfdf5;
            --danger: #ef4444;
            --danger-bg: #fef2f2;
            --warning: #f59e0b;
            --warning-bg: #fef3c7;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            line-height: 1.5;
            padding: 40px 24px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}
        h1 {{ font-size: 28px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }}
        .subtitle {{ font-size: 15px; color: var(--text-muted); }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 24px;
            margin-bottom: 32px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        }}
        .card-title {{
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }}
        .stat-value {{ font-size: 36px; font-weight: 700; color: #0f172a; margin-bottom: 12px; }}
        .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        .stat-item {{
            background: var(--bg);
            border: 1px solid var(--border);
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-item-label {{ font-size: 10px; color: var(--text-muted); margin-bottom: 4px; }}
        .stat-item-value {{ font-size: 15px; font-weight: 600; }}
        .info-row {{ margin-bottom: 10px; font-size: 14px; display: flex; justify-content: space-between; }}
        .info-row span {{ color: var(--text-muted); }}
        .info-row strong {{ color: var(--text-main); font-weight: 500; }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            margin: 40px 0 20px 0;
            color: #0f172a;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}
        .badge-passed {{ background: var(--success-bg); color: var(--success); }}
        .badge-failed {{ background: var(--danger-bg); color: var(--danger); }}
        .badge-unsolved {{ background: var(--bg); color: var(--text-muted); border: 1px solid var(--border); }}
        .question-list {{ display: flex; flex-direction: column; gap: 20px; }}
        .q-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
        }}
        .q-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }}
        .q-name {{ font-size: 17px; font-weight: 600; color: #0f172a; }}
        .q-meta {{ font-size: 12px; color: var(--text-muted); margin-top: 4px; }}
        .pre-box {{
            background: var(--bg);
            border: 1px solid var(--border);
            padding: 14px;
            border-radius: 8px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px;
            color: #334155;
            white-space: pre-wrap;
            margin: 12px 0;
        }}
        .sub-sec {{ font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-top: 18px; letter-spacing: 0.03em; }}
        .split-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .timeline-container, .log-viewer {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
        }}
        .timeline-item {{ display: flex; padding: 12px 0; border-bottom: 1px solid var(--border); }}
        .timeline-item:last-child {{ border-bottom: none; }}
        .timeline-time {{ font-family: monospace; width: 90px; color: var(--primary); font-weight: 600; }}
        .timeline-desc {{ flex: 1; font-size: 14px; color: var(--text-main); }}
        .log-viewer {{
            background: #0f172a;
            color: #e2e8f0;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12.5px;
            white-space: pre-wrap;
            line-height: 1.6;
        }}
        .footer {{ text-align: center; color: var(--text-muted); font-size: 12px; margin-top: 60px; padding-top: 24px; border-top: 1px solid var(--border); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Assessment Execution Report</h1>
            <p class="subtitle">Unified runtime metrics, execution logs, and detailed question solution telemetry</p>
        </header>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">Candidate Details</div>
                <div class="info-row"><span>Email:</span> <strong>{escape(str(meta.get("user", "ppa@yopmail.com")))}</strong></div>
                <div class="info-row"><span>Name:</span> <strong>{escape(str(meta.get("name", "BOT")))}</strong></div>
                <div class="info-row"><span>Mobile:</span> <strong>{escape(str(meta.get("mobile", "9999999999")))}</strong></div>
                <div class="info-row"><span>Roll Number:</span> <strong>{escape(str(meta.get("roll_number", "N/A")))}</strong></div>
            </div>
            
            <div class="card">
                <div class="card-title">Solve Statistics</div>
                <div class="stat-value">{escape(str(total_q))}</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-item-label">Passed Questions</div>
                        <div class="stat-item-value" style="color: var(--success);">{escape(str(passed))}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-item-label">Failed Questions</div>
                        <div class="stat-item-value" style="color: var(--danger);">{escape(str(failed))}</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">Session Performance</div>
                <div class="info-row"><span>Duration:</span> <strong>{escape(duration_str)}</strong></div>
                <div class="info-row"><span>Started At:</span> <strong>{escape(start_time_str)}</strong></div>
                <div class="stat-grid" style="margin-top: 12px;">
                    <div class="stat-item">
                        <div class="stat-item-label">Unsolved</div>
                        <div class="stat-item-value">{escape(str(unsolved))}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-item-label">Success Rate</div>
                        <div class="stat-item-value" style="color: var(--success);">{escape(str(success_rate))}%</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="section-title">Scanned Questions & Verified Solutions</div>
        <div class="question-list">
"""
            for q in questions:
                q_id = q.get("id", "")
                q_type = q.get("type", "N/A")
                q_status = q.get("status", "UNSOLVED")
                q_text = q.get("text", "")
                q_dur = f"{int(q.get('dur', 0))}s" if q.get('dur') else "N/A"
                
                badge_class = f"badge-{q_status.lower()}"
                
                html += f"""
            <div class="q-card">
                <div class="q-header">
                    <div>
                        <div class="q-name">Question {escape(str(q_id))} ({escape(str(q_type))})</div>
                        <div class="q-meta">Solving Time: {q_dur}</div>
                    </div>
                    <span class="badge {badge_class}">{escape(str(q_status))}</span>
                </div>
                
                <div class="sub-sec">Question Description</div>
                <div class="pre-box">{escape(str(q_text))}</div>
"""
                if q_type == "CODING":
                    q_constraints = q.get("constraints", "None")
                    q_ex_in = q.get("example_input", "N/A")
                    q_ex_out = q.get("example_output", "N/A")
                    q_code = q.get("code", "")
                    q_verdict = q.get("verdict", "")
                    
                    html += f"""
                <div class="split-grid">
                    <div>
                        <div class="sub-sec">Constraints</div>
                        <div class="pre-box">{escape(str(q_constraints))}</div>
                    </div>
                    <div>
                        <div class="sub-sec">Example Testcase</div>
                        <div class="pre-box"><strong>Input:</strong>\n{escape(str(q_ex_in))}\n\n<strong>Expected Output:</strong>\n{escape(str(q_ex_out))}</div>
                    </div>
                </div>
"""
                    if q_code:
                        html += f"""
                <div class="sub-sec">Generated solution code</div>
                <div class="pre-box" style="font-family: monospace; background: #f1f5f9;">{escape(str(q_code))}</div>
"""
                    if q_verdict:
                        html += f"""
                <div class="sub-sec">Compilation / Execution Verdict</div>
                <div class="pre-box">{escape(str(q_verdict))}</div>
"""
                elif q_type == "MCQ":
                    q_opts = q.get("opts", [])
                    q_ans = q.get("ans", "N/A")
                    q_reasoning = q.get("reasoning", "")
                    
                    html += f"""
                <div class="sub-sec">Available Options</div>
                <ul style="margin: 8px 0 0 20px; font-size: 14px; color: var(--text-main);">
"""
                    for opt in q_opts:
                        html += f"                    <li>{escape(str(opt))}</li>\n"
                    html += f"""                </ul>
                <div class="sub-sec">Selected Option</div>
                <div class="pre-box"><strong>Option Selected:</strong> {escape(str(q_ans))}</div>
"""
                    if q_reasoning:
                        html += f"""
                <div class="sub-sec">LLM Verification Reasoning</div>
                <div class="pre-box">{escape(str(q_reasoning))}</div>
"""
                html += "            </div>"
                
            html += f"""
        </div>
        
        <div class="split-grid" style="margin-top: 40px; grid-template-columns: 1fr 1fr;">
            <div>
                <div class="section-title">Telemetry Timeline</div>
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
            
            <div>
                <div class="section-title">Raw Console logs</div>
                <pre class="log-viewer"><code>{escape(log_content)}</code></pre>
            </div>
        </div>
        
        <div class="footer">
            Generated autonomously by Antigravity Automation Solver • {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
</body>
</html>"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
            log.info(f"Saved consolidated dashboard to {file_path}")
        except Exception as e:
            log.error(f"Error compiling dashboard: {e}")
