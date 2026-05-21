import os
import random
import re
import google.generativeai as genai
from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

class GeminiSolver:
    def __init__(self, driver=None):
        self.driver = driver
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            log.error("No GEMINI_API_KEY found in configuration!")
        else:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        log.info("GeminiSolver successfully initialized with google-generativeai API.")

    def solve_mcq(self, question, options, screenshot_path=None):
        """
        Solve MCQ type questions by selecting a random option.
        """
        log.info("MCQ type question encountered: selecting a random option.")
        if not options:
            return "No options available", None
        ans = random.choice(options)
        return f"Random selection: {ans}", ans

    def solve_coding(self, question, lang="C++", screenshot_path=None):
        """
        Solve coding type questions by making exactly one API call to write Hello World in C++.
        """
        log.info("Coding type question encountered: generating Hello World in C++ via Gemini API.")
        try:
            prompt = (
                "Write a complete, valid C++ program that prints 'Hello, World!' to standard output. "
                "The program must contain a main function and include necessary libraries. "
                "Return ONLY the executable code without any comments, explanation, or markdown syntax wraps (do NOT use ```cpp or ```)."
            )
            response = self.model.generate_content(prompt)
            code = response.text.strip()
            
            # Post-process to strip markdown formatting just in case
            code = re.sub(r'^```[a-zA-Z\+\#]*\n?', '', code, flags=re.I).strip()
            code = re.sub(r'```$', '', code).strip()
            
            log.info("Successfully fetched C++ Hello World solution from Gemini API.")
            return code
        except Exception as e:
            log.error(f"Gemini API call failed: {e}")
            # Robust fallback C++ program if API call fails
            return '#include <iostream>\nusing namespace std;\nint main() {\n    cout << "Hello, World!" << endl;\n    return 0;\n}'
