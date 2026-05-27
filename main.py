import os
import sys
import time
import re
import traceback
from selenium.webdriver.common.by import By

from config import settings
from pages.candidate_details_page import CandidateDetailsPage
from pages.instructions_page import InstructionsPage
from pages.login_page import LoginPage
from pages.start_test_page import StartTestPage
from pages.summary_page import SummaryPage
from pages.question_page import QuestionPage
from utils.driver_factory import get_chrome_driver
from utils.llm_solver import NvidiaNimSolver
from utils.report_generator import ReportGenerator
from utils.otp_fetcher import YopmailOTPFetcher
from utils.logger import get_logger

log = get_logger("MainRunner")

def run_assessment_flow():
    log.info("Starting automated assessment flow...")
    report = ReportGenerator()
    report.initialize(**settings.TEST_USER, base_url=settings.BASE_URL)
    driver = None
    try:
        run_headless = os.environ.get("HEADLESS", "false").lower() == "true"
        driver = get_chrome_driver(headless=run_headless)
        
        pages = {
            'instructions': InstructionsPage(driver), 'login': LoginPage(driver),
            'details': CandidateDetailsPage(driver), 'start': StartTestPage(driver),
            'summary': SummaryPage(driver), 'question': QuestionPage(driver)
        }
        solver = NvidiaNimSolver(driver)
        
        # Phase 1: Acknowledge instructions
        pages['instructions'].navigate_to(settings.BASE_URL)
        try:
            pages['instructions'].wait_for_page_load()
            pages['instructions'].accept_instructions()
        except Exception as e:
            log.info(f"Skipped instructions (already accepted): {e}")
        
        # Phase 2: Candidate login & OTP retrieval
        pages['login'].wait_for_page_load()
        pages['login'].login_with_email(settings.TEST_USER['email'])
        otp = YopmailOTPFetcher(driver).fetch_latest_otp(settings.TEST_USER['email'].split('@')[0])
        pages['login'].enter_otp_and_verify(otp)
        
        # Phase 3: Details & Start Test
        pages['details'].wait_for_page_load()
        pages['details'].fill_details_and_proceed(settings.TEST_USER['name'], settings.TEST_USER['mobile'], settings.TEST_USER['roll_number'])
        pages['start'].wait_for_page_load()
        pages['start'].click_start_test()
        
        # Phase 4: Scan and Solve
        pages['summary'].wait_for_page_load()
        section_data = pages['summary'].scan_sections_and_questions()
        report.set_scanned_structure(section_data)
        
        sections_to_solve = list(section_data.keys()) if section_data else ["Section 1", "Section 2"]
        log.info(f"Sections to solve: {sections_to_solve}")
        
        overall_q_idx = 0
        norm_str = lambda s: "".join(c for c in s.lower() if c.isalnum())
        
        for s_idx, section_name in enumerate(sections_to_solve, 1):
            log.info(f"\n==========================================\n  STARTING SECTION: {section_name}\n==========================================\n")
            failed_questions = []
            solved_questions_in_section = []
            
            while True:
                on_question_page = len(driver.find_elements(By.XPATH, "//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'editor')]")) > 0
                if not on_question_page:
                    pages['summary'].wait_for_page_load()
                    exclude_list = failed_questions + solved_questions_in_section
                    started = pages['summary'].start_first_unsolved_in_section(section_name, exclude_names=exclude_list)
                    if not started:
                        log.info(f"Section '{section_name}' successfully processed according to summary page.")
                        break
                    time.sleep(1.0)
                
                pages['question'].wait_for_page_load()
                if pages['question'].is_sidebar_open():
                    pages['question'].close_sidebar()
                time.sleep(0.4)
                
                q_type = pages['question'].get_question_type()
                q_text = pages['question'].get_question_text()
                
                active_q_title = q_text.splitlines()[0][:50] if q_text else "Question"
                overall_q_idx += 1
                log.info(f"Q{overall_q_idx}: '{active_q_title}' (Type: {q_type})")
                
                success = False
                if q_type == 'MCQ':
                    success = _solve_mcq(pages['question'], solver, report, section_name, q_text, overall_q_idx)
                else:
                    success = _solve_coding(pages['question'], solver, report, section_name, q_text, overall_q_idx)
                    
                if not success:
                    failed_questions.append(active_q_title)
                else:
                    solved_questions_in_section.append(active_q_title)

                # Try to navigate using the sidebar directly to next unsolved question in section
                pages['question'].open_sidebar()
                time.sleep(0.5)
                pages['question'].switch_sidebar_section(section_name, s_idx)
                time.sleep(0.5)
                
                sidebar_questions = pages['question'].get_sidebar_questions()
                next_q = None
                for q in sidebar_questions:
                    if q['is_solved']:
                        if q['name'] not in solved_questions_in_section:
                            solved_questions_in_section.append(q['name'])
                        continue
                    
                    if not any(norm_str(x) in norm_str(q['name']) or norm_str(q['name']) in norm_str(x) for x in (solved_questions_in_section + failed_questions)):
                        next_q = q
                        break
                
                if next_q:
                    log.info(f"Direct switch to Q{next_q['index']} - '{next_q['name']}'")
                    if pages['question'].click_sidebar_question(next_q['index']):
                        continue
                
                log.info("No further unsolved questions in this section. Returning to summary...")
                pages['question'].open_sidebar()
                time.sleep(0.3)
                if not pages['question'].click_overall_summary() and not pages['question'].return_to_summary():
                    try: driver.back()
                    except: pass
                time.sleep(1.5)

        log.info("Submitting final assessment...")
        pages['summary'].submit_assessment()
        time.sleep(1.5)
        report.add_timeline_event("Assessment successfully submitted.")
        report.build_html_dashboard()
    except Exception as e:
        log.error(f"Fatal execution crash: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        try: report.build_html_dashboard()
        except: pass
        if driver:
            try: driver.quit()
            except: pass

def _solve_mcq(page, solver, report, sec_name, q_text, q_idx):
    opts = page.get_mcq_options()
    report.start_question(q_idx, "MCQ", f"[{sec_name}] {q_text}")
    reasoning, ans = solver.solve_mcq(q_text, opts)
    success = False
    if ans:
        success = page.select_mcq_option(ans)
        if success:
            try:
                page.submit_mcq_answer()
                time.sleep(0.5)
            except: pass
    report.set_mcq_result(q_idx, opts, reasoning, ans, "PASSED" if success else "FAILED")
    try: page.click_save_and_next()
    except: pass
    return success

def _solve_coding(page, solver, report, sec_name, q_text, q_idx):
    page.ensure_cpp_language()
    time.sleep(0.3)
    
    example_input, example_output = page.get_example_input_output()
    constraints = "None specified"
    match = re.search(r'(?:constraints|limit|range):?\s*\n?(.*?)(?:\n\n|\n[A-Z]|\Z)', q_text, re.IGNORECASE | re.DOTALL)
    if match:
        constraints = match.group(1).strip()
        
    report.start_coding_question(q_idx, f"Question {q_idx}", q_text, constraints, example_input, example_output)
    
    log.info("Requesting C++ solution...")
    code = solver.solve_coding(q_text, "C++", constraints, example_input, example_output)
    if not code:
        report.set_coding_final(q_idx, "N/A", "FAILED", "Failed to generate C++ code solution.")
        return False
        
    page.enter_code_solution(code)
    time.sleep(0.5)
    
    if getattr(settings, "MANUAL_MODE", False):
        print(f"\n>>> MANUAL INTERACTION REQUIRED: Q{q_idx} code injected. <<<\n")
        input("Submit manually in browser, then press [Enter] here to continue...")
        report.set_coding_final(q_idx, code, "PASSED", "Manually verified by user.")
        try: page.click_save_and_next()
        except: pass
        return True
    
    passed = False
    verdict = ""
    if example_input:
        page.enable_custom_input()
        page.set_custom_input_value(example_input)
        _, old_actual = page.get_run_outputs()
        page.run_code()
        passed, verdict = page.get_code_result(old_actual)
    else:
        page.run_code()
        passed, verdict = page.get_code_result()
        
    if passed:
        try:
            page.submit_code()
            time.sleep(8.0)
        except: pass
        report.set_coding_final(q_idx, code, "PASSED", verdict)
        try:
            page.click_save_and_next()
            time.sleep(1.0)
        except: pass
        return True
    else:
        report.set_coding_final(q_idx, code, "FAILED", verdict)
        try: page.click_save_and_next()
        except: pass
        return False

if __name__ == "__main__":
    run_assessment_flow()
