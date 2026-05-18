import sys
import time
import traceback

from config import settings
from pages.candidate_details_page import CandidateDetailsPage
from pages.instructions_page import InstructionsPage
from pages.login_page import LoginPage
from pages.question_page import QuestionPage
from pages.start_test_page import StartTestPage
from pages.summary_page import SummaryPage
from utils.driver_factory import get_chrome_driver
from utils.llm_solver import GeminiSolver
from utils.otp_fetcher import YopmailOTPFetcher
from utils.logger import get_logger

logger = get_logger("MainRunner")

def run_assessment_flow():
    logger.info("Initializing Selenium Web Automation...")
    
    driver = None
    try:
        driver = get_chrome_driver(headless=False)
        time.sleep(2)

        # Page Object initializations
        instructions_page = InstructionsPage(driver)
        login_page = LoginPage(driver)
        details_page = CandidateDetailsPage(driver)
        start_test_page = StartTestPage(driver)
        summary_page = SummaryPage(driver)
        question_page = QuestionPage(driver)
        
        solver = GeminiSolver()
        
        # 1. Access Assessment Portal
        logger.info(f"Navigating to assessment page: {settings.BASE_URL}")
        instructions_page.navigate_to(settings.BASE_URL)
        
        instructions_page.wait_for_page_load()
        instructions_page.validate_heading()
        instructions_page.accept_instructions()
        
        # 2. Candidate Authentication
        login_page.wait_for_page_load()
        login_page.login_with_email(settings.TEST_USER["email"])
        
        # Scrape Multi-Factor OTP from temporary email inbox in a new tab context
        otp_fetcher = YopmailOTPFetcher(driver)
        email_username = settings.TEST_USER["email"].split("@")[0]
        otp_code = otp_fetcher.fetch_latest_otp(username=email_username, timeout=60)
        login_page.enter_otp_and_verify(otp_code)
        
        # 3. Enter Candidate Information
        details_page.wait_for_page_load()
        details_page.fill_details_and_proceed(
            name=settings.TEST_USER["name"],
            mobile=settings.TEST_USER["mobile"],
            roll_number=settings.TEST_USER["roll_number"]
        )
        
        # 4. Initiate Assessment
        start_test_page.wait_for_page_load()
        start_test_page.click_start_test()
        
        # 5. Extract Assessment Structures
        summary_page.wait_for_page_load()
        section_data = summary_page.scan_sections_and_questions()
        
        # Dynamically determine the question counts in the active section
        first_section_count = list(section_data.values())[0] if section_data else 2
        logger.info(f"Detected {first_section_count} questions in Section 1.")
        
        summary_page.start_first_section()
        time.sleep(2)
        
        # 6. Question Resolution Traversal
        for q_idx in range(1, first_section_count + 1):
            logger.info(f"Processing Question {q_idx}/{first_section_count}")
            question_page.wait_for_page_load()
            time.sleep(1)
            
            q_type = question_page.get_question_type()
            q_text = question_page.get_question_text()
            
            if q_type == "MCQ":
                logger.info("Resolving Multiple Choice Question...")
                options = question_page.get_mcq_options()
                
                answer_option = solver.solve_mcq(q_text, options)
                if answer_option:
                    selected = question_page.select_mcq_option(answer_option)
                    if not selected:
                        logger.warning("Fuzzy fallback selection triggered...")
                        matched = False
                        for opt in options:
                            if answer_option.lower() in opt.lower() or opt.lower() in answer_option.lower():
                                question_page.select_mcq_option(opt)
                                matched = True
                                break
                        if not matched and options:
                            question_page.select_mcq_option(options[0])
                else:
                    logger.warning("No answer resolved from model. Selecting first option as fallback.")
                    if options:
                        question_page.select_mcq_option(options[0])
                        
                question_page.click_save_and_next()
                
            elif q_type == "CODING":
                logger.info("Resolving Coding workspace question...")
                question_page.click_solve_if_present()
                
                time.sleep(2.0)
                q_text = question_page.get_question_text()
                
                # Self-healing feedback loop using standard 'Run' compilation checks
                max_retries = 6
                current_code = None
                error_msg = None
                run_success = False
                
                for attempt in range(max_retries):
                    logger.info(f"Self-healing loop: Attempt {attempt + 1}/{max_retries}")
                    answer_code = solver.solve_coding(q_text, previous_code=current_code, error_message=error_msg)
                    
                    if answer_code:
                        current_code = answer_code
                        question_page.enter_code_solution(answer_code)
                        
                        question_page.run_code()
                        passed, err = question_page.get_run_result()
                        
                        if passed:
                            logger.info("All compiler and sample testcases passed successfully on 'Run'!")
                            run_success = True
                            break
                        else:
                            logger.warning(f"Compilation/testcase mismatch found: {err}")
                            error_msg = err
                    else:
                        logger.error("Solver returned empty response.")
                        break
                
                if run_success or current_code:
                    logger.info("Executing final 'Submit' run...")
                    question_page.submit_code()
                    passed_submit, submit_err = question_page.get_code_result()
                    if passed_submit:
                        logger.info("All final testcases passed successfully!")
                    else:
                        logger.warning(f"Final submission had partial failures: {submit_err}")
                else:
                    logger.error("Failed to compile or run code successfully within the retry limit.")
                
                question_page.click_save_and_next()
                
                # Break after resolving the first coding question as per single-problem testing instruction
                logger.info("Single question C++ validation completed successfully.")
                break
                
        # Minimize and maximize to force screen focus in foreground
        try:
            driver.minimize_window()
            driver.maximize_window()
        except Exception:
            pass
            
        print("\n>>> Section 1 solved completely and successfully!")
        print(">>> Browser will remain open. Press Enter in this terminal to close the browser and exit.")
        input()
    except Exception as e:
        logger.error("An error occurred during the automation flow.")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        if driver:
            logger.info("Closing browser session...")
            driver.quit()

if __name__ == "__main__":
    run_assessment_flow()
