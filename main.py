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
        
        # Scan and dynamically identify sections and question count per section
        summary_page.scan_sections_and_questions()
        
        # Bring the browser window to the front/foreground so it is visible on your screen
        try:
            driver.minimize_window()
            driver.maximize_window()
        except Exception:
            pass
        
        print("\n>>> Overall Summary Page parsed dynamically!")
        print(">>> A downloadable summary has been generated in your workspace: assessment_summary.txt")
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
