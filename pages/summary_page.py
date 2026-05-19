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

    def start_section(self, section_idx):
        """Click 'Solve' on the section by index (1-based index)."""
        logger.info(f"Attempting to start section {section_idx} dynamically...")
        try:
            self.helpers.wait_for_element(self.SOLVE_BUTTONS_LOCATOR)
            solve_buttons = self.driver.find_elements(*self.SOLVE_BUTTONS_LOCATOR)
            
            if not solve_buttons:
                raise Exception("No 'Solve' buttons found on the page.")
                
            btn_idx = section_idx - 1
            if btn_idx < len(solve_buttons):
                target_button = solve_buttons[btn_idx]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", target_button)
                time.sleep(0.5)
                target_button.click()
                logger.info(f"Successfully started section {section_idx}.")
                return True
            else:
                logger.warning(f"Section index {section_idx} out of range (found {len(solve_buttons)} buttons).")
                return False
        except Exception as e:
            logger.error(f"Failed to start section {section_idx}: {e}")
            self.helpers.take_screenshot(f"start_section_{section_idx}_failed")
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
            
            return section_data
            
        except Exception as e:
            logger.error(f"Error scanning sections and questions: {e}")
            self.helpers.take_screenshot("scan_sections_failed")
            return {}
