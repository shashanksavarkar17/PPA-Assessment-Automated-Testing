import os
import time
from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from utils.logger import get_logger

logger = get_logger(__name__)

class SummaryPage(BasePage):
    """
    Step 7 - Overall Summary Page
    """

    SECTIONS_LOCATOR = (By.CLASS_NAME, "section-container-class") 
    SOLVE_BUTTONS_LOCATOR = (By.XPATH, "//button[contains(text(), 'Solve')]")
    
    def wait_for_page_load(self):
        logger.info("Waiting for Summary page to load...")
        self.helpers.wait_for_element(self.SOLVE_BUTTONS_LOCATOR)
        
    def get_all_sections(self):
        """Dynamically detect all sections."""
        try:
            sections = self.driver.find_elements(*self.SECTIONS_LOCATOR)
            return sections
        except Exception as e:
            logger.error(f"Failed to detect sections: {e}")
            self.helpers.take_screenshot("detect_sections_failed")
            return []
            
    def start_first_section(self):
        """Click 'Solve' on the first section."""
        logger.info("Attempting to start the first section...")
        try:
            self.helpers.wait_for_element(self.SOLVE_BUTTONS_LOCATOR)
            solve_buttons = self.driver.find_elements(*self.SOLVE_BUTTONS_LOCATOR)
            
            if not solve_buttons:
                raise Exception("No 'Solve' buttons found on the page.")
                
            first_solve_button = solve_buttons[0]
            
            self.driver.execute_script("arguments[0].scrollIntoView(true);", first_solve_button)
            time.sleep(0.5)
            
            first_solve_button.click()
            logger.info("Successfully clicked 'Solve' for the first section.")
            
        except Exception as e:
            logger.error(f"Failed to start the first section: {e}")
            self.helpers.take_screenshot("start_first_section_failed")
            raise e

    def scan_sections_and_questions(self):
        """
        Scans the assessment summary page and structures all sections and questions into text and HTML logs.
        """
        logger.info("Scanning Overall Summary Page...")
        try:
            rows = self.driver.find_elements(By.XPATH, "//tr")
            
            section_questions = {}
            current_section = None
            
            for row in rows:
                th_elements = row.find_elements(By.TAG_NAME, "th")
                if th_elements:
                    for th in th_elements:
                        text = th.text.strip()
                        if "Section:" in text:
                            idx = text.find("Section:")
                            section_name = text[idx:].strip()
                            current_section = section_name
                            section_questions[current_section] = []
                            break
                
                elif current_section:
                    td_elements = row.find_elements(By.TAG_NAME, "td")
                    if td_elements and len(td_elements) >= 3:
                        q_id = td_elements[0].text.strip()
                        if q_id.isdigit():
                            q_id = f"Question {q_id}"
                        elif not q_id:
                            q_id = f"Question {len(section_questions[current_section]) + 1}"
                            
                        q_description = td_elements[1].text.strip() if len(td_elements) > 1 else "N/A"
                        if not q_description:
                            q_description = "N/A"
                            
                        q_status = td_elements[2].text.strip() if len(td_elements) > 2 else "Unknown"
                        if not q_status:
                            q_status = "Unknown"
                            
                        section_questions[current_section].append({
                            "id": q_id,
                            "description": q_description,
                            "status": q_status
                        })
            
            section_data = {sec: len(qs) for sec, qs in section_questions.items()}
            
            print("\n" + "="*45)
            print("              ASSESSMENT SUMMARY")
            print("="*45)
            
            total_questions = 0
            summary_lines = []
            for idx, (section, count) in enumerate(section_data.items(), 1):
                total_questions += count
                line = f"{idx}. {section} - Q {count}"
                print(line)
                summary_lines.append(line)
                
            total_line = f"\nTotal Questions: {total_questions}"
            print(total_line)
            summary_lines.append(total_line)
            print("="*45 + "\n")
            
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # Plaintext summary report
            summary_txt_path = os.path.join(base_dir, "assessment_summary.txt")
            with open(summary_txt_path, "w", encoding="utf-8") as f:
                f.write("="*45 + "\n")
                f.write("              ASSESSMENT SUMMARY\n")
                f.write("="*45 + "\n")
                for line in summary_lines:
                    f.write(line + "\n")
                f.write("="*45 + "\n")
            logger.info(f"Downloadable summary TXT created: {summary_txt_path}")
            
            # Tabular HTML report
            summary_html_path = os.path.join(base_dir, "assessment_summary.html")
            
            total_sections = len(section_questions)
            
            # Build tabular rows dynamically using rowspan for the section details
            table_rows_html = ""
            for s_idx, (section_name, questions) in enumerate(section_questions.items(), 1):
                q_count = len(questions)
                s_num_str = f"{s_idx:02d}"
                
                if q_count == 0:
                    table_rows_html += f"""
            <tr>
                <td style="text-align: center; font-weight: bold;">{s_num_str}</td>
                <td style="font-weight: bold;">{section_name}</td>
                <td style="color: #64748b; text-align: center;">-</td>
                <td style="color: #64748b; font-style: italic;">No questions detected</td>
                <td style="text-align: center;"><span class="badge badge-neutral">N/A</span></td>
            </tr>"""
                else:
                    for q_idx, q in enumerate(questions):
                        # Apply badge coloring based on status
                        status = q["status"]
                        status_class = "badge-neutral"
                        if "attempted" in status.lower() and "not" not in status.lower():
                            status_class = "badge-success"
                        elif "not" in status.lower():
                            status_class = "badge-warning"
                        elif "visited" in status.lower():
                            status_class = "badge-danger"
                        
                        status_badge = f'<span class="badge {status_class}">{status}</span>'
                        
                        # First question row gets the rowspan cells for Section # and Section Name
                        if q_idx == 0:
                            table_rows_html += f"""
            <tr>
                <td rowspan="{q_count}" style="text-align: center; font-weight: bold; vertical-align: middle; background-color: #f8fafc; border-right: 1px solid #e2e8f0;">{s_num_str}</td>
                <td rowspan="{q_count}" style="font-weight: bold; vertical-align: middle; background-color: #f8fafc; border-right: 1px solid #e2e8f0;">
                    {section_name}<br>
                    <span style="font-size: 0.75rem; font-weight: normal; color: #64748b;">({q_count} { 'Question' if q_count == 1 else 'Questions' })</span>
                </td>
                <td style="font-weight: 500;">{q["id"]}</td>
                <td>{q["description"]}</td>
                <td style="text-align: center;">{status_badge}</td>
            </tr>"""
                        else:
                            table_rows_html += f"""
            <tr>
                <td style="font-weight: 500; border-left: none;">{q["id"]}</td>
                <td>{q["description"]}</td>
                <td style="text-align: center;">{status_badge}</td>
            </tr>"""
            
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Assessment Summary</title>
    <style>
        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #f8fafc;
            color: #1e293b;
            padding: 2.5rem 1.5rem;
            margin: 0;
            line-height: 1.5;
        }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 2.5rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
        }}

        header {{
            margin-bottom: 2rem;
            border-bottom: 2px solid #f1f5f9;
            padding-bottom: 1.5rem;
        }}

        h1 {{
            font-size: 2rem;
            font-weight: 800;
            color: #0f172a;
            margin: 0 0 0.5rem 0;
            letter-spacing: -0.025em;
        }}

        .subtitle {{
            color: #64748b;
            font-size: 1rem;
            margin: 0;
        }}

        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 1.25rem 1.5rem;
        }}

        .stat-label {{
            font-size: 0.8rem;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }}

        .stat-value {{
            font-size: 1.85rem;
            font-weight: 700;
            color: #0f172a;
        }}

        /* Table Styling */
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            margin-top: 1.5rem;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow: hidden;
        }}

        th {{
            background-color: #f1f5f9;
            color: #334155;
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 1rem 1.25rem;
            border-bottom: 2px solid #e2e8f0;
        }}

        td {{
            padding: 1rem 1.25rem;
            border-bottom: 1px solid #e2e8f0;
            font-size: 0.9rem;
            color: #334155;
            vertical-align: top;
        }}

        tr:hover td {{
            background-color: #f8fafc;
        }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }}

        .badge-success {{
            background-color: #d1fae5;
            color: #065f46;
            border: 1px solid #a7f3d0;
        }}

        .badge-warning {{
            background-color: #fef3c7;
            color: #92400e;
            border: 1px solid #fde68a;
        }}

        .badge-danger {{
            background-color: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }}

        .badge-neutral {{
            background-color: #e2e8f0;
            color: #334155;
            border: 1px solid #cbd5e1;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 1.5rem;
            }}
            table, thead, tbody, th, td, tr {{
                display: block;
            }}
            thead {{
                display: none;
            }}
            tr {{
                border-bottom: 2px solid #e2e8f0;
                margin-bottom: 1rem;
            }}
            td {{
                border: none;
                padding: 0.5rem 0;
            }}
            td::before {{
                content: attr(data-label);
                font-weight: bold;
                display: block;
                color: #64748b;
                font-size: 0.75rem;
                text-transform: uppercase;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Assessment Summary</h1>
            <p class="subtitle">Complete tabular overview of detected sections, questions, and descriptions</p>
        </header>

        <section class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Sections</div>
                <div class="stat-value">{total_sections}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Questions</div>
                <div class="stat-value">{total_questions}</div>
            </div>
        </section>

        <table>
            <thead>
                <tr>
                    <th style="width: 10%; text-align: center;">Section #</th>
                    <th style="width: 30%;">Section Name</th>
                    <th style="width: 15%;">Question #</th>
                    <th style="width: 33%;">Question Description</th>
                    <th style="width: 12%; text-align: center;">Status</th>
                </tr>
            </thead>
            <tbody>
                {table_rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
            with open(summary_html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"Downloadable summary HTML created successfully at: {summary_html_path}")
            
            return section_data
            
        except Exception as e:
            logger.error(f"Error scanning sections and questions: {e}")
            self.helpers.take_screenshot("scan_sections_failed")
            return {}
