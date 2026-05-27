import logging, sys, os

# Custom log formatter for standardized terminal outputs with status indicators and formatting.
class ConsoleFmt(logging.Formatter):
    def format(self, r):
        m = r.getMessage()
        # Truncate multi-line or long messages to maintain clean console output.
        if r.levelno < logging.ERROR and (len(m) > 160 or '\n' in m):
            m = f"{m.splitlines()[0][:157]}..."
        # Maps log levels and keywords to distinct symbols and ANSI colors.
        p = f"\033[92m✔" if r.levelno == 20 and any(k in m.lower() for k in ["success", "complete", "done", "passed"]) else (f"\033[94mℹ" if r.levelno == 20 else (f"\033[93m⚠" if r.levelno == 30 else f"\033[91m✖"))
        return f"{p}\033[0m \033[1m[{r.name.split('.')[-1][:12]}]\033[0m {m}"

def get_logger(name="Runner"):
    log = logging.getLogger(name)
    if not log.handlers:
        log.setLevel(logging.INFO)
        # Enable ANSI escape sequences on Windows console environments.
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
            except: pass
        # Reconfigure standard output encoding to prevent encoding exception crashes.
        try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except: pass
        
        # Direct log streams to standard output.
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(ConsoleFmt())
        log.addHandler(ch)

        # Direct logs to reports/execution_log.txt file
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            reports_dir = os.path.join(base_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            log_path = os.path.join(reports_dir, "execution_log.txt")
            
            # Clear log file on fresh run if initialized by the MainRunner
            mode = "w" if name == "MainRunner" or not os.path.exists(log_path) else "a"
            fh = logging.FileHandler(log_path, mode=mode, encoding="utf-8")
            fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))
            log.addHandler(fh)
        except Exception as e:
            print(f"Failed to add file handler to logger: {e}", file=sys.stderr)
            
    return log
