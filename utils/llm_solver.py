import os
import random
import re
import time
from openai import OpenAI
from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

class NvidiaNimSolver:
    def __init__(self, driver=None):
        self.driver = driver
        api_key = settings.NVIDIA_API_KEY
        base_url = settings.NVIDIA_NIM_BASE_URL
        self.model_name = settings.NVIDIA_NIM_MODEL
        
        if not api_key:
            log.error("No NVIDIA_API_KEY found in configuration!")
            self.client = None
        else:
            self.client = OpenAI(
                base_url=base_url,
                api_key=api_key
            )
            log.info(f"NvidiaNimSolver successfully initialized with base_url={base_url} and model={self.model_name}")

    def solve_mcq(self, question, options, screenshot_path=None):
        """
        Solve MCQ type questions by selecting a random option.
        """
        log.info("MCQ type question encountered: selecting a random option.")
        if not options:
            return "No options available", None
        ans = random.choice(options)
        return f"Random selection: {ans}", ans

    def solve_coding(self, question, lang="C++", screenshot_path=None, previous_code=None, error_message=None):
        """
        Solve coding type questions. Includes error context for self-healing loops.
        """
        log.info("Coding type question encountered: generating solution via NVIDIA NIM API.")
        if not self.client:
            log.error("NVIDIA NIM API client is not initialized.")
            return self._fallback_code(lang)
            
        try:
            log.info("Applying paced delay: sleeping 4.0 seconds before calling NVIDIA NIM API...")
            time.sleep(4.0)
            prompt = f"Write a complete, valid, and optimal {lang} program to solve this specific problem:\n{question}\n\n"
            prompt += f"Enforce strict boundary: focus exclusively on this target question description. Do not scan, reference, or copy any other questions.\n"
            if previous_code and error_message:
                prompt += (
                    f"CRITICAL: The previous {lang} code failed to match the expected output!\n"
                    f"Error Context / Output Mismatch:\n{error_message}\n\n"
                    f"Previous Code:\n{previous_code}\n\n"
                    f"Please analyze the mismatch carefully, identify the bug in logic or printing format, "
                    f"rectify the error in the code, and return a corrected version that produces the exact expected output."
                )
            
            prompt += "\nReturn ONLY the executable code without any comments, explanation, or markdown syntax wraps (do NOT use ```)."
            
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": f"You are an expert coder. Focus exclusively on writing clean, optimal, executable {lang} code for the current target problem. Do not reference, scan, or copy other questions. Return only raw executable code, no markdown wrappers, explanations, or comments."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2048
            )
            
            code = completion.choices[0].message.content.strip()
            
            # Post-process to strip markdown formatting just in case
            code = re.sub(r'^```[a-zA-Z\+\#]*\n?', '', code, flags=re.I).strip()
            code = re.sub(r'```$', '', code).strip()
            
            log.info(f"Successfully fetched {lang} solution from NVIDIA NIM API.")
            return code
        except Exception as e:
            log.error(f"NVIDIA NIM API call failed: {e}")
            return self._fallback_code(lang)

    def _fallback_code(self, lang):
        if lang.lower() in ["c++", "cpp"]:
            return '#include <iostream>\nusing namespace std;\nint main() {\n    cout << "Hello, World!" << endl;\n    return 0;\n}'
        elif lang.lower() == "python":
            return 'print("Hello, World!")'
        elif lang.lower() == "java":
            return 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, World!");\n    }\n}'
        else:
            return '// Hello World fallback'
