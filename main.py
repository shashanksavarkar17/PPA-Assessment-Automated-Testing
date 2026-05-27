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
        try:
            pages['instructions'].wait_for_page_load()
            pages['instructions'].accept_instructions()
        except Exception as inst_err:
            log.info(f"Skipping instruction page acceptance (already accepted or summary loaded directly): {inst_err}")
        
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
        overall_q_idx = 0
        if section_data:
            sections_to_solve = list(section_data.keys())
        else:
            sections_to_solve = ["Section 1", "Section 2"]
            
        log.info(f"Detected sections to solve: {sections_to_solve}")
        
        for s_idx, section_name in enumerate(sections_to_solve, 1):
            log.info(f"\n==========================================")
            log.info(f"   STARTING SECTION: {section_name} ({s_idx} / {len(sections_to_solve)})")
            log.info(f"==========================================\n")
            
            # Standard summary-driven question traversal for all sections (both coding and MCQ)
            failed_questions = []
            solved_questions_in_section = []
            
            # Initialize solved_questions_in_section from the Summary Page table status
            try:
                rows = driver.find_elements(By.XPATH, "//tr")
                curr_sec = None
                clean_sec_target = pages['summary'].clean_section_name(section_name).lower()
                for r in rows:
                    th = r.find_elements(By.TAG_NAME, "th")
                    if th and "section" in th[0].text.lower():
                        curr_sec = pages['summary'].clean_section_name(th[0].text).lower()
                    elif curr_sec and curr_sec == clean_sec_target:
                        tds = [t.text.strip() for t in r.find_elements(By.TAG_NAME, "td")]
                        if len(tds) >= 3:
                            problem_name = tds[1]
                            status = tds[3].lower() if len(tds) >= 4 else tds[2].lower()
                            if any(w in status for w in ["success", "pass", "attempted", "submitted"]):
                                solved_questions_in_section.append(problem_name)
                log.info(f"Initially identified {len(solved_questions_in_section)} already solved questions in section: {solved_questions_in_section}")
            except Exception as init_err:
                log.warning(f"Could not scan already solved questions initially: {init_err}")
            
            current_q_name = None
            
            while True:
                # 1. Check if we need to enter the section from the Summary page
                # If we are already on a question page, we don't need to go back to Summary page!
                on_question_page = False
                try:
                    if driver.find_elements(By.XPATH, "//*[contains(@class, 'problem') or contains(@class, 'question') or contains(@class, 'editor')]"):
                        on_question_page = True
                except: pass

                if not on_question_page:
                    log.info("Currently on Summary page. Entering section...")
                    pages['summary'].wait_for_page_load()
                    
                    # Check and open the first unsolved question in the current section on the summary page
                    exclude_list = failed_questions + solved_questions_in_section
                    
                    # Pre-load the exact name of the question we are going to start
                    first_unsolved_name = None
                    try:
                        rows = driver.find_elements(By.XPATH, "//tr")
                        curr_sec = None
                        clean_sec_target = pages['summary'].clean_section_name(section_name).lower()
                        for r in rows:
                            th = r.find_elements(By.TAG_NAME, "th")
                            if th and "section" in th[0].text.lower():
                                curr_sec = pages['summary'].clean_section_name(th[0].text).lower()
                            elif curr_sec and curr_sec == clean_sec_target:
                                tds = [t.text.strip() for t in r.find_elements(By.TAG_NAME, "td")]
                                if len(tds) >= 3:
                                    problem_name = tds[1]
                                    status = tds[3].lower() if len(tds) >= 4 else tds[2].lower()
                                    
                                    norm_str = lambda s: "".join(c for c in s.lower() if c.isalnum())
                                    prob_norm = norm_str(problem_name)
                                    is_excluded = False
                                    for ex in exclude_list:
                                        if norm_str(ex) in prob_norm or prob_norm in norm_str(ex):
                                            is_excluded = True
                                            break
                                            
                                    if not is_excluded and not any(w in status for w in ["success", "pass", "attempted", "submitted"]):
                                        first_unsolved_name = problem_name
                                        break
                    except Exception as scan_err:
                        log.warning(f"Could not scan target question name: {scan_err}")
                        
                    started = pages['summary'].start_first_unsolved_in_section(section_name, exclude_names=exclude_list)
                    if started and first_unsolved_name:
                        current_q_name = first_unsolved_name
                        
                    if not started:
                        # Fallback to start_section index if name-based start fails and we haven't started anything yet
                        if not exclude_list:
                            log.warning(f"Could not start section via name '{section_name}'. Trying index-based start...")
                            started = pages['summary'].start_section(s_idx)
                        
                    if not started:
                        log.info(f"All questions in section '{section_name}' successfully processed according to summary page.")
                        break
                        
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
                
                # 2. Now we are definitely on the Question page! Let's solve the current question
                pages['question'].wait_for_page_load()
                
                # Ensure sidebar is closed before attempting the question to prevent overlays
                if pages['question'].is_sidebar_open():
                    pages['question'].close_sidebar()
                time.sleep(0.4)
                
                q_type = pages['question'].get_question_type()
                q_text = pages['question'].get_question_text()
                
                # Derive active question title
                active_q_title = None
                if current_q_name:
                    active_q_title = current_q_name
                else:
                    try:
                        active_q_title = pages['question'].helpers.wait_for_element(
                            (By.XPATH, "//h1 | //h2 | //h3 | //div[contains(@class, 'title') or contains(@class, 'name')]"),
                            timeout=3
                        ).text.strip()
                        if "score" in active_q_title.lower() or len(active_q_title) < 2:
                            active_q_title = None
                    except: pass
                    
                if not active_q_title:
                    if q_text:
                        active_q_title = q_text.splitlines()[0][:50]
                    else:
                        active_q_title = "Question"
                
                overall_q_idx += 1
                log.info(f"Transitioned to Question {overall_q_idx}: '{active_q_title}' (Type: {q_type})")
                
                success = False
                if q_type == 'MCQ':
                    success = _solve_mcq(pages['question'], solver, report, section_name, q_text, overall_q_idx)
                else:
                    success = _solve_coding(pages['question'], solver, report, section_name, q_text, overall_q_idx)
                    
                if not success:
                    log.warning(f"Question '{active_q_title}' failed to resolve. Flagging to prevent retry loop.")
                    failed_questions.append(active_q_title)
                else:
                    log.info(f"Question '{active_q_title}' solved successfully. Tracking to prevent redundant attempts.")
                    solved_questions_in_section.append(active_q_title)

                # 3. Use sidebar navigation to find and switch to the next unsolved question in this section
                log.info("Checking sidebar for next unsolved question in this section...")
                pages['question'].open_sidebar()
                time.sleep(0.5)
                
                # Ensure the correct sidebar accordion section is expanded
                pages['question'].switch_sidebar_section(section_name, s_idx)
                time.sleep(0.5)
                
                sidebar_questions = pages['question'].get_sidebar_questions()
                next_q = None
                
                # Find the first question in the current section that is not solved yet
                for q in sidebar_questions:
                    q_id_name = q['name'].strip()
                    if q['is_solved']:
                        if q_id_name not in solved_questions_in_section:
                            solved_questions_in_section.append(q_id_name)
                        continue
                    
                    # Fuzzy match q_id_name against solved and failed lists
                    norm_str = lambda s: "".join(c for c in s.lower() if c.isalnum())
                    q_norm = norm_str(q_id_name)
                    
                    already_processed = False
                    for processed_q in (solved_questions_in_section + failed_questions):
                        p_norm = norm_str(processed_q)
                        if p_norm in q_norm or q_norm in p_norm:
                            already_processed = True
                            break
                            
                    if already_processed:
                        continue
                        
                    next_q = q
                    break
                
                if next_q:
                    log.info(f"Found next unsolved question in sidebar: Q{next_q['index']} - '{next_q['name']}'")
                    if pages['question'].click_sidebar_question(next_q['index']):
                        current_q_name = next_q['name']
                        # Successfully switched directly to the next question, continue internal loop!
                        continue
                
                # If no next unsolved question exists in this section, return to overall summary
                log.info(f"No further unsolved questions found in sidebar for section '{section_name}'. Returning to summary page...")
                pages['question'].open_sidebar()
                time.sleep(0.3)
                if not pages['question'].click_overall_summary():
                    if not pages['question'].return_to_summary():
                        try: driver.back()
                        except: pass
                time.sleep(1.5)

        report.build_html_dashboard()
        
        # Always submit the final assessment automatically
        log.info("All questions attempted! Submitting final assessment automatically...")
        pages['summary'].submit_assessment()
        time.sleep(1.5)
        report.add_timeline_event("Assessment successfully submitted automatically.")
            
        # Persist consolidated execution telemetry.
        report.build_html_dashboard()

        log.info("Assessment is completely finished. Exiting...")
    except Exception as e:
        log.error(f"Fatal execution crash: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        try:
            report.build_html_dashboard()
        except Exception as rep_err:
            log.warning(f"Could not generate final dashboard in teardown: {rep_err}")
            
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
            "    <title>Generated Assessment Solutions</title>\n"
            "    <style>\n"
            "        body {\n"
            "            font-family: system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;\n"
            "            color: #333333;\n"
            "            background-color: #ffffff;\n"
            "            line-height: 1.5;\n"
            "            margin: 0;\n"
            "            padding: 24px;\n"
            "        }\n"
            "        .container {\n"
            "            max-width: 900px;\n"
            "            margin: 0 auto;\n"
            "        }\n"
            "        header {\n"
            "            border-bottom: 2px solid #eaeaea;\n"
            "            padding-bottom: 16px;\n"
            "            margin-bottom: 24px;\n"
            "        }\n"
            "        h1 {\n"
            "            font-size: 26px;\n"
            "            font-weight: 700;\n"
            "            margin: 0 0 8px 0;\n"
            "            color: #111111;\n"
            "        }\n"
            "        .subtitle {\n"
            "            color: #666666;\n"
            "            font-size: 15px;\n"
            "            margin: 0;\n"
            "        }\n"
            "        section {\n"
            "            border: 1px solid #dddddd;\n"
            "            border-radius: 6px;\n"
            "            padding: 20px;\n"
            "            margin-bottom: 24px;\n"
            "            background-color: #f9f9f9;\n"
            "        }\n"
            "        h2 {\n"
            "            font-size: 18px;\n"
            "            font-weight: 600;\n"
            "            margin: 0 0 12px 0;\n"
            "            color: #222222;\n"
            "            border-bottom: 1px solid #eaeaea;\n"
            "            padding-bottom: 8px;\n"
            "        }\n"
            "        pre {\n"
            "            font-family: Consolas, Monaco, monospace;\n"
            "            background-color: #ffffff;\n"
            "            padding: 12px;\n"
            "            border-radius: 4px;\n"
            "            border: 1px solid #eaeaea;\n"
            "            overflow-x: auto;\n"
            "            margin: 8px 0;\n"
            "            color: #333333;\n"
            "            font-size: 13px;\n"
            "            white-space: pre-wrap;\n"
            "        }\n"
            "        code {\n"
            "            font-family: Consolas, Monaco, monospace;\n"
            "        }\n"
            "        p {\n"
            "            margin: 6px 0;\n"
            "            font-size: 14px;\n"
            "        }\n"
            "        strong {\n"
            "            color: #555555;\n"
            "        }\n"
            "    </style>\n"
            "</head>\n"
            "<body>\n"
            "    <div class=\"container\">\n"
            "        <header>\n"
            "            <h1>Generated Assessment Solutions</h1>\n"
            "            <p class=\"subtitle\">A clean repository of all verified solutions generated during the assessment</p>\n"
            "        </header>\n"
            "        <main>\n"
        )
        for q in solved_questions:
            from html import escape
            q_text_esc = escape(q['q_text'])
            code_esc = escape(q['code'])
            
            html_content += (
                f"            <section>\n"
                f"                <h2>Question {q['q_idx']} ({q['sec_name']})</h2>\n"
                f"                <p><strong>Type/Language:</strong> {q['lang']}</p>\n"
                f"                <p><strong>Status:</strong> COMPLETED</p>\n"
                f"                <p><strong>Question Description:</strong></p>\n"
                f"                <pre>{q_text_esc}</pre>\n"
                f"                <p><strong>Generated Solution / Reasoning:</strong></p>\n"
                f"                <pre><code>{code_esc}</code></pre>\n"
                f"            </section>\n"
            )
        html_content += (
            "        </main>\n"
            "    </div>\n"
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
    
    # Track the MCQ answer in solved_questions list so it logs in generated_answers reports
    solved_questions.append({
        "q_idx": q_idx,
        "sec_name": sec_name,
        "q_text": q_text,
        "lang": "MCQ",
        "code": f"Selected Option: {ans}\n\nReasoning:\n{reasoning}"
    })
    write_generated_answers()
    
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
