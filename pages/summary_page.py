import os
import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

log = get_logger(__name__)

class SummaryPage(BasePage):
    """Overall Assessment Summary Page operations."""

    def wait_for_page_load(self):
        self.helpers.wait_for_element((By.XPATH, "//button[contains(text(), 'Solve')]"))
        
    def start_section(self, section_idx):
        try:
            btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Solve')]")
            if not btns or section_idx - 1 >= len(btns): return False
            btn = btns[section_idx - 1]
            self.driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", btn)
            return True
        except: return False

    def scan_sections_and_questions(self):
        try:
            rows = self.driver.find_elements(By.XPATH, "//tr")
            data, curr_sec = {}, None
            
            for r in rows:
                th = r.find_elements(By.TAG_NAME, "th")
                if th and "Section:" in th[0].text:
                    curr_sec = th[0].text[th[0].text.find("Section:"):].strip()
                    data[curr_sec] = []
                elif curr_sec:
                    tds = [t.text.strip() or "N/A" for t in r.find_elements(By.TAG_NAME, "td")]
                    if len(tds) >= 3:
                        qid = f"Question {tds[0]}" if tds[0].isdigit() else (tds[0] if tds[0] != "N/A" else f"Question {len(data[curr_sec]) + 1}")
                        data[curr_sec].append({"id": qid, "desc": tds[1], "status": tds[2]})
            
            sec_counts = {k: len(v) for k, v in data.items()}
            tot_q = sum(sec_counts.values())
            
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            txt_path = os.path.join(base_dir, "assessment_summary.txt")
            html_path = os.path.join(base_dir, "assessment_summary.html")
            
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"Assessment Summary\n==================\n\nOverview:\nTotal Sections: {len(sec_counts)}\nTotal Questions: {tot_q}\n\nScanned Sections:\n")
                for s, c in sec_counts.items(): f.write(f"- {s}: {c} questions\n")
                f.write("\nQuestions:\n")
                for s, qs in data.items():
                    f.write(f"\n--- {s} ---\n")
                    for q in qs: f.write(f"- {q['id']} | Question: {q['desc']} | Type/Status: {q['status']}\n")
                        
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
        except:
            return {}
