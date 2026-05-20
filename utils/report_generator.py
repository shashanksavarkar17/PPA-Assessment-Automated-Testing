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
        # Output our telemetry.json log file to the project workspace directory.
        ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(ws, "telemetry.json"), "w") as f:
                json.dump(self.data, f, indent=2)
            log.info("Saved telemetry.json")
        except: pass
