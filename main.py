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
        otp_code = input("\n\n>>> ACTION REQUIRED: Please enter the OTP sent to your email: ")
        login_page.enter_otp_and_verify(otp_code.strip())
        
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
        sections = summary_page.get_all_sections()
        summary_page.start_first_section()
        
        # STEP 8: Answering Questions Loop
        logger.info("Executing Step 8: Answering Questions")
        
        # We will loop infinitely until we can't find a question (e.g., reaching the end of the section)
        # Note: In a real scenario, you'd check for a 'Finish Test' or 'Submit Section' button to break the loop.
        for question_num in range(1, 7): # We saw 6 questions in the screenshot
            logger.info(f"--- Processing Question {question_num} ---")
            question_page.wait_for_page_load()
            
            q_type = question_page.get_question_type()
            q_text = question_page.get_question_text()
            logger.info(f"Question Text: {q_text[:50]}...")
            
            if q_type == "MCQ":
                options = question_page.get_mcq_options()
                logger.info(f"Found {len(options)} options.")
                answer = solver.solve_mcq(q_text, options)
                if answer:
                    question_page.select_mcq_option(answer)
                question_page.click_save_and_next()
            else:
                max_retries = 3
                current_code = None
                error_msg = None
                
                for attempt in range(max_retries):
                    logger.info(f"Attempt {attempt + 1} for Coding Question {question_num}")
                    
                    answer_code = solver.solve_coding(q_text, previous_code=current_code, error_message=error_msg)
                    if answer_code:
                        current_code = answer_code
                        question_page.enter_code_solution(answer_code)
                        question_page.submit_code()
                        
                        passed, err = question_page.get_code_result()
                        if passed:
                            logger.info("Code passed! Proceeding to next question.")
                            question_page.click_save_and_next()
                            break
                        else:
                            error_msg = err
                            logger.warning(f"Code failed. Error: {error_msg}. Retrying...")
                    else:
                        logger.error("Solver failed to return code.")
                        question_page.click_save_and_next()
                        break
                else:
                    logger.error(f"Failed to solve Coding Question {question_num} after {max_retries} attempts.")
                    question_page.click_save_and_next()
            
        logger.info("Automation Flow Completed Successfully!")
        time.sleep(15)
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
