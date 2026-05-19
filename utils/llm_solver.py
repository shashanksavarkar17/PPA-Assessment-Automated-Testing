import google.generativeai as genai
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class GeminiSolver:
    """
    Core solving broker connecting to Gemini models for resolving MCQs (grounded with search)
    and Coding questions (with support for self-healing error corrections).
    """
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in config/settings.py")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = 'gemini-2.0-flash'
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"GeminiSolver initialized with {self.model_name}")

    def _generate_content_with_fallback(self, prompt, req_type="coding"):
        import os
        import json
        import time
        
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
            
            logger.warning(f"Local Gemini API call failed: {e}. Activating file-based bridge IPC fallback...")
            
            workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            req_file = os.path.join(workspace_dir, "pending_request.json")
            res_file = os.path.join(workspace_dir, "resolved_response.json")
            
            if os.path.exists(req_file):
                try: os.remove(req_file)
                except Exception: pass
            if os.path.exists(res_file):
                try: os.remove(res_file)
                except Exception: pass
                
            request_data = {
                "type": req_type,
                "prompt": prompt
            }
            try:
                with open(req_file, "w", encoding="utf-8") as f:
                    json.dump(request_data, f, indent=2)
                logger.info(f"Request written to IPC bridge. Waiting for response...")
            except Exception as write_err:
                logger.error(f"Failed to write request file: {write_err}")
                raise e
                
            start_time = time.time()
            while time.time() - start_time < 120:
                if os.path.exists(res_file):
                    try:
                        time.sleep(0.5)
                        with open(res_file, "r", encoding="utf-8") as f:
                            res_data = json.load(f)
                        response_text = res_data.get("response", "").strip()
                        
                        try: os.remove(req_file)
                        except Exception: pass
                        try: os.remove(res_file)
                        except Exception: pass
                        
                        logger.info("Successfully received answer from external solver.")
                        return response_text
                    except Exception as read_err:
                        logger.warning(f"Error reading response file: {read_err}. Retrying...")
                time.sleep(2)
                
            logger.error("Timeout waiting for solver response.")
            raise e

    def _search_web(self, query):
        logger.info(f"DuckDuckGo search: {query}")
        try:
            import urllib.request
            import urllib.parse
            import re

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36'
            }
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
            
            snippets = []
            results = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            for res in results:
                clean_text = re.sub(r'<[^>]+>', '', res)
                clean_text = clean_text.replace('\n', ' ').strip()
                if clean_text:
                    snippets.append(clean_text)
                    if len(snippets) >= 5:
                        break
                        
            snippet_str = "\n".join([f"- {s}" for s in snippets])
            return snippet_str
        except Exception as e:
            logger.warning(f"Web search failed: {e}. Falling back to default Gemini generation.")
            return ""

    def solve_mcq(self, question_text, options):
        search_query = question_text.strip()[:200]
        search_context = self._search_web(search_query)

        logger.info("Sending MCQ to model...")
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
        Provide your reasoning first, and then the exact matching option as your final answer.
        
        You MUST respond strictly in the following format:
        REASONING: <brief step-by-step logic explaining the choice>
        ANSWER: <the exact text of the correct option from the list above, character for character>
        
        Rules:
        1. In the ANSWER field, write ONLY the exact text of the option. Do not prefix with option numbers like '1.', 'A.', etc., unless it's part of the option text itself.
        2. Do not include markdown codeblocks or quotes.
        """
        
        try:
            response = self._generate_content_with_fallback(prompt, req_type="mcq")
            logger.info(f"MCQ Raw Response:\n{response}")
            
            reasoning = "No reasoning provided."
            answer = None
            
            if "REASONING:" in response and "ANSWER:" in response:
                parts = response.split("ANSWER:")
                reasoning = parts[0].replace("REASONING:", "").strip()
                answer = parts[1].strip()
            else:
                # Fallback parser if format was slightly ignored
                lines = [l.strip() for l in response.split("\n") if l.strip()]
                for line in reversed(lines):
                    clean = line.replace("ANSWER:", "").strip()
                    if clean in options:
                        answer = clean
                        break
                if not answer and lines:
                    answer = lines[-1].replace("ANSWER:", "").strip()
                    
            logger.info(f"Parsed MCQ - Reasoning: {reasoning} | Answer: {answer}")
            return reasoning, answer
        except Exception as e:
            logger.error(f"Error solving MCQ: {e}")
            return "Error during MCQ resolution.", None

    def solve_coding(self, problem_statement, previous_code=None, error_message=None, language="C++"):
        logger.info(f"Sending Coding problem to model in language: {language}...")
        
        # Determine language specific guidelines
        lang_lower = language.lower()
        if "python" in lang_lower:
            lang_name = "Python 3"
            lang_rules = """
        1. Write ONLY valid Python 3 code. No markdown formatting (like ```python ... ```).
        2. No explanations, no comments unless absolutely necessary.
        3. Make sure to import necessary standard modules (like `sys`, `collections`, `math`, `heapq`, `bisect` etc.).
        4. Read input from standard input (`sys.stdin`) and print output to standard output (`print()`).
        5. Keep computations fast and optimize algorithms.
            """
        elif "java" in lang_lower:
            lang_name = "Java"
            lang_rules = """
        1. Write ONLY valid Java code. No markdown formatting (like ```java ... ```).
        2. No explanations, no comments unless absolutely necessary.
        3. Make sure to import necessary packages (like `java.util.*`, `java.io.*`).
        4. Provide the full executable class. The class name MUST be `Main` (`public class Main`). Include the `public static void main(String[] args)` method.
        5. Read input from standard input (`Scanner` or `BufferedReader`) and print output to standard output (`System.out.println()`).
            """
        elif "javascript" in lang_lower or "js" in lang_lower:
            lang_name = "JavaScript (Node.js)"
            lang_rules = """
        1. Write ONLY valid JavaScript code. No markdown formatting (like ```javascript ... ```).
        2. No explanations, no comments unless absolutely necessary.
        3. Provide clean, execution-ready Node.js code.
        4. Read input from standard input (`fs.readFileSync(0, 'utf-8')` or standard readline) and print output to standard output (`console.log()`).
            """
        else:  # Default to C++
            lang_name = "C++"
            lang_rules = """
        1. Write ONLY valid C++ code. No markdown formatting (like ```cpp ... ```).
        2. No explanations, no comments unless absolutely necessary.
        3. Make sure to `#include` necessary libraries like `<iostream>`, `<vector>`, `<algorithm>`, `<string>`, `<map>`, `<set>`, `<queue>`, `<cmath>`, `<climits>` etc.
        4. Include `using namespace std;`.
        5. Provide the full executable code including `int main()`.
        6. Read input from standard input (`cin`) and print output to standard output (`cout`).
            """

        prompt = f"""
        You are an expert competitive programmer.
        Please provide a {lang_name} solution for the following coding problem.
        
        Problem Statement:
        {problem_statement}
        """
        
        if previous_code and error_message:
            error_lower = error_message.lower()
            
            # 1. Performance TLE Warning
            if any(term in error_lower for term in ["time limit exceeded", "tle", "timeout", "timed out"]):
                prompt += f"""
                
                ### CRITICAL PERFORMANCE WARNING: TIME LIMIT EXCEEDED (TLE)
                Your previous {lang_name} solution compiled but failed on large test cases because its time complexity was too high.
                You MUST optimize your algorithm's time complexity to be highly optimal (e.g. from O(N^2) or O(2^N) to O(N log N) or O(N)).
                - Avoid nested loops, brute-force recursion, or redundant computations.
                - Utilize optimal data structures like HashMaps, HashSets, Heaps/Priority Queues, Two Pointers, Sliding Window, Prefix Sums, or Binary Search.
                - Use fast I/O libraries if relevant.
                """
            
            # 2. Correctness WA Warning
            elif any(term in error_lower for term in ["wrong answer", "wa", "failed", "mismatch", "expected"]):
                prompt += f"""
                
                ### CRITICAL CORRECTNESS WARNING: WRONG ANSWER (WA) / LOGIC FAIL
                Your previous {lang_name} solution compiled and ran but returned incorrect results for certain validation test cases.
                Please perform a thorough dry-run trace of the algorithm. Pay strict attention to these edge cases:
                - Extremely small, empty, or single-element inputs (e.g., N = 0, N = 1, empty strings).
                - Extremely large boundary inputs (check for potential integer overflow, use `long long` in C++ or big integers).
                - Negative values, zero boundaries, duplicates, or unsorted ranges.
                - Review your index offsets, off-by-one errors, and array out-of-bounds limits.
                """
                
            # 3. Compilation / General Runtime Error Warning
            else:
                prompt += f"""
                
                My previous {lang_name} code failed with the following compilation/runtime error:
                {error_message}
                """
            
            prompt += f"""
            
            Previous Code that failed:
            {previous_code}
            
            Please rewrite and correct the {lang_name} code to pass all test cases successfully.
            """
            
        prompt += f"""
        
        IMPORTANT RULES:
        {lang_rules}
        """
        
        try:
            code = self._generate_content_with_fallback(prompt, req_type="coding")
            
            # Resilient cleaning of markdown backticks for various programming language wrappers
            lang_cleaners = ["cpp", "c++", "python", "py", "java", "javascript", "js", "node"]
            code_cleaned = code.strip()
            for lc in lang_cleaners:
                if code_cleaned.lower().startswith(f"``` {lc}"):
                    code_cleaned = code_cleaned[len(lc) + 4:]
                    break
                elif code_cleaned.lower().startswith(f"```{lc}"):
                    code_cleaned = code_cleaned[len(lc) + 3:]
                    break
            if code_cleaned.startswith("```"):
                code_cleaned = code_cleaned[3:]
            if code_cleaned.endswith("```"):
                code_cleaned = code_cleaned[:-3]
                
            code_cleaned = code_cleaned.strip()
            logger.info(f"Coding solution resolved for {lang_name}.")
            return code_cleaned
        except Exception as e:
            logger.error(f"Error solving Coding problem: {e}")
            return None
