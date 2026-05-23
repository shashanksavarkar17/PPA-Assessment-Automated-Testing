import os
import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

log = get_logger(__name__)

# This page handles checking the main test dashboard, listing all sections and writing an HTML/text summary.
class SummaryPage(BasePage):
    def wait_for_page_load(self):
        # We wait until the first "Solve" or "Review" button is visible to confirm we're back on the dashboard.
        self.helpers.wait_for_element((By.XPATH, "//button[contains(text(), 'Solve') or contains(text(), 'Review')]"))
        
    def clean_section_name(self, raw_name):
        if not raw_name: return ""
        name = raw_name.split("\n")[0].split("Attempted")[0].strip()
        return name

    def start_section(self, section_idx):
        try:
            # Locate all the section solve buttons and click the target one via JS.
            btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Solve')]")
            if not btns or section_idx - 1 >= len(btns): return False
            self.driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", btns[section_idx - 1])
            return True
        except: return False

    def start_first_unsolved_in_section(self, section_name):
        clean_sec_target = self.clean_section_name(section_name).lower()
        log.info(f"Looking for first unsolved/failed question in section: '{clean_sec_target}'")
        try:
            rows = self.driver.find_elements(By.XPATH, "//tr")
            curr_sec = None
            for r in rows:
                try:
                    th = r.find_elements(By.TAG_NAME, "th")
                    if th and "section:" in th[0].text.lower():
                        curr_sec = self.clean_section_name(th[0].text).lower()
                    elif curr_sec and curr_sec == clean_sec_target:
                        tds = [t.text.strip() for t in r.find_elements(By.TAG_NAME, "td")]
                        if len(tds) >= 3:
                            # 4-column support: tds[3] is Status, tds[2] is Type
                            status = tds[3].lower() if len(tds) >= 4 else tds[2].lower()
                            problem_name = tds[1]
                            
                            # Identify any status except success / solved (exact match) / passed
                            is_passed = any(x in status for x in ["success", "passed"]) or (status == "solved")
                            if not is_passed:
                                btn_elements = r.find_elements(By.XPATH, ".//button | .//a")
                                for btn in btn_elements:
                                    if btn.is_displayed() and btn.is_enabled():
                                        # Click the button (whether Solve or Review, as long as status is unsolved)
                                        log.info(f"Opening unsolved question '{problem_name}' (Status: {status}) via button click.")
                                        self.driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", btn)
                                        return True
                except: pass
        except Exception as e:
            log.warning(f"Error starting first unsolved in section: {e}")
        return False

    def scan_sections_and_questions(self):
        try:
            # Find all table rows to parse the test structure.
            rows = self.driver.find_elements(By.XPATH, "//tr")
            data, curr_sec = {}, None
            
            for r in rows:
                th = r.find_elements(By.TAG_NAME, "th")
                if th and "Section:" in th[0].text:
                    # Found a new section header row. Clean it to base title name and group questions under it.
                    curr_sec = th[0].text[th[0].text.find("Section:"):].strip()
                    curr_sec = self.clean_section_name(curr_sec)
                    data[curr_sec] = []
                elif curr_sec:
                    # This must be a question detail row. Parse standard columns: ID, Description, Type, Status.
                    tds = [t.text.strip() or "N/A" for t in r.find_elements(By.TAG_NAME, "td")]
                    if len(tds) >= 3:
                        qid = f"Question {tds[0]}" if tds[0].isdigit() else (tds[0] if tds[0] != "N/A" else f"Question {len(data[curr_sec]) + 1}")
                        # 4-column support: tds[3] is Status, tds[2] is Type
                        status = tds[3] if len(tds) >= 4 else tds[2]
                        data[curr_sec].append({"id": qid, "desc": tds[1], "status": status})
            
            sec_counts = {k: len(v) for k, v in data.items()}
            tot_q = sum(sec_counts.values())
            
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            txt_path = os.path.join(base_dir, "assessment_summary.txt")
            html_path = os.path.join(base_dir, "assessment_summary.html")
            
            # Write a simple text file summarizing everything we scanned.
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"Assessment Summary\n==================\n\nOverview:\nTotal Sections: {len(sec_counts)}\nTotal Questions: {tot_q}\n\nScanned Sections:\n")
                for s, c in sec_counts.items(): f.write(f"- {s}: {c} questions\n")
                f.write("\nQuestions:\n")
                for s, qs in data.items():
                    f.write(f"\n--- {s} ---\n")
                    for q in qs: f.write(f"- {q['id']} | Question: {q['desc']} | Type/Status: {q['status']}\n")
            
            # Write a beautifully simple HTML report to look at in the browser.
            html = f'''<!DOCTYPE html><html><head><title>Assessment Summary</title></head><body><h1>Assessment Summary</h1>
<h2>Overview</h2><table border="1"><tr><th>Total Sections</th><th>Total Questions</th></tr><tr><td>{len(sec_counts)}</td><td>{tot_q}</td></tr></table>
<h2>Scanned Sections</h2><table border="1"><tr><th>Section Name</th><th>Questions Count</th></tr>'''
            for s, c in sec_counts.items(): html += f"<tr><td>{s}</td><td>{c}</td></tr>"
            html += '''</table><h2>Questions</h2><table border="1"><tr><th>Section</th><th>Question Index</th><th>Question</th><th>Type/Status</th></tr>'''
            for s, qs in data.items():
                for q in qs: html += f"<tr><td>{s}</td><td>{q['id']}</td><td>{q['desc']}</td><td>{q['status']}</td></tr>"
            html += "</table></body></html>"
 
            with open(html_path, "w", encoding="utf-8") as f: f.write(html)
            print(f"Summary logs written to {txt_path} and {html_path}")
            return sec_counts
        except Exception as e:
            log.warning(f"Oh no, failed to scan assessment summary: {e}")
            return {}

    def submit_assessment(self):
        try:
            for el in self.driver.find_elements(By.XPATH, "//button | //a"):
                if el.is_displayed() and el.is_enabled():
                    text = el.text.lower()
                    if "submit" in text and ("assessment" in text or "test" in text or "final" in text):
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", el)
                        log.info("Clicked the final 'Submit Assessment' button.")
                        return True
            log.warning("Could not find the final 'Submit Assessment' button.")
            return False
        except Exception as e:
            log.error(f"Failed to submit assessment: {e}")
            return False
