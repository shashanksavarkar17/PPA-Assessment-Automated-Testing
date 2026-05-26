import os
import sys
import time
import re
import traceback
from datetime import datetime
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

# Main execution coordinator driving the end-to-end automated workflow.
def run_assessment_flow():
    log.info("Starting automated assessment flow...")
    report = ReportGenerator()
    report.initialize(**settings.TEST_USER, base_url=settings.BASE_URL)
    driver = None
    try:
        # Configure headless mode flag and launch custom Chrome instance.
        run_headless = os.environ.get("HEADLESS", "false").lower() == "true"
        driver = get_chrome_driver(headless=run_headless)
        
        pages = {
            'instructions': InstructionsPage(driver), 'login': LoginPage(driver),
            'details': CandidateDetailsPage(driver), 'start': StartTestPage(driver),
            'summary': SummaryPage(driver), 'question': QuestionPage(driver)
        }
        solver = NvidiaNimSolver(driver)
        failed_questions = []
        solved_in_this_run = []
        
        # Phase 1: Consent and instruction acknowledgment.
        pages['instructions'].navigate_to(settings.BASE_URL)
        pages['instructions'].wait_for_page_load()
        pages['instructions'].accept_instructions()
        
        # Phase 2: Candidate login and verification via OTP retrieval.
        pages['login'].wait_for_page_load()
        pages['login'].login_with_email(settings.TEST_USER['email'])
        otp = YopmailOTPFetcher(driver).fetch_latest_otp(settings.TEST_USER['email'].split('@')[0])
        pages['login'].enter_otp_and_verify(otp)
        
        # Phase 3: Registration data entry and test initiation.
        pages['details'].wait_for_page_load()
        pages['details'].fill_details_and_proceed(settings.TEST_USER['name'], settings.TEST_USER['mobile'], settings.TEST_USER['roll_number'])
        pages['start'].wait_for_page_load()
        pages['start'].click_start_test()
        
        # Phase 4: Structural examination and curriculum solving.
        pages['summary'].wait_for_page_load()
        section_data = pages['summary'].scan_sections_and_questions()
        report.set_scanned_structure(section_data)
        
        # Solve all sections sequentially
        if section_data:
            sections_to_solve = list(section_data.keys())
        else:
            sections_to_solve = ["Section 1", "Section 2"]
            
        log.info(f"Detected sections to solve: {sections_to_solve}")
        
        for s_idx, section_name in enumerate(sections_to_solve, 1):
            log.info(f"\n==========================================")
            log.info(f"   STARTING SECTION: {section_name} ({s_idx} / {len(sections_to_solve)})")
            log.info(f"==========================================\n")
            
            # Start the current section to transition to the editor/question view
            pages['summary'].wait_for_page_load()
            
            started = False
            if section_data:
                started = pages['summary'].start_first_unsolved_in_section(section_name)
            
            if not started:
                # Fallback to start_section index if name-based start fails or was not available
                log.warning(f"Could not start section via name '{section_name}'. Trying index-based start...")
                started = pages['summary'].start_section(s_idx)
                
            if not started:
                log.warning(f"Failed to transition into section '{section_name}'. Skipping...")
                continue
                
            log.info("Transition started. Waiting for question page statement to render...")
            try:
                pages['question'].helpers.wait_for_element(
                    (By.XPATH, "//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'editor')]"),
                    timeout=12
                )
                log.info("Question page statement rendered successfully!")
            except Exception as wait_err:
                log.warning(f"Timeout waiting for question page statement: {wait_err}")
            time.sleep(1.0)
            
            solved_in_this_run = []
            failed_questions = []
            
            # Streamlined linear MCQ section handler (bypasses sidebar navigation completely)
            if "multiple choice" in section_name.lower() or "mcq" in section_name.lower():
                log.info(f"Detected MCQ section: '{section_name}'. Starting streamlined linear MCQ solving pipeline...")
                q_idx = 1
                while True:
                    pages['question'].wait_for_page_load()
                    q_type = pages['question'].get_question_type()
                    
                    if q_type != 'MCQ':
                        log.info("Reached non-MCQ viewport or completed MCQ section. Returning to summary...")
                        break
                        
                    q_text = pages['question'].get_question_text()
                    log.info(f"Solving MCQ {q_idx} on screen...")
                    
                    success = _solve_mcq(pages['question'], solver, report, section_name, q_text, q_idx)
                    
                    # Check if next button is disabled (this was the last question)
                    if pages['question'].is_next_button_disabled():
                        log.info("Reached the last MCQ question (Next button is disabled). Gracefully finishing MCQ section solving loop...")
                        break
                        
                    if not success:
                        log.warning(f"MCQ {q_idx} failed to resolve. Clicking Next to skip...")
                        try: pages['question'].click_save_and_next()
                        except: pass
                        
                    q_idx += 1
                    time.sleep(1.5)
            else:
                # Standard sidebar-driven question traversal for coding sections
                while True:
                    pages['question'].wait_for_page_load()
                    
                    # Switch to correct section sidebar elements (e.g. accordion/tab)
                    pages['question'].switch_sidebar_section(section_name)
                    
                    # Open sidebar control panel to inspect active questions list.
                    pages['question'].open_sidebar()
                    time.sleep(0.2)
                    
                    # Scan sidebar structural elements.
                    sidebar_questions = pages['question'].get_sidebar_questions()
                    
                    # Filter all unsolved questions in this section.
                    unsolved = [q for q in sidebar_questions if not q['is_solved'] and q['index'] not in failed_questions and q['index'] not in solved_in_this_run]
                    
                    if unsolved:
                        next_q = unsolved[0]
                        log.info(f"Transitioning to Question {next_q['index']} ({next_q['type']})")
                        
                        try:
                            driver.execute_script("arguments[0].click();", next_q['element'])
                        except:
                            try: next_q['element'].click()
                            except: pass
                        time.sleep(0.6)
                        
                        pages['question'].wait_for_page_load()
                        q_type = pages['question'].get_question_type()
                        q_text = pages['question'].get_question_text()
                        
                        success = False
                        if q_type == 'MCQ':
                            success = _solve_mcq(pages['question'], solver, report, section_name, q_text, next_q['index'])
                        else:
                            success = _solve_coding(pages['question'], solver, report, section_name, q_text, next_q['index'])
                            
                        if not success:
                            log.warning(f"Question {next_q['index']} failed to resolve. Flagging to prevent retry loop.")
                            failed_questions.append(next_q['index'])
                        else:
                            solved_in_this_run.append(next_q['index'])
                    else:
                        log.info(f"All scanned questions in section '{section_name}' successfully processed.")
                        break
                        
                    time.sleep(0.5)
                
            # Navigate back to overall summary dashboard to prepare for the next section.
            pages['question'].open_sidebar()
            time.sleep(0.3)
            if not pages['question'].click_overall_summary():
                if not pages['question'].return_to_summary():
                    try: driver.back()
                    except: pass
            time.sleep(1.5)
            pages['summary'].wait_for_page_load()

        report.build_html_dashboard()
        
        # Final completion validation checking fail threshold.
        if report.data["meta"]["fail"] == 0 and report.data["meta"]["pass"] > 0:
            log.info("All questions successfully attempted and validated! Submitting final assessment...")
            pages['summary'].submit_assessment()
            time.sleep(1.5)
            report.add_timeline_event("Assessment successfully submitted automatically.")
        else:
            log.warning("Some questions were not fully validated or remain unsolved. Leaving assessment open for manual review.")
            report.add_timeline_event("Assessment left open for manual review due to failed/unsolved questions.")
            
        # Persist consolidated execution telemetry.
        report.build_html_dashboard()

        log.info("Assessment is completely finished. Press Enter to exit.")
        input()
    except Exception as e:
        log.error(f"Fatal execution crash: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        if driver:
            try: driver.quit()
            except: pass

solved_questions = []

def write_generated_answers():
    txt_path = os.path.join(settings.REPORTS_DIR, "generated_answers.txt")
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            for q in solved_questions:
                f.write("============================================================\n")
                f.write(f"Question {q['q_idx']} [{q['sec_name']}]\n")
                f.write(f"Language: {q['lang']}\n")
                f.write("------------------------------------------------------------\n")
                f.write(f"Question Text:\n{q['q_text']}\n")
                f.write("------------------------------------------------------------\n")
                f.write(f"Generated Code:\n{q['code']}\n")
                f.write("============================================================\n\n")
        log.info(f"Successfully updated text solutions in: {txt_path}")
    except Exception as e:
        log.warning(f"Error writing plain text solution: {e}")

    html_path = os.path.join(settings.REPORTS_DIR, "generated_answers.html")
    try:
        html_content = (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "    <meta charset=\"UTF-8\">\n"
            "    <title>Generated Coding Solutions</title>\n"
            "</head>\n"
            "<body>\n"
            "    <header>\n"
            "        <h1>Generated Coding Solutions</h1>\n"
            "        <p>A clean repository of all verified solutions generated during assessment</p>\n"
            "    </header>\n"
            "    <main>\n"
        )
        for q in solved_questions:
            from html import escape
            q_text_esc = escape(q['q_text'])
            code_esc = escape(q['code'])
            
            html_content += (
                f"        <section>\n"
                f"            <h2>Question {q['q_idx']} ({q['sec_name']})</h2>\n"
                f"            <p><strong>Language:</strong> {q['lang']}</p>\n"
                f"            <p><strong>Status:</strong> PASSED</p>\n"
                f"            <p><strong>Question Description:</strong></p>\n"
                f"            <pre>{q_text_esc}</pre>\n"
                f"            <p><strong>Generated Solution:</strong></p>\n"
                f"            <pre><code>{code_esc}</code></pre>\n"
                f"        </section>\n"
                "        <hr>\n"
            )
        html_content += (
            "    </main>\n"
            "</body>\n"
            "</html>\n"
        )
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        log.info(f"Successfully updated HTML solutions in: {html_path}")
    except Exception as e:
        log.warning(f"Error writing HTML solution: {e}")

def _solve_mcq(page, solver, report, sec_name, q_text, q_idx):
    opts = page.get_mcq_options()
    report.start_question(q_idx, "MCQ", f"[{sec_name}] {q_text}")
    
    reasoning, ans = solver.solve_mcq(q_text, opts)
    success = False
    if ans:
        success = page.select_mcq_option(ans)
        if success:
            log.info(f"Selected MCQ Option: '{ans}'")
            try:
                page.submit_mcq_answer()
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"Error submitting MCQ answer: {e}")
        else:
            log.warning(f"Failed to click MCQ Option: '{ans}'")
            
    report.set_mcq_result(q_idx, opts, reasoning, ans, "PASSED" if success else "FAILED")
    try: page.click_save_and_next()
    except: pass
    return success

