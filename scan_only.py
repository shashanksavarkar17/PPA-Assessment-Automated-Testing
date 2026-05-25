import sys
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import settings
from pages.candidate_details_page import CandidateDetailsPage
from pages.instructions_page import InstructionsPage
from pages.login_page import LoginPage
from pages.start_test_page import StartTestPage
from pages.summary_page import SummaryPage
from pages.question_page import QuestionPage
from utils.driver_factory import get_chrome_driver
from utils.otp_fetcher import YopmailOTPFetcher
from utils.logger import get_logger

log = get_logger("Scanner")

def wait_for_question_text_to_change(page, previous_text):
    if not previous_text:
        return
    log.info("Waiting for question text to change from previous question...")
    start_time = time.time()
    while time.time() - start_time < 5:
        current_text = page.get_question_text()
        if current_text != previous_text and current_text != "Unknown Question":
            log.info("Question text successfully changed.")
            return
        time.sleep(0.5)
    log.warning("Timeout waiting for question text to change. Proceeding anyway.")

def navigate_sidebar(driver, clean_sec_name, q_index_in_section):
    log.info(f"Navigating via sidebar to {clean_sec_name} -> Q{q_index_in_section}")
    q_label = f"Q{q_index_in_section}"
    
    def try_click_q():
        try:
            # Find elements that exactly match "Q1", "Q2", etc.
            q_elements = driver.find_elements(By.XPATH, f"//*[text()='{q_label}' or normalize-space()='{q_label}']")
            for el in q_elements:
                if el.is_displayed() and el.tag_name not in ['script', 'style']:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'}); arguments[0].click();", el)
                    return True
        except: pass
        return False

    if try_click_q(): return True
    
    # If not clicked, section is likely collapsed. Try expanding it.
    log.info(f"Could not see {q_label}, trying to expand section {clean_sec_name}...")
    try:
        sec_elements = driver.find_elements(By.XPATH, f"//*[contains(translate(normalize-space(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{clean_sec_name.upper()}')]")
        for el in sec_elements:
            if el.is_displayed() and el.tag_name not in ['script', 'style']:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'}); arguments[0].click();", el)
                time.sleep(1) # Wait for expansion animation
                break
    except: pass
    
    # Try clicking the question again after expanding
    return try_click_q()

def run_scan():
    log.info("Starting targeted scanning process using sidebar navigation...")
    driver = None
    try:
        driver = get_chrome_driver(headless=False)
        pages = {
            'instructions': InstructionsPage(driver),
            'login': LoginPage(driver),
            'details': CandidateDetailsPage(driver),
            'start': StartTestPage(driver),
            'summary': SummaryPage(driver),
            'question': QuestionPage(driver)
        }
        
        # 1. Login flow
        pages['instructions'].navigate_to(settings.BASE_URL)
        pages['instructions'].wait_for_page_load()
        pages['instructions'].accept_instructions()
        
        pages['login'].wait_for_page_load()
        pages['login'].login_with_email(settings.TEST_USER['email'])
        otp = YopmailOTPFetcher(driver).fetch_latest_otp(settings.TEST_USER['email'].split('@')[0])
        pages['login'].enter_otp_and_verify(otp)
        
        pages['details'].wait_for_page_load()
        pages['details'].fill_details_and_proceed(
            settings.TEST_USER['name'], 
            settings.TEST_USER['mobile'], 
            settings.TEST_USER['roll_number']
        )
        pages['start'].wait_for_page_load()
        pages['start'].click_start_test()
        
        # 2. Get section counts
        pages['summary'].wait_for_page_load()
        section_data = pages['summary'].scan_sections_and_questions()
        log.info(f"Test structure scanned: {section_data}")
        
        scanned_questions = []
        global_q = 1
        
        # 3. Traverse and scan each question
        sections_list = list(section_data.items())
        
        # Start first section to enter the test view where sidebar is present
        if sections_list:
            pages['summary'].start_section(1)
            time.sleep(2.0)
            
        for sec_idx, (sec_name, q_count) in enumerate(sections_list):
            clean_sec_name = sec_name.replace("Section:", "").strip()
            log.info(f"Scanning Section {sec_idx + 1}: {clean_sec_name}")
            
            # If not the first section, use sidebar to navigate to its first question
            if sec_idx > 0:
                navigate_sidebar(driver, clean_sec_name, 1)
                time.sleep(1.0)
            
            prev_text = ""
            for q_idx in range(1, q_count + 1):
                pages['question'].wait_for_page_load()
                time.sleep(0.5)
                
                # Resiliently wait for text to update using local helper
                wait_for_question_text_to_change(pages['question'], prev_text)
                
                q_type = pages['question'].get_question_type()
                q_text = pages['question'].get_question_text()
                
                opts = []
                if q_type == 'MCQ':
                    opts = pages['question'].get_mcq_options()
                    
                q_info = {
                    "id": f"Question {global_q}",
                    "type": q_type,
                    "text": q_text,
                    "section": clean_sec_name,
                    "opts": opts
                }
                scanned_questions.append(q_info)
                prev_text = q_text
                
                log.info(f"Scanned {q_info['id']} in {clean_sec_name} | Type: {q_type}")
                
                # Navigate to next question via sidebar
                if q_idx < q_count:
                    navigate_sidebar(driver, clean_sec_name, q_idx + 1)
                
                global_q += 1
                time.sleep(0.5)
            
        # 4. Generate clean 0-CSS HTML file
        sections = {}
        for q in scanned_questions:
            sec = q.get("section", "General")
            if sec not in sections:
                sections[sec] = []
            sections[sec].append(q)
            
        html_content = "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <title>Scanned Assessment Questions</title>\n</head>\n<body>\n    <header>\n        <h1>Scanned Assessment Questions</h1>\n    </header>\n    <main>\n"
        
        for sec_name, q_list in sections.items():
            html_content += f"        <section>\n            <h2>{sec_name}</h2>\n            <ol>\n"
            for q in q_list:
                q_id = q.get("id", "N/A")
                q_type = q.get("type", "N/A")
                q_text = q.get("text", "N/A")
                
                html_content += f"                <li>\n                    <div>\n                        <h3>{q_id}</h3>\n                        <p><strong>Type:</strong> {q_type}</p>\n                        <p><strong>Description:</strong></p>\n                        <pre>{q_text}</pre>\n"
                
                if q_type == "MCQ" and q.get("opts"):
                    html_content += "                        <p><strong>Options:</strong></p>\n                        <ul>\n"
                    for opt in q["opts"]:
                        html_content += f"                            <li>{opt}</li>\n"
                    html_content += "                        </ul>\n"
                    
                html_content += "                    </div>\n                </li>\n"
            html_content += "            </ol>\n        </section>\n"
            
        html_content += "    </main>\n</body>\n</html>\n"
        
        # Write to files
        filepath = os.path.join(settings.REPORTS_DIR, "scanned_questions.html")
        for _ in range(5):
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html_content)
                log.info(f"Successfully wrote scanned questions HTML to: {filepath}")
                break
            except Exception as e:
                log.warning(f"Error writing to {filepath}: {e}")
                time.sleep(0.5)
                    
        log.info("SCAN COMPLETED SUCCESSFULLY!")
        
    except Exception as e:
        log.error(f"Scanner crashed: {e}")
    finally:
        if driver:
            try: driver.quit()
            except: pass

if __name__ == "__main__":
    run_scan()
