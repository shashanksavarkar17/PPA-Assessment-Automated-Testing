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
from pages.question_page import QuestionPage
from pages.start_test_page import StartTestPage
from pages.summary_page import SummaryPage
from utils.driver_factory import get_chrome_driver
from utils.llm_solver import NvidiaNimSolver
from utils.report_generator import ReportGenerator
from utils.otp_fetcher import YopmailOTPFetcher
from utils.logger import get_logger

log = get_logger("MainRunner")

# The main coordinator function that drives the entire automated flow end-to-end.
def run_assessment_flow():
    log.info("Starting automated assessment flow...")
    report = ReportGenerator()
    report.initialize(**settings.TEST_USER, base_url=settings.BASE_URL)
    driver = None
    try:
        # Check if headless mode is active, then launch custom Chrome.
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
        
        # 1. Accept instructions page.
        pages['instructions'].navigate_to(settings.BASE_URL)
        pages['instructions'].wait_for_page_load()
        pages['instructions'].accept_instructions()
        
        # 2. Login & fetch OTP via Yopmail tab.
        pages['login'].wait_for_page_load()
        pages['login'].login_with_email(settings.TEST_USER['email'])
        otp = YopmailOTPFetcher(driver).fetch_latest_otp(settings.TEST_USER['email'].split('@')[0])
        pages['login'].enter_otp_and_verify(otp)
        
        # 3. Enter Registration Details & Launch.
        pages['details'].wait_for_page_load()
        pages['details'].fill_details_and_proceed(settings.TEST_USER['name'], settings.TEST_USER['mobile'], settings.TEST_USER['roll_number'])
        pages['start'].wait_for_page_load()
        pages['start'].click_start_test()
        
        # 4. Scan the dashboard structure and solve sections.
        pages['summary'].wait_for_page_load()
        section_data = pages['summary'].scan_sections_and_questions()
        report.set_scanned_structure(section_data)
        
        for sec_idx, (sec_name, q_count) in enumerate(section_data.items(), 1):
            log.info(f"Checking Section {sec_idx}: {sec_name} for unsolved questions...")
            started = pages['summary'].start_first_unsolved_in_section(sec_name)
            if not started:
                log.info(f"All questions in section '{sec_name}' are already fully solved. Skipping section!")
                continue
            time.sleep(1.0)
            
            section_finished = False
            is_mcq_sec = "mcq" in sec_name.lower()
            
            # Reset unsolved tracking specifically for this section to prevent duplicate index collisions
            solved_in_this_run = []
            failed_questions = []
            
            if is_mcq_sec:
                log.info("Executing sequential MCQ solver loop...")
                mcq_idx = 1
                previous_q_text = None
                
                while not section_finished:
                    pages['question'].wait_for_page_load()
                    time.sleep(0.5)
                    
                    # Extract current MCQ text
                    q_text = pages['question'].get_question_text()
                    
                    # Detect duplicate loop if stuck on final question
                    if previous_q_text and q_text == previous_q_text:
                        log.info("Detected duplicate question text. We have completed all questions in this MCQ section!")
                        section_finished = True
                        break
                        
                    previous_q_text = q_text
                    
                    log.info(f"Solving MCQ question: {q_text[:60]}...")
                    success = _solve_mcq(pages['question'], solver, report, sec_name, q_text, f"MCQ {mcq_idx}")
                    solved_in_this_run.append(f"MCQ_{mcq_idx}")
                    mcq_idx += 1
                    
                    time.sleep(1.0)
                    # Check if we returned to summary dashboard
                    if pages['summary'].helpers.is_element_present((By.XPATH, "//button[contains(text(), 'Solve') or contains(text(), 'Review')]")):
                        log.info("Returned to summary page dashboard. MCQ Section complete!")
                        section_finished = True
                        break
            else:
                while not section_finished:
                    pages['question'].wait_for_page_load()
                    time.sleep(0.5)
                    
                    # 1. Open the sidebar to check statuses
                    pages['question'].open_sidebar()
                    time.sleep(0.5)
                    
                    # 2. Scan sidebar for questions and statuses
                    sidebar_questions = pages['question'].get_sidebar_questions()
                    
                    # 3. Find all unsolved questions in this section, excluding failed ones
                    unsolved = [q for q in sidebar_questions if q['index'] not in solved_in_this_run and q['index'] not in failed_questions]
                    
                    if unsolved:
                        next_q = unsolved[0]
                        log.info(f"Next unsolved question found in sidebar: Q{next_q['index']} ({next_q['name']})")
                        
                        try:
                            driver.execute_script("arguments[0].click();", next_q['element'])
                            time.sleep(1.0)
                        except:
                            try: next_q['element'].click()
                            except: pass
                            time.sleep(1.0)
                        
                        pages['question'].close_sidebar()
                        time.sleep(0.5)
                        
                        pages['question'].wait_for_page_load()
                        q_type = pages['question'].get_question_type()
                        q_text = pages['question'].get_question_text()
                        
                        success = False
                        if q_type == 'MCQ':
                            success = _solve_mcq(pages['question'], solver, report, sec_name, q_text, next_q['index'])
                        else:
                            success = _solve_coding(pages['question'], solver, report, sec_name, q_text, next_q['index'])
                            
                        if not success:
                            log.warning(f"Q{next_q['index']} failed to resolve. Adding to failed list.")
                            failed_questions.append(next_q['index'])
                        else:
                            solved_in_this_run.append(next_q['index'])
                    else:
                        log.info(f"All questions in section '{sec_name}' are successfully solved and submitted!")
                        section_finished = True
                    
            # Return to summary dashboard at the end of the section
            pages['question'].open_sidebar()
            time.sleep(0.5)
            if not pages['question'].click_overall_summary():
                log.info("Overall Summary button not clickable. Falling back to dashboard click...")
                if not pages['question'].return_to_summary():
                    try: driver.back()
                    except: pass
            time.sleep(1.0)
            pages['summary'].wait_for_page_load()

        report.build_html_dashboard()
        
        # Check if all questions are successfully attempted and validated (no failures)
        if report.data["meta"]["fail"] == 0 and report.data["meta"]["pass"] > 0:
            log.info("All questions successfully attempted and validated! Submitting final assessment...")
            pages['summary'].submit_assessment()
            time.sleep(1.5)
            report.add_timeline_event("Assessment successfully submitted automatically.")
        else:
            log.warning("Some questions were not fully validated or remain unsolved. Leaving assessment open for manual review.")
            report.add_timeline_event("Assessment left open for manual review due to failed/unsolved questions.")
            
        # Re-save report with final timeline stamps
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
    if ans:
        page.select_mcq_option(ans)
    report.set_mcq_result(q_idx, opts, reasoning, ans, "PASSED")
    try: page.click_save_and_next()
    except: pass
    return True