def _solve_coding(page, solver, report, sec_name, q_text, q_idx):
    # Set C++ as the active compiler language.
    page.ensure_cpp_language()
    time.sleep(0.3)
    
    # Step 1: Parse requirements and test cases.
    example_input, example_output = page.get_example_input_output()
    
    constraints = "None specified"
    match_constraints = re.search(r'(?:constraints|limit|range):?\s*\n?(.*?)(?:\n\n|\n[A-Z]|\Z)', q_text, re.IGNORECASE | re.DOTALL)
    if match_constraints:
        constraints = match_constraints.group(1).strip()
        
    report.start_coding_question(
        idx=q_idx,
        title=f"Question {q_idx}",
        text=q_text,
        constraints=constraints,
        example_input=example_input,
        example_output=example_output
    )
    
    # Step 2: Request optimized competitive solution.
    log.info("Requesting C++ solution from NVIDIA NIM API...")
    code = solver.solve_coding(
        question=q_text,
        lang="C++",
        constraints=constraints,
        example_input=example_input,
        example_output=example_output
    )
    if not code:
        log.error("NVIDIA NIM solver returned empty code solution.")
        report.set_coding_final(q_idx, "N/A", "FAILED", "Failed to generate C++ code solution.")
        return False
        
    # Step 3: Inject solution payload into the active editor instance.
    log.info("Injecting generated C++ solution into editor...")
    page.enter_code_solution(code)
    time.sleep(0.5)
    
    # Handle manual execution mode if enabled in settings
    if getattr(settings, "MANUAL_MODE", False):
        log.info("MANUAL MODE active: Code has been injected successfully!")
        print("\n" + "="*80)
        print(">>> MANUAL INTERACTION REQUIRED <<<")
        print(f"Code has been successfully injected for Question {q_idx}.")
        print("Please review the injected code, select custom input (if needed),")
        print("and click 'Run' or 'Submit' in the browser window manually.")
        print("Once you are ready, press [Enter] in this terminal to proceed to the next question...")
        print("="*80 + "\n")
        input("Press [Enter] to continue...")
        
        # Mark as passed manually in report and solutions log
        report.set_coding_final(q_idx, code, "PASSED", "Manually verified and submitted by user.")
        solved_questions.append({
            "q_idx": q_idx,
            "sec_name": sec_name,
            "q_text": q_text,
            "lang": "C++",
            "code": code
        })
        write_generated_answers()
        
        try:
            page.click_save_and_next()
        except Exception as e:
            log.warning(f"Error navigating to next question: {e}")
        return True
    
    # Step 4: Configure custom input data.
    verdict_trace = ""
    passed = False
    if example_input:
        page.enable_custom_input()
        page.set_custom_input_value(example_input)
        
        # Step 5: Execute program with custom inputs.
        log.info("Executing compilability and runtime testcase checks...")
        # Record legacy output to prevent premature validation returns.
        _, old_actual = page.get_run_outputs()
        
        page.run_code()
        time.sleep(0.8)
        
        # Wait for output refresh and validate the result.
        passed, verdict_trace = page.get_code_result(old_actual) 
    else:
        page.run_code()
        time.sleep(0.8)
        passed, verdict_trace = page.get_code_result()
        
    # Step 6: Submit validated solution payload.
    if passed:
        log.info("Submission confirmed: Registering answer.")
        try:
            page.submit_code()
            log.info("Code submitted successfully. Sleeping 8 seconds for evaluation to complete...")
            time.sleep(8.0)
        except Exception as e:
            log.warning(f"Error clicking Submit: {e}")
            
        report.set_coding_final(q_idx, code, "PASSED", verdict_trace)
        solved_questions.append({
            "q_idx": q_idx,
            "sec_name": sec_name,
            "q_text": q_text,
            "lang": "C++",
            "code": code
        })
        write_generated_answers()
        
        try:
            page.click_save_and_next()
            time.sleep(1.0)
        except: pass
        return True
    else:
        log.warning("Validation unsuccessful. Skipping submission.")
        report.set_coding_final(q_idx, code, "FAILED", verdict_trace)
        try: page.click_save_and_next()
        except: pass
        return False

if __name__ == "__main__":
    run_assessment_flow()
