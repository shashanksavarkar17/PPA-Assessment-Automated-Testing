import logging, sys, os
from config import settings

class ConsoleFmt(logging.Formatter):
    def format(self, r):
        m = r.getMessage()
        m = f"{m.split('\n')[0][:157]}..." if len(m) > 160 or '\n' in m else m
        p = f"\033[92m✔" if r.levelno == 20 and any(k in m.lower() for k in ["success", "complete", "done", "passed"]) else (f"\033[94mℹ" if r.levelno == 20 else (f"\033[93m⚠" if r.levelno == 30 else f"\033[91m✖"))
        return f"{p}\033[0m \033[1m[{r.name.split('.')[-1][:12]}]\033[0m {m}"

def get_logger(name="Runner"):
    log = logging.getLogger(name)
    if not log.handlers:
        log.setLevel(logging.INFO)
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
            except: pass
        try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except: pass
        
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(ConsoleFmt())
        fh = logging.FileHandler(settings.LOG_FILE, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        log.addHandler(ch); log.addHandler(fh)
    return log
