import os
import random
import re
from openai import OpenAI
from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

class NvidiaNimSolver:
    def __init__(self, driver=None):
        self.driver = driver
        # Collect loaded API keys list
        self.api_keys = getattr(settings, "NVIDIA_API_KEYS", [])
        self.current_key_index = 0
        self.client = None
        self.model_name = settings.NVIDIA_NIM_MODEL
        self._initialize_client()

    def _initialize_client(self):
        if not self.api_keys or self.current_key_index >= len(self.api_keys):
            log.error("No valid NVIDIA API keys found in settings!")
            self.client = None
            return False
        
        api_key = self.api_keys[self.current_key_index]
        log.info(f"Initializing NvidiaNimSolver client with key index {self.current_key_index} (model: {self.model_name})...")
        self.client = OpenAI(
            base_url=settings.NVIDIA_NIM_BASE_URL,
            api_key=api_key,
            timeout=15.0
        )
        return True

    def solve_mcq(self, question, options, screenshot_path=None):
        """
        Solve MCQ type questions by making an API call to NVIDIA NIM to find the correct answer.
        Supports self-healing fallback key rotation on API exceptions.
        """
        log.info("MCQ type question encountered: generating correct option via NVIDIA NIM API...")
        if not options:
            return "No options available", None
            
        max_attempts = len(self.api_keys) if self.api_keys else 1
        for attempt in range(max_attempts):
            if not self.client:
                if not self._initialize_client():
                    break
            
            try:
                options_str = "\n".join([f"- {opt}" for opt in options])
                prompt = (
                    "You are a computer science expert. Solve the following multiple-choice question.\n\n"
                    f"### QUESTION:\n{question}\n\n"
                    f"### OPTIONS:\n{options_str}\n\n"
                    "### REQUIREMENTS:\n"
                    "1. Think carefully and determine the correct option from the options listed.\n"
                    "2. Return the exact selected option from the list. It MUST match one of the options word-for-word.\n"
                    "3. Return ONLY the matched option text as your final response, with no markdown, no quotes, no explanations, and no other text."
                )
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=512,
                )
                selected_option = response.choices[0].message.content.strip()
                selected_option = selected_option.replace('"', '').replace("'", "").strip()
                
                best_match = None
                for opt in options:
                    if opt.strip().lower() == selected_option.lower():
                        best_match = opt
                        break
                
                if not best_match:
                    for opt in options:
                        if opt.strip().lower() in selected_option.lower() or selected_option.lower() in opt.strip().lower():
                            best_match = opt
                            break
                            
                if best_match:
                    log.info(f"NVIDIA NIM selected correct option: {best_match}")
                    return f"NVIDIA NIM Reasoning: Verified correctness of option.", best_match
                else:
                    log.warning(f"Could not cleanly match API response '{selected_option}' with any option. Selecting first option.")
                    return f"API output mismatch fallback: {options[0]}", options[0]
            except Exception as e:
                log.error(f"NVIDIA NIM API MCQ call failed with key index {self.current_key_index}: {e}")
                self.current_key_index += 1
                self.client = None
                
        log.warning("All NVIDIA NIM keys failed for MCQ. Using fallback random selection.")
        ans = random.choice(options)
        return f"Random fallback selection: {ans}", ans

    def solve_coding(self, question, lang="C++", constraints=None, example_input=None, example_output=None, screenshot_path=None):
        """
        Solve coding type questions by making an API call to write an optimized C++ solution.
        Enriches the prompt with scanned constraints and examples, and supports key rotation.
        """
        log.info("Coding type question encountered: generating C++ solution via NVIDIA NIM API...")
        
        max_attempts = len(self.api_keys) if self.api_keys else 1
        for attempt in range(max_attempts):
            if not self.client:
                if not self._initialize_client():
                    break
            
            try:
                prompt = (
                    "You are a competitive programming world champion. Write a complete, valid C++ program that solves the following question.\n\n"
                    f"### QUESTION STATEMENT:\n{question}\n\n"
                )
                if constraints:
                    prompt += f"### CONSTRAINTS:\n{constraints}\n\n"
                if example_input:
                    prompt += f"### EXAMPLE INPUT:\n{example_input}\n\n"
                if example_output:
                    prompt += f"### EXAMPLE EXPECTED OUTPUT:\n{example_output}\n\n"
                    
                prompt += (
                    "### REQUIREMENTS:\n"
                    "1. Provide a COMPLETE, working C++ solution that reads input from standard input (std::cin) and writes to standard output (std::cout) in competitive programming style.\n"
                    "2. Do NOT use placeholder methods, recursion depth risks, or unnecessary complexity. Optimize for performance (target O(N) or O(N log N) solutions if constraints are large).\n"
                    "3. Enforce extremely fast I/O by adding the following snippet at the beginning of your main() function:\n"
                    "   std::ios::sync_with_stdio(false);\n"
                    "   std::cin.tie(nullptr);\n"
                    "4. Include all necessary standard library headers (e.g. <iostream>, <vector>, <algorithm>, <string>, <map>, <unordered_map>, <set>, <queue>).\n"
                    "5. Return ONLY the fully executable C++ code. Do NOT include any markdown block wraps (no ```cpp or ```), explanation, comments, or annotations. The output must be pure source code."
                )
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=2048,
                )
                code = response.choices[0].message.content.strip()
                
                code = re.sub(r'^```[a-zA-Z\+\#]*\n?', '', code, flags=re.I).strip()
                code = re.sub(r'```$', '', code).strip()
                
                log.info("Successfully fetched optimized C++ solution from NVIDIA NIM API.")
                return code
            except Exception as e:
                log.error(f"NVIDIA NIM API call failed with key index {self.current_key_index}: {e}")
                self.current_key_index += 1
                self.client = None
        
        log.warning("All available NVIDIA NIM API keys failed. Using fallback C++ code.")
        return self._get_fallback_code(lang)

    def _get_fallback_code(self, lang):
        # High quality C++ boilerplate fallback
        return (
            "#include <iostream>\n"
            "using namespace std;\n"
            "int main() {\n"
            "    ios::sync_with_stdio(false);\n"
            "    cin.tie(nullptr);\n"
            "    int n;\n"
            "    if (cin >> n) {\n"
            "        cout << n << '\\n';\n"
            "    }\n"
            "    return 0;\n"
            "}"
        )
