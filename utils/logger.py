import logging
import sys
import os
from config import settings

class ConsoleFormatter(logging.Formatter):
    """Console logging formatter with ANSI color support."""
    GREY = "\033[90m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def format(self, record):
        parts = record.name.split('.')
        short_name = parts[-1] if parts else record.name
        
        if "page" in short_name.lower():
            short_name = short_name.replace("page", "").capitalize() + "Page"
        elif "solver" in short_name.lower():
            short_name = "Solver"
        elif "runner" in short_name.lower() or "main" in short_name.lower():
            short_name = "Runner"
        else:
            short_name = short_name.capitalize()

        name_tag = f"[{short_name}]"
        msg = record.getMessage()

        if len(msg) > 160 or "\n" in msg:
            first_line = msg.split("\n")[0]
            if len(first_line) > 160:
                first_line = first_line[:157] + "..."
            msg = f"{first_line} ... [Text truncated in console - see automation.log]"

        if record.levelno == logging.INFO:
            if any(k in msg.lower() for k in ["success", "complete", "done", "validated", "passed"]):
                prefix = f"{self.GREEN}✔{self.RESET} {self.GREEN}{self.BOLD}{name_tag:<14}{self.RESET}"
            else:
                prefix = f"{self.BLUE}ℹ{self.RESET} {self.BLUE}{name_tag:<14}{self.RESET}"
        elif record.levelno == logging.WARNING:
            prefix = f"{self.YELLOW}⚠{self.RESET} {self.YELLOW}{self.BOLD}{name_tag:<14}{self.RESET}"
        elif record.levelno >= logging.ERROR:
            prefix = f"{self.RED}✖{self.RESET} {self.RED}{self.BOLD}{name_tag:<14}{self.RESET}"
        else:
            prefix = f"{self.GREY}•{self.RESET} {self.GREY}{name_tag:<14}{self.RESET}"

        return f"{prefix} {msg}"

def get_logger(name="AutomationLogger"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_formatter = ConsoleFormatter()
        
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
            
        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except Exception:
                pass
                
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(console_formatter)
        logger.addHandler(ch)
        
        fh = logging.FileHandler(settings.LOG_FILE, encoding='utf-8')
        fh.setFormatter(file_formatter)
        logger.addHandler(fh)
        
    return logger

