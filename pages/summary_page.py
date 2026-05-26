import os
import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

log = get_logger(__name__)

# Page Object representing the final summary dashboard and test submission interface.
class SummaryPage(BasePage):
    def wait_for_page_load(self):
        # Wait for either standard navigation element to render, verifying dashboard load.
        self.helpers.wait_for_element((By.XPATH, "//button[contains(text(), 'Solve') or contains(text(), 'Review')]"))
        
    def clean_section_name(self, raw_name):
        if not raw_name: return ""
        name = raw_name.split("\n")[0].split("Attempted")[0].strip()
        return name

    def start_section(self, section_idx):
        try:
            xpath = "//button | //a"
            candidates = []
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed() and el.is_enabled():
                        text = el.text.lower()
                        if any(kw in text for kw in ["solve", "resume", "start", "attempt", "review", "continue"]):
                            if "overall" not in text and "submit" not in text:
                                if el not in candidates:
                                    candidates.append(el)
                except: pass
                
            log.info(f"Found {len(candidates)} section action buttons on summary page.")
            if not candidates or section_idx - 1 >= len(candidates):
                return False
                
            target_btn = candidates[section_idx - 1]
            log.info(f"Clicking section action button at index {section_idx - 1}: '{target_btn.text}'")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_btn)
            time.sleep(0.2)
            try:
                target_btn.click()
                log.info("Successfully clicked section action button natively.")
            except:
                self.driver.execute_script("arguments[0].click();", target_btn)
                log.info("Clicked section action button via JS.")
            return True
        except Exception as e:
            log.warning(f"Error starting section: {e}")
            return False

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
                            status = tds[3].lower() if len(tds) >= 4 else tds[2].lower()
                            problem_name = tds[1]
                            
                            # We want to solve any question that isn't already solved/passed.
                            if "success" not in status and "pass" not in status:
                                # Find all possible action elements within this row
                                btn_elements = []
                                for xpath in [".//button", ".//a", ".//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'solve') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'resume') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'attempt') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]"]:
                                    for el in r.find_elements(By.XPATH, xpath):
                                        if el and el.is_displayed() and el not in btn_elements:
                                            btn_elements.append(el)
                                
                                # Fallback: last td
                                if not btn_elements:
                                    row_tds = r.find_elements(By.TAG_NAME, "td")
                                    if row_tds:
                                        last_td = row_tds[-1]
                                        btn_elements.extend(last_td.find_elements(By.XPATH, ".//*"))
                                        btn_elements.append(last_td)
                                        
                                for btn in btn_elements:
                                    try:
                                        if btn.is_displayed() and btn.is_enabled():
                                            log.info(f"Opening unsolved question '{problem_name}' (Status: {status}) via element click...")
                                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                            time.sleep(0.2)
                                            try:
                                                btn.click()
                                                log.info("Successfully clicked using Selenium native click.")
                                            except Exception as click_err:
                                                log.warning(f"Native click failed: {click_err}. Trying direct JS click...")
                                                self.driver.execute_script("arguments[0].click();", btn)
                                            return True
                                    except: pass
                except: pass
        except Exception as e:
            log.warning(f"Error starting first unsolved in section: {e}")
        return False

    def scan_sections_and_questions(self):
        try:
            # Query DOM table rows to decode curriculum architecture.
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
                    # Parse details from the row content.
                    tds = [t.text.strip() or "N/A" for t in r.find_elements(By.TAG_NAME, "td")]
                    if len(tds) >= 3:
                        qid = f"Question {tds[0]}" if tds[0].isdigit() else (tds[0] if tds[0] != "N/A" else f"Question {len(data[curr_sec]) + 1}")
                        # Normalize status mapping depending on the available table schema.
                        status = tds[3] if len(tds) >= 4 else tds[2]
                        data[curr_sec].append({"id": qid, "desc": tds[1], "status": status})
            
            sec_counts = {k: len(v) for k, v in data.items()}
            tot_q = sum(sec_counts.values())
            
            from config import settings
            txt_path = os.path.join(settings.REPORTS_DIR, "assessment_summary.txt")
            html_path = os.path.join(settings.REPORTS_DIR, "assessment_summary.html")
            
            # Write formatted assessment statistics to plain text format.
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"Assessment Summary\n==================\n\nOverview:\nTotal Sections: {len(sec_counts)}\nTotal Questions: {tot_q}\n\nScanned Sections:\n")
                for s, c in sec_counts.items(): f.write(f"- {s}: {c} questions\n")
                f.write("\nQuestions:\n")
                for s, qs in data.items():
                    f.write(f"\n--- {s} ---\n")
                    for q in qs: f.write(f"- {q['id']} | Question: {q['desc']} | Type/Status: {q['status']}\n")
            
            # Compile summary dashboard HTML output.
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
            log.warning(f"Failed to scan assessment summary: {e}")
            return {}

    def submit_assessment(self):
        try:
            submit_clicked = False
            for el in self.driver.find_elements(By.XPATH, "//button | //a"):
                if el.is_displayed() and el.is_enabled():
                    text = el.text.lower()
                    if "submit" in text and ("assessment" in text or "test" in text or "final" in text):
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", el)
                        log.info("Clicked the final 'Submit Assessment' button.")
                        submit_clicked = True
                        break
            
            if not submit_clicked:
                log.warning("Could not find the final 'Submit Assessment' button.")
                return False
                
            # Wait for the submit confirmation modal to display.
            log.info("Waiting for the confirmation popup/modal to appear...")
            time.sleep(2.0)
            
            # Query and click the final confirm action inside the active modal.
            for priority_term in ["end test", "end", "confirm", "submit", "yes", "finish"]:
                for el in self.driver.find_elements(By.XPATH, "//button | //a | //input[@type='button']"):
                    if el.is_displayed() and el.is_enabled():
                        text = el.text.strip().lower()
                        if priority_term in text:
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
                            time.sleep(0.5)
                            self.driver.execute_script("arguments[0].click();", el)
                            log.info(f"Clicked the popup confirmation button: '{el.text}'")
                            return True
                            
            log.warning("Could not find popup confirmation button (e.g. 'end test').")
            return True
        except Exception as e:
            log.error(f"Failed to submit assessment: {e}")
            return False
