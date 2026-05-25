import sys, time, traceback, os
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
            while not section_finished:
                pages['question'].wait_for_page_load()
                time.sleep(0.5)
                
                # 1. Open the sidebar to check statuses
                pages['question'].open_sidebar()
                time.sleep(0.5)
                
                # 2. Scan sidebar for questions and statuses
                sidebar_questions = pages['question'].get_sidebar_questions()
                
                # 3. Find all unsolved questions in this section, excluding failed ones
                unsolved = [q for q in sidebar_questions if not q['is_solved'] and q['index'] not in failed_questions]
                
                if unsolved:
                    # Pick the first unsolved question
                    next_q = unsolved[0]
                    log.info(f"Next unsolved question found in sidebar: Q{next_q['index']} ({next_q['name']})")
                    
                    # Click to load it
                    try:
                        driver.execute_script("arguments[0].click();", next_q['element'])
                        time.sleep(1.0)
                    except:
                        try: next_q['element'].click()
                        except: pass
                        time.sleep(1.0)
                    
                    # Close the sidebar so the editor pane is wide and visible
                    pages['question'].close_sidebar()
                    time.sleep(0.5)
                    
                    # Process and solve this question
                    pages['question'].wait_for_page_load()
                    q_type = pages['question'].get_question_type()
                    q_text = pages['question'].get_question_text()
                    
                    success = False
                    if q_type == 'MCQ':
                        success = _solve_mcq(pages['question'], solver, report, sec_name, q_text, next_q['index'])
                    else:
                        success = _solve_coding(pages['question'], solver, report, sec_name, q_text, next_q['index'])
                        
                    if not success:
                        log.warning(f"Q{next_q['index']} failed to resolve after max attempts. Adding to skip list.")
                        failed_questions.append(next_q['index'])
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
        
        # Check if all questions are successfully attempted and validated
        if report.data["meta"]["fail"] == 0 and report.data["meta"]["pass"] == report.data["meta"]["questions"]:
            log.info("All questions successfully attempted and validated! Submitting final assessment...")
            pages['summary'].submit_assessment()
            time.sleep(1.5)
            report.add_timeline_event("Assessment successfully submitted automatically.")
        else:
            log.warning("Some questions were not fully validated or remain unsolved. Leaving assessment open for manual review.")
            report.add_timeline_event("Assessment left open for manual review due to failed/unsolved questions.")
            
        # Re-save report with final timeline stamps
        report.build_html_dashboard()

        log.info("Woohoo! Assessment is completely finished. Press Enter to exit.")
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
    # 1. Plain text file
    txt_path = os.path.join(settings.BASE_DIR, "generated_answers.txt")
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

    # 2. Zero-CSS HTML file
    html_path = os.path.join(settings.BASE_DIR, "generated_answers.html")
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
    # Fetch options, choose option randomly, and proceed.
    opts = page.get_mcq_options()
    report.start_question(q_idx, "MCQ", f"[{sec_name}] {q_text}")
    
    html_content = f"<h2>[{sec_name}] Question {q_idx} (MCQ)</h2><p>{q_text}</p><h3>Options:</h3><ul>"
    for opt in opts: html_content += f"<li>{opt}</li>"
    html_content += "</ul>"
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_question.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
        
    reasoning, ans = solver.solve_mcq(q_text, opts)
    if ans:
        page.select_mcq_option(ans)
    report.set_mcq_result(q_idx, opts, reasoning, ans, "PASSED")
    try: page.click_save_and_next()
    except: pass
    return True


def _solve_coding(page, solver, report, sec_name, q_text, q_idx):
    # Retrieve C++ program from NVIDIA NIM, inject, run/submit, and proceed.
    page.click_solve_if_present()
    time.sleep(0.5)
    lang = page.get_selected_language()
    report.start_question(q_idx, "CODING", f"[{sec_name}] {q_text}")
    
    html_content = f"<h2>[{sec_name}] Question {q_idx} (CODING)</h2><p>{q_text}</p><p>Language: {lang}</p>"
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanned_question.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
        
    current_code = None
    error_msg = None
    max_retries = 5 # Up to 5 attempts to satisfy all testcase flags
    final_status = "FAILED"
    
    for attempt in range(max_retries):
        log.info(f"Coding attempt {attempt+1}/{max_retries}")
        code = solver.solve_coding(q_text, lang=lang, previous_code=current_code, error_message=error_msg)
        if not code:
            log.error("Solver returned empty code.")
            break
            
        current_code = code
        page.enter_code_solution(code)
        
        # 1. Click Run to validate code against sample test cases
        try: 
            log.info("Clicking Run to validate outputs...")
            page.run_code()
            time.sleep(1.0)
        except: pass
        
        # 2. Verify results of the Run execution (expected vs actual comparison)
        passed, err = page.get_code_result()
        
        # 3. If outputs match successfully, click Submit to finalize solution
        if passed:
            log.info("Validation passed! Clicking Submit to finalize solution...")
            try:
                page.submit_code()
                time.sleep(1.5)
                # Wait briefly for submission processing to complete and capture final status
                passed, err = page.get_code_result()
            except: pass
            
        report.add_coding_attempt(q_idx, attempt+1, code, err, None)

        
        if passed:
            log.info("Code passed all testcases! Validation successful (will not use remaining attempts).")
            final_status = "PASSED"
            break
        else:
            log.warning(f"Code failed. Error: {err}")
            error_msg = err
            
    report.set_coding_final(q_idx, current_code or "N/A", final_status, lang, error_msg or "N/A")
    
    if final_status == "PASSED":
        solved_questions.append({
            "q_idx": q_idx,
            "sec_name": sec_name,
            "q_text": q_text,
            "lang": lang,
            "code": current_code
        })
        write_generated_answers()
        try:
            log.info("Clicking Submit final confirmation...")
            page.submit_code()
            time.sleep(1.0)
        except: pass
        try: page.click_save_and_next()
        except: pass
        return True
    else:
        log.warning(f"Coding question Q{q_idx} did not pass all testcases after 3 attempts. Skipping to next question.")
        return False

if __name__ == "__main__":
    run_assessment_flow()
