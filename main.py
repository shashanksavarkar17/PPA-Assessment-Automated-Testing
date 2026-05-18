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
    """
    Executes the end-to-end assessment automation flow.
    """
    logger.info("Starting Assessment Automation Flow...")

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
        
        # --- STEP 1: Open Assessment ---
        logger.info(f"Navigating to {settings.BASE_URL}")
        instructions_page.navigate_to(settings.BASE_URL)
        
        # STEP 2: Instructions Page
        logger.info("Executing Step 2: Instructions Page")
        instructions_page.wait_for_page_load()
        instructions_page.validate_heading()
        instructions_page.accept_instructions()
        
        # STEP 3: Login
        logger.info("Executing Step 3: Login")
        login_page.wait_for_page_load()
        login_page.login_with_email(settings.TEST_USER["email"])
        
        # STEP 4: OTP Handling
        logger.info("Executing Step 4: OTP Handling")
        otp_fetcher = YopmailOTPFetcher(driver)
        email_username = settings.TEST_USER["email"].split("@")[0]
        otp_code = otp_fetcher.fetch_latest_otp(username=email_username, timeout=60)
        login_page.enter_otp_and_verify(otp_code)
        
        # STEP 5: Candidate Details
        logger.info("Executing Step 5: Candidate Details")
        details_page.wait_for_page_load()
        details_page.fill_details_and_proceed(
            name=settings.TEST_USER["name"],
            mobile=settings.TEST_USER["mobile"],
            roll_number=settings.TEST_USER["roll_number"]
        )
        
        # STEP 6: Start Test
        logger.info("Executing Step 6: Start Test")
        start_test_page.wait_for_page_load()
        start_test_page.click_start_test()
        
        # STEP 7: Overall Summary Page
        logger.info("Executing Step 7: Summary Page")
        summary_page.wait_for_page_load()
        
        # Scan and dynamically identify sections and question count per section
        section_data = summary_page.scan_sections_and_questions()
        
        # Extract first section details dynamically
        first_section_count = list(section_data.values())[0] if section_data else 2
        logger.info(f"Dynamically determined Section 1 count: {first_section_count} questions.")
        
        # Start Section 1
        summary_page.start_first_section()
        time.sleep(2)
        
        # Traversing questions
        for q_idx in range(1, first_section_count + 1):
            logger.info(f"--- Solving Question {q_idx} of {first_section_count} ---")
            question_page.wait_for_page_load()
            time.sleep(1)
            
            # Detect Question Type
            q_type = question_page.get_question_type()
            q_text = question_page.get_question_text()
            
            if q_type == "MCQ":
                logger.info("Handling MCQ type question...")
                options = question_page.get_mcq_options()
                logger.info(f"Question options found: {options}")
                
                # Solve using Gemini (grounded with web search)
                answer_option = solver.solve_mcq(q_text, options)
                if answer_option:
                    selected = question_page.select_mcq_option(answer_option)
                    if not selected:
                        logger.warning("Exact option match failed. Trying fallback matching...")
                        # Fuzzy match or fallback
                        matched = False
                        for opt in options:
                            if answer_option.lower() in opt.lower() or opt.lower() in answer_option.lower():
                                question_page.select_mcq_option(opt)
                                matched = True
                                break
                        if not matched and options:
                            question_page.select_mcq_option(options[0])
                else:
                    logger.warning("Failed to obtain MCQ answer from LLM. Selecting first option as fallback.")
                    if options:
                        question_page.select_mcq_option(options[0])
                        
                # Click Save & Next
                question_page.click_save_and_next()
                
            elif q_type == "CODING":
                logger.info("Handling Coding type question...")
                
                # Check and click Solve button if present (enters coding workspace)
                question_page.click_solve_if_present()
                
                # Problem details could be re-read after workspace entry
                time.sleep(1.5)
                q_text = question_page.get_question_text()
                
                # Self-healing feedback loop
                max_retries = 3
                current_code = None
                error_msg = None
                
                for attempt in range(max_retries):
                    logger.info(f"Coding attempt {attempt+1} of {max_retries}...")
                    answer_code = solver.solve_coding(q_text, previous_code=current_code, error_message=error_msg)
                    
                    if answer_code:
                        current_code = answer_code
                        question_page.enter_code_solution(answer_code)
                        question_page.submit_code()
                        
                        passed, err = question_page.get_code_result()
                        if passed:
                            logger.info("All testcases passed successfully!")
                            break
                        else:
                            logger.warning(f"Testcase failures detected on attempt {attempt+1}. Error detail: {err}")
                            error_msg = err
                    else:
                        logger.error("Solver returned empty code.")
                        break
                else:
                    logger.error("Failed to solve coding question within the retry limit.")
                    
                # Click Save & Next to proceed
                question_page.click_save_and_next()
                
        # Bring the browser window to the front/foreground so it is visible on your screen
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
