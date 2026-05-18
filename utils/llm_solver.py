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

    def _generate_content_with_fallback(self, prompt, req_type="coding"):
        """
        Executes generate_content, falling back to a file-based bridge if the API key fails.
        """
        import os
        import json
        import time
        
        # Try local API first
        try:
            res = self.model.generate_content(prompt)
            return res.text.strip()
        except Exception as e:
            if self.model_name == 'gemini-2.0-flash':
                logger.warning(f"Generation failed with {self.model_name}: {e}. Retrying with 'gemini-pro-latest' fallback...")
                try:
                    self.model_name = 'gemini-pro-latest'
                    self.model = genai.GenerativeModel(self.model_name)
                    res = self.model.generate_content(prompt)
                    return res.text.strip()
                except Exception as e2:
                    logger.error(f"Fallback model failed: {e2}")
            
            logger.warning(f"Local Gemini API call failed completely: {e}. Activating file-based bridge fallback...")
            
            # File paths
            workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            req_file = os.path.join(workspace_dir, "pending_request.json")
            res_file = os.path.join(workspace_dir, "resolved_response.json")
            
            # Clean up old files
            if os.path.exists(req_file):
                try: os.remove(req_file)
                except Exception: pass
            if os.path.exists(res_file):
                try: os.remove(res_file)
                except Exception: pass
                
            # Write request
            request_data = {
                "type": req_type,
                "prompt": prompt
            }
            try:
                with open(req_file, "w", encoding="utf-8") as f:
                    json.dump(request_data, f, indent=2)
                logger.info(f"Request written to {req_file}. Waiting for solver resolution...")
            except Exception as write_err:
                logger.error(f"Failed to write request file: {write_err}")
                raise e
                
            # Poll for response (up to 120 seconds)
            start_time = time.time()
            while time.time() - start_time < 120:
                if os.path.exists(res_file):
                    try:
                        # Add a tiny sleep to make sure writing is complete
                        time.sleep(0.5)
                        with open(res_file, "r", encoding="utf-8") as f:
                            res_data = json.load(f)
                        response_text = res_data.get("response", "").strip()
                        
                        # Clean up files
                        try: os.remove(req_file)
                        except Exception: pass
                        try: os.remove(res_file)
                        except Exception: pass
                        
                        logger.info("Successfully received answer from solver.")
                        return response_text
                    except Exception as read_err:
                        logger.warning(f"Error reading response file: {read_err}. Retrying...")
                time.sleep(2)
                
            logger.error("Timeout waiting for solver to resolve request.")
            raise e

    def _search_web(self, query):
        """
        Executes a basic web search on DuckDuckGo Lite / HTML and returns key content snippets.
        """
        logger.info(f"Performing DuckDuckGo search for: {query}")
        try:
            import urllib.request
            import urllib.parse
            import re

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36'
            }
            # Search query URL-encoded
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
            
            # Simple text scraper to extract search result snippets
            snippets = []
            results = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            for res in results:
                # Strip HTML tags
                clean_text = re.sub(r'<[^>]+>', '', res)
                clean_text = clean_text.replace('\n', ' ').strip()
                if clean_text:
                    snippets.append(clean_text)
                    if len(snippets) >= 5:
                        break
                        
            snippet_str = "\n".join([f"- {s}" for s in snippets])
            logger.info("Successfully fetched search snippets.")
            return snippet_str
        except Exception as e:
            logger.warning(f"Web search failed: {e}. Falling back to default Gemini generation.")
            return ""

    def solve_mcq(self, question_text, options):
        """
        Asks Gemini to solve an MCQ and return the EXACT text of the correct option.
        Grounds the model using a DuckDuckGo web search snippet context.
        """
        # Formulate a query using the question text
        search_query = question_text.strip()[:200]
        search_context = self._search_web(search_query)

        logger.info("Sending MCQ to Gemini for solving with web search context...")
        prompt = f"""
        You are an expert taking a programming assessment.
        Please answer the following Multiple Choice Question.
        
        """
        if search_context:
            prompt += f"""
            Below is search engine snippet data from the web regarding this topic:
            {search_context}
            
            """

        prompt += f"""
        Question:
        {question_text}
        
        Options:
        """
        for i, option in enumerate(options):
            prompt += f"{i+1}. {option}\n"
            
        prompt += """
        
        Analyze the question, the options, and any provided web search context.
        IMPORTANT: Your final answer MUST be EXACTLY the text of the correct option from the list above, character for character.
        Do not include option numbers like '1.', 'A.', etc., unless it's part of the option text itself.
        Do not include any explanations. Just the exact text of the correct option.
        """
        
        try:
            answer = self._generate_content_with_fallback(prompt, req_type="mcq")
            logger.info(f"MCQ answer resolved: {answer}")
            return answer
        except Exception as e:
            logger.error(f"Error solving MCQ: {e}")
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
            code = self._generate_content_with_fallback(prompt, req_type="coding")
            # Clean up any potential markdown code blocks if the LLM disobeys
            if code.startswith("```cpp"):
                code = code[6:]
            elif code.startswith("```c++"):
                code = code[6:]
            elif code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
                
            code = code.strip()
            logger.info("Coding solution resolved.")
            return code
        except Exception as e:
            logger.error(f"Error solving Coding problem: {e}")
            return None
