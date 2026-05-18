import logging
import sys
from config import settings

def get_logger(name="AutomationLogger"):
    """
    Returns a configured logger instance that logs to both console and a file.
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times if logger is already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Console Handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # File Handler
        fh = logging.FileHandler(settings.LOG_FILE)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger
