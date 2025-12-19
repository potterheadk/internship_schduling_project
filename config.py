"""
config.py - Centralized Configuration & Constants

Manages all application-level paths, constants, and environment variables
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==============================================================================
# DIRECTORY PATHS
# ==============================================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# ==============================================================================
# DATA FILE PATHS (NEW SCHEDULER)
# ==============================================================================
SCHEDULES_FILE = os.path.join(DATA_DIR, 'final_schedular_correct.csv')
CLASSROOMS_FILE = os.path.join(DATA_DIR, 'classrooms.csv')
LEGACY_LABS_FILE = os.path.join(DATA_DIR, 'lab_backend.csv')
CYCLES_FILE = os.path.join(DATA_DIR, 'ciclo2025.csv')

# ==============================================================================
# OUTPUT FILE PATHS
# ==============================================================================
OUTPUT_SCHEDULE_FILE = os.path.join(OUTPUT_DIR, 'final_schedule.csv')
OUTPUT_REPORT_FILE = os.path.join(OUTPUT_DIR, 'scheduling_report.txt')
CONFLICT_REPORT_FILE = os.path.join(OUTPUT_DIR, 'conflict_analysis_report.txt')
DEBUG_LOG_FILE = os.path.join(LOGS_DIR, 'scheduler_debug.log')

# ==============================================================================
# SCHEDULING CONSTANTS
# ==============================================================================
LAB_KEYWORDS = ['LABORATORIO', 'LAB']
PRESENTIAL_KEYWORDS = ['PRESENCIAL', 'PRACTICA', 'TEORIA']
VIRTUAL_KEYWORD = 'VIRTUAL'
UNASSIGNED_PHRASE = 'SIN AULA ASIGNADA'
LAB_ROOM_TYPE_CODE = 'LB'
CLASSROOM_TYPE_CODES = ['CL', 'AU', 'SP', 'MR']
TEACHER_ID_COLUMN = 'c_dnidoc'
DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

# ==============================================================================
# FLASK CONFIGURATION
# ==============================================================================
FLASK_SECRET_KEY = 'your_very_secret_key_change_me_in_production'
FLASK_HOST = '127.0.0.1'
FLASK_PORT = 5000
FLASK_DEBUG = False

# ==============================================================================
# GEMINI API CONFIGURATION
# ==============================================================================
GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY', '')

# Check if Gemini is available
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.DEBUG

def setup_logger(name=None):
    """
    Setup logger with console and file handlers.
    
    Args:
        name (str): Logger name. If None, returns root logger
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name or __name__)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(LOG_LEVEL)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console_handler)
    
    # File handler (only for root logger to avoid duplication)
    if name is None:
        file_handler = logging.FileHandler(DEBUG_LOG_FILE)
        file_handler.setLevel(LOG_LEVEL)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(file_handler)
    
    return logger


# Initialize root logger on import
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(DEBUG_LOG_FILE)
    ]
)

logger = setup_logger()
logger.info("=" * 80)
logger.info("🚀 SCHEDULER APPLICATION CONFIGURATION LOADED")
logger.info(f"Debug logs: {DEBUG_LOG_FILE}")
logger.info("=" * 80)