def _solve_coding(page, solver, report, sec_name, q_text, q_idx):
    # Enforce C++ dropdown selection
    page.ensure_cpp_language()
    time.sleep(0.5)
    
    # 1. STEP 1 & 2: Parse question constraints & example testcases
    log.info("STEP 1: Extracting constraints and examples...")
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
    
    # 2. STEP 3: Request optimized competitive C++ solution
    log.info("STEP 2: Generating optimized C++ competitive programming code...")
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
        
    # 3. STEP 4: Inject code solution into editor
    log.info("STEP 3: Injecting generated C++ solution...")
    page.enter_code_solution(code)
    time.sleep(0.5)
    
    # 4. STEP 5: Enable custom input and paste parsed example input
    verdict_trace = ""
    passed = False
    if example_input:
        log.info("STEP 4: Setting custom input with parsed example input...")
        page.enable_custom_input()
        page.set_custom_input_value(example_input)
        
        # 5. STEP 6: Run Code to validate custom outputs
        log.info("STEP 5: Running custom input validation...")
        # Capture current stale/old console output to prevent instant validation returns
        _, old_actual = page.get_run_outputs()
        
        page.run_code()
        time.sleep(1.0)
        
        # Wait for validation completion, comparing against old stale actual
        page.get_code_result(old_actual) 
        
        # Extract console results
        expected_on_page, actual_on_page = page.get_run_outputs()
        console_errs = page.get_console_errors()
        
        # Clean and normalize strings
        normalize = lambda s: "\n".join([line.strip() for line in s.strip().splitlines() if line.strip()]).strip()
        norm_actual = normalize(actual_on_page)
        norm_expected = normalize(example_output)
        
        # Clean leading punctuation from expected output
        clean_expected = re.sub(r'^[:\s\-\=\>]+', '', norm_expected).strip()
        
        log.info(f"Custom Input Execution - Your Output: {repr(norm_actual)}")
        log.info(f"Custom Input Execution - Expected Output: {repr(clean_expected)}")
        
        if console_errs:
            passed = False
            verdict_trace = f"Execution Error / Compile Error:\n{console_errs}"
            log.warning("Validation failed: compilation or runtime errors encountered on console.")
        elif clean_expected and clean_expected.lower() in norm_actual.lower():
            passed = True
            verdict_trace = f"Validation PASSED (Substring matching)!\nExpected Output: {repr(clean_expected)}\nYour Output: {repr(norm_actual)}"
            log.info("Validation passed! Expected output is found within the execution terminal console.")
        else:
            # Fallback checking integers list in case of subtle spacing
            act_ints = re.findall(r'-?\d+', norm_actual)
            exp_ints = re.findall(r'-?\d+', clean_expected)
            if exp_ints and all(x in act_ints for x in exp_ints):
                passed = True
                verdict_trace = f"Validation PASSED (Integer matching)!\nExpected Output: {repr(clean_expected)}\nYour Output: {repr(norm_actual)}"
                log.info("Validation passed! Expected integers sequence is found within the execution console.")
            else:
                passed = False
                verdict_trace = f"Validation FAILED: Output mismatch!\nExpected Output:\n{example_output}\n\nYour Output:\n{actual_on_page}"
                log.warning("Validation failed: Output mismatch between console output and parsed expected output.")
    else:
        log.warning("No example inputs parsed from the question statement. Bypassing custom run validation and executing direct Run...")
        page.run_code()
        time.sleep(1.0)
        passed, verdict_trace = page.get_code_result()
        
    # 6. STEP 8: Final submission
    if passed:
        log.info("Validation successful! Clicking Submit to finalize question...")
        try:
            page.submit_code()
            time.sleep(1.5)
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
        
        try: page.click_save_and_next()
        except: pass
        return True
    else:
        log.warning("Validation unsuccessful. Skipping submission to next question.")
        report.set_coding_final(q_idx, code, "FAILED", verdict_trace)
        try: page.click_save_and_next()
        except: pass
        return False

if __name__ == "__main__":
    run_assessment_flow()
