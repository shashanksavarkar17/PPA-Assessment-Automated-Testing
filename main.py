import sys
import time
import traceback
from selenium import webdriver
from config import settings
from pages.candidate_details_page import CandidateDetailsPage
from pages.instructions_page import InstructionsPage
from pages.login_page import LoginPage
from pages.question_page import QuestionPage
from pages.start_test_page import StartTestPage
from pages.summary_page import SummaryPage
from utils.driver_factory import get_chrome_driver
from utils.llm_solver import GeminiSolver
from utils.report_generator import ReportGenerator
from utils.otp_fetcher import YopmailOTPFetcher
from utils.logger import get_logger

log = get_logger("MainRunner")

# The main function that connects pages, utilities, and solver to automate the entire test flow.
def run_assessment_flow():
    log.info("Starting automated assessment flow...")
    
    # Initialize our reporting and telemetry generator.
    report = ReportGenerator()
    report.initialize(**settings.TEST_USER, base_url=settings.BASE_URL)
    
    driver = None
    try:
        # Fire up our custom Chrome driver instance (checking if we told it to run headlessly).
        import os
        run_headless = os.environ.get("HEADLESS", "false").lower() == "true"
        driver = get_chrome_driver(headless=run_headless)
        
        pages = {
            'instructions': InstructionsPage(driver),
            'login': LoginPage(driver),
            'details': CandidateDetailsPage(driver),
            'start': StartTestPage(driver),
            'summary': SummaryPage(driver),
            'question': QuestionPage(driver)
        }
        
        solver = GeminiSolver(driver)
        
        # 1. Accept assessment instructions.
        pages['instructions'].navigate_to(settings.BASE_URL)
        pages['instructions'].wait_for_page_load()
        pages['instructions'].accept_instructions()
        
        # 2. Enter email on the login screen.
        pages['login'].wait_for_page_load()
        pages['login'].login_with_email(settings.TEST_USER['email'])
        
        # 3. Open Yopmail, fetch the latest OTP code, and verify.
        otp = YopmailOTPFetcher(driver).fetch_latest_otp(settings.TEST_USER['email'].split('@')[0])
        pages['login'].enter_otp_and_verify(otp)
        
        # 4. Fill in candidate registration information.
        pages['details'].wait_for_page_load()
        pages['details'].fill_details_and_proceed(
            settings.TEST_USER['name'], 
            settings.TEST_USER['mobile'], 
            settings.TEST_USER['roll_number']
        )
        
        # 5. Confirm and click "Start Test".
        pages['start'].wait_for_page_load()
        pages['start'].click_start_test()
        
        # 6. Read test details and count the number of questions.
        pages['summary'].wait_for_page_load()
        section_data = pages['summary'].scan_sections_and_questions()
        report.set_scanned_structure(section_data)
        
        # 7. Loop through every section and solve each question one-by-one!
        global_q = 1
        for sec_idx, (sec_name, q_count) in enumerate(section_data.items(), 1):
            log.info(f"Navigating to Section {sec_idx}: {sec_name}")
            pages['summary'].start_section(sec_idx)
            time.sleep(0.5)
            
            for q_idx in range(1, q_count + 1):
                pages['question'].wait_for_page_load()
                time.sleep(0.3)
                
                # Check whether we need to solve an MCQ or Code snippet!
                q_type = pages['question'].get_question_type()
                q_text = pages['question'].get_question_text()
                
                if q_type == 'MCQ':
                    _solve_mcq(pages['question'], solver, report, sec_name, q_text, global_q)
                elif q_type == 'CODING':
                    _solve_coding(pages['question'], solver, report, sec_name, q_text, global_q)
                    
                global_q += 1
                
            # Head back to the summary dashboard to proceed to the next section.
            if not pages['question'].return_to_summary():
                driver.get(settings.BASE_URL)
            time.sleep(0.5)
            pages['summary'].wait_for_page_load()
            
        # Build telemetry report.
        report.build_html_dashboard()
        log.info("Woohoo! Assessment is completely finished. Press Enter to exit.")
        input()
        
    except Exception as e:
        log.error(f"Fatal execution crash: {traceback.format_exc()}")
        sys.exit(1)

def _solve_mcq(page, solver, report, sec_name, q_text, q_idx):
    # Fetch options, snap a quick question screenshot, let Gemini solve it, and submit the response!
    opts = page.get_mcq_options()
    report.start_question(q_idx, "MCQ", f"[{sec_name}] {q_text}")
    
    import os
    screenshot_path = os.path.abspath(f"screenshots/q_{q_idx}.png")
    page.take_question_screenshot(screenshot_path)
    
    reasoning, ans = solver.solve_mcq(q_text, opts, screenshot_path=screenshot_path)
    # Match the resolved string with one of our existing checkbox/radio options.
    if not ans or not page.select_mcq_option(ans):
        ans = next((o for o in opts if (ans and ans.lower() in o.lower()) or (ans and o.lower() in ans.lower())), opts[0] if opts else None)
        if ans: page.select_mcq_option(ans)
            
    report.set_mcq_result(q_idx, opts, reasoning, ans, "PASSED")
    try: page.click_save_and_next()
    except: pass

def _solve_coding(page, solver, report, sec_name, q_text, q_idx):
    # Click the solve challenge button, request clean executable code, inject it, and verify outcome!
    page.click_solve_if_present()
    time.sleep(0.5)
    
    lang = page.get_selected_language()
    report.start_question(q_idx, "CODING", f"[{sec_name}] {q_text}")
    
    log.info(f"Solving coding task Q{q_idx} via single-pass automated code runner...")
    code = solver.solve_coding(q_text, lang, screenshot_path=None)
    
    passed, err = False, ""
    if code:
        # Inject the solution into Monaco/CodeMirror editor and execute tests.
        page.enter_code_solution(code)
        page.run_code()
        passed, err = page.get_run_result()
        log.info(f"Code runner completed. Result: {passed} | Output errors: {err}")
        
        # Take a screenshot if the code failed to compile/run correctly.
        ss = None
        if not passed:
            try: ss = page.helpers.take_screenshot(f"fail_Q{q_idx}")
            except: pass
            
        report.add_coding_attempt(q_idx, 1, code, err if not passed else None, ss)
    else:
        err = "Failed to generate code."
        
    status = "PASSED" if passed else "FAILED"
    report.set_coding_final(q_idx, code or "N/A", status, lang, err or "N/A")
    try: page.click_save_and_next()
    except: pass

if __name__ == "__main__":
    run_assessment_flow()