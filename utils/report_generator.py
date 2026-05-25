import os, json, time
from datetime import datetime
from utils.logger import get_logger

log = get_logger(__name__)

# This singleton class keeps track of our exam stats and exports everything into a telemetry file when complete!
class ReportGenerator:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ReportGenerator, cls).__new__(cls)
            cls._instance.data = {"meta": {}, "timeline": [], "questions": []}
        return cls._instance
        
    def initialize(self, email, name, mobile, roll_number, base_url):
        # Set up general context metadata parameters.
        self.data["meta"] = {"start": time.time(), "user": email, "sections": 0, "questions": 0, "pass": 0, "fail": 0}
        self.add_timeline_event("Initialized telemetry.")
        
    def add_timeline_event(self, evt):
        # Print the logs to the console and stamp a timestamp on it for telemetry.
        self.data["timeline"].append({"t": datetime.now().strftime("%H:%M:%S"), "e": evt})
        log.info(evt)
        
    def set_scanned_structure(self, data):
        # Scan totals.
        self.data["meta"].update({"sections": len(data), "questions": sum(data.values())})
        
    def _get_q(self, idx):
        # Find an existing question in the list, or create a brand new dictionary.
        for q in self.data["questions"]:
            if q["id"] == idx: return q
        q = {"id": idx, "attempts": [], "start": time.time()}
        self.data["questions"].append(q)
        return q
        
    def start_question(self, idx, type, text=""):
        q = self._get_q(idx)
        q.update({"type": type, "text": text, "start": time.time()})
        self.add_timeline_event(f"Starting Q{idx} ({type})")
        return q
        
    def set_mcq_result(self, idx, opts, reason, ans, status="PASSED"):
        q = self._get_q(idx)
        q.update({"opts": opts, "ans": ans, "status": status, "dur": time.time() - q["start"]})
        self.data["meta"]["pass" if status == "PASSED" else "fail"] += 1
        
    def add_coding_attempt(self, idx, attempt, code, err=None, ss=None):
        self._get_q(idx)["attempts"].append({"attempt": attempt, "code": code, "err": err})
        
    def set_coding_final(self, idx, code, status, lang="C++", err=""):
        q = self._get_q(idx)
        q.update({"code": code, "status": status, "lang": lang, "dur": time.time() - q["start"]})
        self.data["meta"]["pass" if status == "PASSED" else "fail"] += 1

    def build_html_dashboard(self):
        ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(ws, "telemetry.json"), "w") as f:
                json.dump(self.data, f, indent=2)
            log.info("Saved telemetry.json")
        except: pass

        try:
            from html import escape
            meta = self.data.get("meta", {})
            duration = time.time() - meta.get("start", time.time())
            
            html = (
                "<!DOCTYPE html>\n"
                "<html lang=\"en\">\n"
                "<head>\n"
                "    <meta charset=\"UTF-8\">\n"
                "    <title>Assessment Execution Telemetry Report</title>\n"
                "</head>\n"
                "<body>\n"
                "    <h1>Assessment Execution Telemetry Report</h1>\n"
                "    <hr>\n"
                "    <h2>1. Executive Summary Overview</h2>\n"
                "    <ul>\n"
                f"        <li><strong>Candidate / User Email:</strong> {escape(str(meta.get('user', 'N/A')))}</li>\n"
                f"        <li><strong>Total Scanned Sections:</strong> {escape(str(meta.get('sections', 'N/A')))}</li>\n"
                f"        <li><strong>Total Scanned Questions:</strong> {escape(str(meta.get('questions', 'N/A')))}</li>\n"
                f"        <li><strong>Passed / Solved Questions:</strong> {escape(str(meta.get('pass', 'N/A')))}</li>\n"
                f"        <li><strong>Failed / Skipped Questions:</strong> {escape(str(meta.get('fail', 'N/A')))}</li>\n"
                f"        <li><strong>Total Execution Time:</strong> {duration:.2f} seconds</li>\n"
                "    </ul>\n"
                "    <hr>\n"
                "    <h2>2. Section-by-Section Execution Status</h2>\n"
                "    <table border=\"1\">\n"
                "        <thead>\n"
                "            <tr>\n"
                "                <th>Question Index</th>\n"
                "                <th>Type</th>\n"
                "                <th>Status</th>\n"
                "                <th>Time Spent</th>\n"
                "            </tr>\n"
                "        </thead>\n"
                "        <tbody>\n"
            )
            
            for q in self.data.get("questions", []):
                q_idx = q.get("id", "N/A")
                q_type = q.get("type", "N/A")
                q_status = q.get("status", "N/A")
                q_dur = q.get("dur", 0.0)
                html += (
                    "            <tr>\n"
                    f"                <td>Q{escape(str(q_idx))}</td>\n"
                    f"                <td>{escape(str(q_type))}</td>\n"
                    f"                <td>{escape(str(q_status))}</td>\n"
                    f"                <td>{q_dur:.2f} seconds</td>\n"
                    "            </tr>\n"
                )
                
            html += (
                "        </tbody>\n"
                "    </table>\n"
                "    <hr>\n"
                "    <h2>3. Question-by-Question Detailed Telemetry</h2>\n"
            )
            
            for q in self.data.get("questions", []):
                q_idx = q.get("id", "N/A")
                q_type = q.get("type", "N/A")
                q_status = q.get("status", "N/A")
                q_text = q.get("text", "N/A")
                q_dur = q.get("dur", 0.0)
                
                html += (
                    f"    <h3>Question Q{escape(str(q_idx))} Details ({escape(str(q_type))})</h3>\n"
                    "    <ul>\n"
                    f"        <li><strong>Status:</strong> {escape(str(q_status))}</li>\n"
                    f"        <li><strong>Duration:</strong> {q_dur:.2f} seconds</li>\n"
                    "    </ul>\n"
                    "    <p><strong>Question Description Text:</strong></p>\n"
                    f"    <pre>{escape(str(q_text))}</pre>\n"
                )
                
                if q_type == "CODING":
                    q_code = q.get("code", "N/A")
                    html += (
                        "    <p><strong>Final Solution Code Injected:</strong></p>\n"
                        f"    <pre><code>{escape(str(q_code))}</code></pre>\n"
                        "    <h4>Self-Healing Attempt History Logs</h4>\n"
                    )
                    
                    attempts = q.get("attempts", [])
                    if attempts:
                        html += "    <table border=\"1\">\n"
                        html += "        <thead>\n"
                        html += "            <tr>\n"
                        html += "                <th>Attempt #</th>\n"
                        html += "                <th>Injected Code</th>\n"
                        html += "                <th>Execution / Compiler Errors Encountered</th>\n"
                        html += "            </tr>\n"
                        html += "        </thead>\n"
                        html += "        <tbody>\n"
                        for att in attempts:
                            att_num = att.get("attempt", 0)
                            att_code = att.get("code", "")
                            att_err = att.get("err", "")
                            html += (
                                "            <tr>\n"
                                f"                <td>Attempt #{escape(str(att_num))}</td>\n"
                                f"                <td><pre><code>{escape(str(att_code))}</code></pre></td>\n"
                                f"                <td><pre>{escape(str(att_err or 'No errors / Validated successfully'))}</pre></td>\n"
                                "            </tr>\n"
                            )
                        html += "        </tbody>\n"
                        html += "    </table>\n"
                    else:
                        html += "    <p><em>No attempts recorded for this coding question.</em></p>\n"
                elif q_type == "MCQ":
                    q_opts = q.get("opts", [])
                    q_ans = q.get("ans", "N/A")
                    html += "    <p><strong>Available Options:</strong></p>\n    <ul>\n"
                    for opt in q_opts:
                        html += f"        <li>{escape(str(opt))}</li>\n"
                    html += "    </ul>\n"
                    html += f"    <p><strong>Selected Choice Option:</strong> {escape(str(q_ans))}</p>\n"
                    
                html += "    <hr>\n"
                
            html += (
                "    <h2>4. System Execution Timeline Log & Audit Trail</h2>\n"
                "    <ol>\n"
            )
            
            for evt in self.data.get("timeline", []):
                t = evt.get("t", "N/A")
                e = evt.get("e", "N/A")
                html += f"        <li><strong>[{escape(str(t))}]</strong> {escape(str(e))}</li>\n"
                
            html += (
                "    </ol>\n"
                "</body>\n"
                "</html>\n"
            )
            
            report_path = os.path.join(ws, "telemetry_report.html")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html)
            log.info(f"Saved execution report to {report_path}")
        except Exception as e:
            log.warning(f"Error saving HTML telemetry report: {e}")

