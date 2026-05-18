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
        Dynamically scans the Overall Summary Page.
        Identifies:
        - How many sections are present.
        - How many questions are in each section.
        - Total questions in the assessment.
        Prints a summary in the terminal.
        """
        logger.info("Scanning Overall Summary Page dynamically...")
        try:
            # Locate all table rows in the summary table
            rows = self.driver.find_elements(By.XPATH, "//tr")
            
            section_data = {}
            current_section = None
            
            for row in rows:
                # Check for section header cells
                th_elements = row.find_elements(By.TAG_NAME, "th")
                if th_elements:
                    # Look for cell with "Section:" text
                    for th in th_elements:
                        text = th.text.strip()
                        if "Section:" in text:
                            # Extract section name
                            idx = text.find("Section:")
                            section_name = text[idx:].strip()
                            current_section = section_name
                            section_data[current_section] = 0
                            break
                
                # Check for question rows (only count if we are inside a section)
                elif current_section:
                    td_elements = row.find_elements(By.TAG_NAME, "td")
                    # A question row must contain cells
                    if td_elements:
                        cell_texts = [td.text.strip() for td in td_elements if td.text.strip()]
                        if cell_texts and len(td_elements) >= 3:
                            section_data[current_section] += 1
            
            # Print the formatted summary in the terminal
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
            
            # Generate a downloadable summary file in the workspace base directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            summary_file_path = os.path.join(base_dir, "assessment_summary.txt")
            with open(summary_file_path, "w", encoding="utf-8") as f:
                f.write("="*45 + "\n")
                f.write("              ASSESSMENT SUMMARY\n")
                f.write("="*45 + "\n")
                for line in summary_lines:
                    f.write(line + "\n")
                f.write("="*45 + "\n")
                
            logger.info(f"Downloadable summary file created successfully at: {summary_file_path}")
            return section_data
            
        except Exception as e:
            logger.error(f"Error scanning sections and questions: {e}")
            self.helpers.take_screenshot("scan_sections_failed")
            return {}
