import google.generativeai as genai
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class GeminiSolver:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in config/settings.py")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # Try to use gemini-2.0-flash first, fallback to gemini-pro-latest if needed
        self.model_name = 'gemini-2.0-flash'
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"GeminiSolver initialized with {self.model_name}")

    def _generate_content_with_fallback(self, prompt):
        """
        Executes generate_content, falling back to 'gemini-pro-latest' if 'gemini-2.0-flash' is unsupported.
        """
        try:
            return self.model.generate_content(prompt)
        except Exception as e:
            if self.model_name == 'gemini-2.0-flash':
                logger.warning(f"Generation failed with {self.model_name}: {e}. Retrying with 'gemini-pro-latest' fallback...")
                self.model_name = 'gemini-pro-latest'
                self.model = genai.GenerativeModel(self.model_name)
                return self.model.generate_content(prompt)
            else:
                logger.error(f"Generation failed with fallback model {self.model_name}: {e}")
                raise e

    def solve_mcq(self, question_text, options):
        """
        Asks Gemini to solve an MCQ and return the EXACT text of the correct option.
        """
        logger.info("Sending MCQ to Gemini for solving...")
        prompt = f"""
        You are an expert taking a programming assessment.
        Please answer the following Multiple Choice Question.
        
        Question:
        {question_text}
        
        Options:
        """
        for i, option in enumerate(options):
            prompt += f"{i+1}. {option}\n"
            
        prompt += """
        
        Analyze the question and the options.
        IMPORTANT: Your final answer MUST be EXACTLY the text of the correct option from the list above, character for character.
        Do not include option numbers like '1.', 'A.', etc., unless it's part of the text.
        Do not include any explanations. Just the exact text of the correct option.
        """
        
        try:
            response = self._generate_content_with_fallback(prompt)
            answer = response.text.strip()
            logger.info(f"Gemini returned MCQ answer: {answer}")
            return answer
        except Exception as e:
            logger.error(f"Error solving MCQ with Gemini: {e}")
            return None

    def solve_coding(self, problem_statement, previous_code=None, error_message=None):
        """
        Asks Gemini to write C++ code to solve a coding problem.
        If previous_code and error_message are provided, asks it to fix the code.
        """
        logger.info("Sending Coding problem to Gemini for solving (C++)...")
        
        prompt = f"""
        You are an expert competitive programmer.
        Please provide a C++ solution for the following coding problem.
        
        Problem Statement:
        {problem_statement}
        """
        
        if previous_code and error_message:
            prompt += f"""
            
            My previous C++ code failed with the following error/output:
            {error_message}
            
            Previous Code:
            {previous_code}
            
            Please fix the code so it passes all test cases.
            """
            
        prompt += """
        
        IMPORTANT RULES:
        1. Write ONLY the C++ code. No markdown formatting (like ```cpp ... ```).
        2. No explanations, no comments unless absolutely necessary.
        3. Make sure to `#include` necessary libraries like `<iostream>`, `<vector>`, `<algorithm>`, etc.
        4. Include `using namespace std;`.
        5. Provide the full executable code including `int main()`.
        6. Read input from standard input (`cin`) and print output to standard output (`cout`).
        """
        
        try:
            response = self._generate_content_with_fallback(prompt)
            # Clean up any potential markdown code blocks if the LLM disobeys
            code = response.text.strip()
            if code.startswith("```cpp"):
                code = code[6:]
            elif code.startswith("```c++"):
                code = code[6:]
            elif code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
                
            code = code.strip()
            logger.info("Gemini returned C++ Coding solution.")
            return code
        except Exception as e:
            logger.error(f"Error solving Coding problem with Gemini: {e}")
            return None
