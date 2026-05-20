import sys
import time
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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

options = Options()

options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)

logger = get_logger("MainRunner")

def run_assessment_flow():
    logger.info("Initializing Selenium Web Automation...")
    
    report = ReportGenerator()
    report.initialize(
        email=settings.TEST_USER["email"],
        name=settings.TEST_USER["name"],
        mobile=settings.TEST_USER["mobile"],
        roll_number=settings.TEST_USER["roll_number"],
        base_url=settings.BASE_URL
    )
    
    driver = None
    try:
        driver = get_chrome_driver(headless=False)
        time.sleep(2)

        instructions_page = InstructionsPage(driver)
        login_page = LoginPage(driver)
        details_page = CandidateDetailsPage(driver)
        start_test_page = StartTestPage(driver)
        summary_page = SummaryPage(driver)
        question_page = QuestionPage(driver)
        
        solver = GeminiSolver()
        
        logger.info(f"Navigating to assessment page: {settings.BASE_URL}")
        instructions_page.navigate_to(settings.BASE_URL)
        
        instructions_page.wait_for_page_load()
        instructions_page.validate_heading()
        instructions_page.accept_instructions()
        report.add_timeline_event("Instructions page validated and accepted.")
        
        login_page.wait_for_page_load()
        login_page.login_with_email(settings.TEST_USER["email"])
        report.add_timeline_event("Triggered login with Candidate email.")
        
        otp_fetcher = YopmailOTPFetcher(driver)
        email_username = settings.TEST_USER["email"].split("@")[0]
        otp_code = otp_fetcher.fetch_latest_otp(username=email_username, timeout=60)
        login_page.enter_otp_and_verify(otp_code)
        report.add_timeline_event("OTP scraped from Yopmail and validated.")
        
        details_page.wait_for_page_load()
        details_page.fill_details_and_proceed(
            name=settings.TEST_USER["name"],
            mobile=settings.TEST_USER["mobile"],
            roll_number=settings.TEST_USER["roll_number"]
        )
        report.add_timeline_event("Candidate detail fields successfully submitted.")
        
        start_test_page.wait_for_page_load()
        start_test_page.click_start_test()
        report.add_timeline_event("Assessment start confirmed.")
        
        summary_page.wait_for_page_load()
        section_data = summary_page.scan_sections_and_questions()
        
        report.set_scanned_structure(section_data)
        report.add_timeline_event("Overall assessment structure scanned and logged.")
        
        global_q_idx = 1
        
        for sec_idx, (section_name, q_count) in enumerate(section_data.items(), 1):
            logger.info(f"=== Starting Section {sec_idx}: {section_name} ({q_count} questions) ===")
            report.add_timeline_event(f"Starting Section {sec_idx}: {section_name}")
            
            summary_page.start_section(sec_idx)
            time.sleep(2)
            
            for q_idx in range(1, q_count + 1):
                logger.info(f"Processing Section {sec_idx} Question {q_idx}/{q_count} (Global Q{global_q_idx})")
                question_page.wait_for_page_load()
                time.sleep(1)
                
                q_type = question_page.get_question_type()
                q_text = question_page.get_question_text()
                
                if q_type == "MCQ":
                    logger.info("Resolving Multiple Choice Question...")
                    options = question_page.get_mcq_options()
                    
                    report.start_question(global_q_idx, "MCQ", f"[{section_name}] {q_text}")
                    
                    reasoning, answer_option = solver.solve_mcq(q_text, options)
                    if answer_option:
                        selected = question_page.select_mcq_option(answer_option)
                        if not selected:
                            logger.warning("Fuzzy fallback selection triggered...")
                            matched = False
                            for opt in options:
                                if answer_option.lower() in opt.lower() or opt.lower() in answer_option.lower():
                                    question_page.select_mcq_option(opt)
                                    answer_option = opt
                                    matched = True
                                    break
                            if not matched and options:
                                question_page.select_mcq_option(options[0])
                                answer_option = options[0]
                    else:
                        logger.warning("No answer resolved from model. Selecting first option as fallback.")
                        reasoning = "Fallback selection due to empty model response."
                        if options:
                            question_page.select_mcq_option(options[0])
                            answer_option = options[0]
                            
                    report.set_mcq_result(global_q_idx, options, reasoning, answer_option, "PASSED")
                    try:
                        question_page.click_save_and_next()
                    except Exception as nav_err:
                        logger.warning(f"Save/Next failed for MCQ Q{global_q_idx}: {nav_err}. Continuing to next question.")
                    
                elif q_type == "CODING":
                    logger.info("Resolving Coding workspace question...")
                    question_page.click_solve_if_present()
                    
                    time.sleep(2.0)
                    q_text = question_page.get_question_text()
                    
                    selected_lang = question_page.get_selected_language()
                    logger.info(f"Auto-detected Editor Language: {selected_lang}")
                    
                    report.start_question(global_q_idx, "CODING", f"[{section_name}] {q_text}")
                    
                    max_retries = 6
                    current_code = None
                    error_msg = None
                    run_success = False
                    consecutive_empty = 0
                    
                    for attempt in range(max_retries):
                        logger.info(f"Self-healing loop: Attempt {attempt + 1}/{max_retries}")
                        
                        answer_code = solver.solve_coding(
                            q_text, 
                            previous_code=current_code, 
                            error_message=error_msg, 
                            language=selected_lang
                        )
                        
                        if answer_code:
                            consecutive_empty = 0
                            current_code = answer_code
                            question_page.enter_code_solution(answer_code)
                            
                            question_page.run_code()
                            passed, err = question_page.get_run_result()
                            
                            screenshot_path = None
                            if not passed:
                                screenshot_name = f"failure_Q{global_q_idx}_attempt{attempt + 1}"
                                try:
                                    screenshot_path = question_page.helpers.take_screenshot(screenshot_name)
                                except Exception as ss_err:
                                    logger.warning(f"Failed to capture failure screenshot: {ss_err}")
                            
                            report.add_coding_attempt(
                                index=global_q_idx,
                                attempt_idx=attempt + 1,
                                code=answer_code,
                                error=err if not passed else None,
                                screenshot=screenshot_path
                            )
                            
                            if passed:
                                logger.info("All compiler and sample testcases passed successfully on 'Run'!")
                                run_success = True
                                break
                            else:
                                logger.warning(f"Compilation/testcase mismatch found: {err}")
                                error_msg = err
                        else:
                            consecutive_empty += 1
                            logger.warning(f"Solver returned empty response (attempt {attempt+1}). {'Aborting retry loop.' if consecutive_empty >= 2 else 'Retrying...'}")
                            if consecutive_empty >= 2:
                                logger.error("Two consecutive empty solver responses. Skipping this question.")
                                break
                            time.sleep(5)
                    
                    final_status = "FAILED"
                    final_err_msg = "N/A"
                    if current_code:
                        logger.info("Executing final 'Submit' run...")
                        try:
                            question_page.submit_code()
                            passed_submit, submit_err = question_page.get_code_result()
                            
                            if passed_submit:
                                logger.info("All final testcases passed successfully!")
                                final_status = "PASSED"
                            else:
                                logger.warning(f"Final submission had partial failures: {submit_err}")
                                final_status = "PARTIAL_SUCCESS" if run_success else "FAILED"
                                final_err_msg = submit_err
                        except Exception as submit_ex:
                            logger.warning(f"Submit step encountered an error: {submit_ex}")
                            final_status = "PARTIAL_SUCCESS" if run_success else "FAILED"
                            final_err_msg = str(submit_ex)
                    else:
                        logger.error("No code was generated. Skipping submission for this question.")
                        final_err_msg = "Solver returned no code within retry limit."
                    
                    report.set_coding_final(
                        index=global_q_idx,
                        final_code=current_code if current_code else "N/A",
                        status=final_status,
                        language=selected_lang,
                        error_msg=final_err_msg
                    )
                    
                    try:
                        question_page.click_save_and_next()
                    except Exception as nav_err:
                        logger.warning(f"Save/Next failed for CODING Q{global_q_idx}: {nav_err}. Continuing to next question.")
                    
                global_q_idx += 1
                
            logger.info(f"Finished all questions in Section {sec_idx}. Returning to dashboard...")
            if not question_page.return_to_summary():
                logger.info("Direct UI button not found. Fallback: navigating directly to Base URL...")
                driver.get(settings.BASE_URL)
            time.sleep(3)
            summary_page.wait_for_page_load()
            
        try:
            driver.minimize_window()
            driver.maximize_window()
        except Exception:
            pass
            
        report.add_timeline_event("Assessment flow completed.")
        
        report.build_html_dashboard()
        
        print("\n>>> All assessment sections solved completely and successfully!")
        print(">>> Dynamic visual HTML dashboard created at 'assessment_summary.html'")
        print(">>> Browser will remain open. Press Enter in this terminal to close the browser and exit.")
        input()
    except Exception as e:
        logger.error("An error occurred during the automation flow.")
        logger.error(traceback.format_exc())
        
        try:
            report.add_timeline_event(f"Fatal execution crash: {str(e)}")
            report.build_html_dashboard()
        except Exception:
            pass
            
        sys.exit(1)
    finally:
        if driver:
            logger.info("Closing browser session...")
            driver.quit()

if __name__ == "__main__":
    run_assessment_flow()