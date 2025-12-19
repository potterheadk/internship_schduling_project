"""
chatbot_logic.py - Intelligent Router & Tool Architecture

THREE-LAYER ARCHITECTURE:
Layer 1: The Semantic Router (Gemini) - Classifies intent & extracts fuzzy entities
Layer 2: The Tool Belt (Python/Pandas) - Executes lookups, availability checks, reports
Layer 3: The Synthesizer (Gemini) - Translates raw data into natural language
"""

import pandas as pd
import os
import logging
import json
from datetime import datetime, timedelta

# Gemini LLM imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Fuzzy matching import
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

# Additional imports for improvements
import unicodedata
import re
import time
from functools import wraps


# ==============================================================================
# UTILITY FUNCTIONS FOR FUZZY MATCHING & NAME NORMALIZATION
# ==============================================================================

def normalize_name(name):
    """
    Normalize a name for fuzzy matching.
    - Remove accents (é→e, ñ→n)
    - Standardize to title case
    - Strip whitespace
    """
    if not name:
        return ""
    
    # Remove accents using unicode normalization
    name = unicodedata.normalize('NFKD', str(name))
    name = name.encode('ASCII', 'ignore').decode('utf-8')
    
    # Standardize case and strip
    name = name.strip().title()
    
    # Remove extra spaces
    name = ' '.join(name.split())
    
    return name


def sanitize_input(text, max_length=500):
    """
    Sanitize user input.
    - Remove control characters
    - Limit length
    - Normalize whitespace
    """
    if not text:
        return ""
    
    # Remove control characters
    text = re.sub(r'[\x00-\x1F\x7F]', '', str(text))
    
    # Check length
    if len(text) > max_length:
        text = text[:max_length]
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text.strip()


def find_best_fuzzy_match(query, candidates, threshold=70):
    """
    Find the best fuzzy match for a query in a list of candidates.
    
    Args:
        query (str): Search query
        candidates (list): List of candidate strings
        threshold (int): Minimum score (0-100) to consider a match
        
    Returns:
        tuple: (best_match, score) or (None, 0) if no match
    """
    if not RAPIDFUZZ_AVAILABLE or not candidates:
        return None, 0
    
    best_match = None
    best_score = 0
    
    for candidate in candidates:
        if not candidate or pd.isna(candidate):
            continue
        
        # Try partial ratio (better for substring matches)
        score = fuzz.partial_ratio(
            normalize_name(query).lower(),
            normalize_name(str(candidate)).lower()
        )
        
        if score > best_score:
            best_score = score
            best_match = candidate
    
    if best_score >= threshold:
        return best_match, best_score
    
    return None, best_score


def find_all_fuzzy_matches(query, candidates, threshold=50, limit=5):
    """
    Find all fuzzy matches for a query above threshold.
    
    Args:
        query (str): Search query
        candidates (list): List of candidate strings
        threshold (int): Minimum score (0-100)
        limit (int): Maximum number of results
        
    Returns:
        list: [(match, score), ...] sorted by score descending
    """
    if not RAPIDFUZZ_AVAILABLE or not candidates:
        return []
    
    matches = []
    
    for candidate in candidates:
        if not candidate or pd.isna(candidate):
            continue
        
        score = fuzz.partial_ratio(
            normalize_name(query).lower(),
            normalize_name(str(candidate)).lower()
        )
        
        if score >= threshold:
            matches.append((candidate, score))
    
    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return matches[:limit]


# ==============================================================================
# LOGGING SETUP
# ==============================================================================

def setup_chatbot_logger(log_file=None):
    """Setup logger with console and file handlers."""
    logger = logging.getLogger('ScheduleChatbot')
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        '%(asctime)s [BOT] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s [BOT] %(levelname)s: %(message)s'
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not setup file logging: {e}")
    
    return logger


# ==============================================================================
# ENTITY NORMALIZER - Maps user input to database format
# ==============================================================================

class EntityNormalizer:
    """Normalize user inputs to match database values."""
    
    # Day names mapping (supports both Spanish and English)
    DAY_MAP = {
        'monday': 'Monday', 'lunes': 'Monday',
        'tuesday': 'Tuesday', 'martes': 'Tuesday',
        'wednesday': 'Wednesday', 'miércoles': 'Wednesday', 'miercoles': 'Wednesday',
        'thursday': 'Thursday', 'jueves': 'Thursday',
        'friday': 'Friday', 'viernes': 'Friday',
        'saturday': 'Saturday', 'sábado': 'Saturday', 'sabado': 'Saturday',
        'sunday': 'Sunday', 'domingo': 'Sunday',
        'tomorrow': None,  # Special case - will be calculated
        'mañana': None
    }
    
    @classmethod
    def get_day(cls, text):
        """Normalize day name to English format (used in new scheduler)."""
        if not text:
            return None
        
        text_lower = str(text).lower().strip()
        
        # Handle special cases
        if text_lower in ['tomorrow', 'mañana']:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%A').lower()
            return cls.DAY_MAP.get(tomorrow)
        
        return cls.DAY_MAP.get(text_lower)
    
    @classmethod
    def get_room_type(cls, text):
        """Detect if user wants Lab or Classroom."""
        if not text:
            return None
        
        text_lower = str(text).lower()
        
        if 'lab' in text_lower or 'laboratory' in text_lower or 'laboratorio' in text_lower:
            return 'LB'
        
        if 'class' in text_lower or 'aula' in text_lower or 'classroom' in text_lower:
            return 'CL'
        
        return None
    
    @classmethod
    def parse_time_range(cls, time_str):
        """Parse time string to start and end times."""
        if not time_str:
            return None, None
        
        time_raw = str(time_str).strip()

        # Normalize common separators for ranges
        for sep in ['–', '—', ' to ', ' hasta ', ' hasta ', ' a ']:
            if sep in time_raw and '-' not in time_raw:
                time_raw = time_raw.replace(sep, '-')

        def parse_single(tstr):
            tstr = tstr.strip()
            # Try pandas to_datetime which uses dateutil and is flexible (handles '2pm', '14:00', '2:00 pm')
            try:
                parsed = pd.to_datetime(tstr, errors='coerce')
                if not pd.isna(parsed):
                    return parsed.time()
            except Exception:
                pass

            # Try adding minutes if missing (e.g., '14' -> '14:00')
            try:
                if ':' not in tstr and any(c.isdigit() for c in tstr):
                    parsed = pd.to_datetime(tstr + ':00', errors='coerce')
                    if not pd.isna(parsed):
                        return parsed.time()
            except Exception:
                pass

            return None

        try:
            # Range format
            if '-' in time_raw:
                parts = time_raw.split('-')
                if len(parts) >= 2:
                    start_str = parts[0].strip()
                    end_str = parts[1].strip()
                    start_time = parse_single(start_str)
                    end_time = parse_single(end_str)
                    return start_time, end_time

            # Single time -> assume 90-minute block
            single = parse_single(time_raw)
            if single:
                temp_dt = datetime.combine(datetime.today(), single) + timedelta(minutes=90)
                return single, temp_dt.time()

            return None, None

        except Exception:
            return None, None
    
    @classmethod
    def validate_query_length(cls, query, max_length=500):
        """Validate query length."""
        if not query:
            return False, "Query is empty"
        
        if len(query) > max_length:
            return False, f"Query too long ({len(query)} chars). Max: {max_length}"
        
        return True, "OK"


# ==============================================================================
# CONFLICT REPORT PARSER - Extracts conflict data from report file
# ==============================================================================

class ConflictReportParser:
    """Parse and cache conflict data from conflict_analysis_report.txt"""
    
    def __init__(self, report_file=None):
        """Initialize the parser with report file path."""
        self.report_file = report_file
        self.report_data = {}
        self.teacher_conflicts = {}
        self.room_conflicts = {}
        self.overall_stats = {}
        self.parsed = False
        
        if report_file and os.path.exists(report_file):
            self.parse_report()
    
    def parse_report(self):
        """Parse the conflict analysis report file."""
        try:
            if not os.path.exists(self.report_file):
                return False
            
            with open(self.report_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract overall statistics
            self._parse_statistics(content)
            
            # Extract teacher conflicts
            self._parse_teacher_conflicts(content)
            
            # Extract room conflicts
            self._parse_room_conflicts(content)
            
            self.parsed = True
            return True
            
        except Exception as e:
            logging.getLogger('ScheduleChatbot').error(f"Error parsing conflict report: {e}")
            return False
    
    def _parse_statistics(self, content):
        """Extract overall statistics from report."""
        try:
            # Extract dataset statistics section
            stats_section = content.split('CONFLICT ANALYSIS')[0]
            
            # Parse key metrics
            import re
            
            patterns = {
                'total_classes': r'Total Classes:\s+(\d+)',
                'assigned_rooms': r'Assigned Rooms:\s+(\d+)',
                'unassigned_rooms': r'Unassigned Rooms:\s+(\d+)',
                'unique_rooms': r'Unique Rooms:\s+(\d+)',
                'unique_teachers': r'Unique Teachers:\s+(\d+)',
                'teacher_conflicts': r'Teacher Conflicts:\s+(\d+)',
                'room_conflicts': r'Room Conflicts:\s+(\d+)',
                'total_conflicts': r'Total Conflicts:\s+(\d+)',
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, stats_section)
                if match:
                    self.overall_stats[key] = int(match.group(1))
            
        except Exception as e:
            logging.getLogger('ScheduleChatbot').debug(f"Error parsing statistics: {e}")
    
    def _parse_teacher_conflicts(self, content):
        """Extract teacher conflicts from report."""
        try:
            import re
            
            # Find teacher conflicts section
            if 'DETAILED TEACHER CONFLICTS' not in content:
                return
            
            teacher_section = content.split('DETAILED TEACHER CONFLICTS')[1]
            
            # Stop at room conflicts section if it exists
            if 'DETAILED ROOM CONFLICTS' in teacher_section:
                teacher_section = teacher_section.split('DETAILED ROOM CONFLICTS')[0]
            
            # Parse individual conflicts
            # Pattern: "1. Teacher: <id>\n   Day: <day>\n   Conflict:\n   • <course> at <time> in <room>"
            
            current_teacher = None
            current_day = None
            
            for line in teacher_section.split('\n'):
                line = line.strip()
                
                # Match teacher line (with or without number prefix like "1.")
                if 'Teacher:' in line:
                    # Extract teacher ID after "Teacher:"
                    parts = line.split('Teacher:')
                    if len(parts) > 1:
                        current_teacher = parts[1].strip()
                        if current_teacher not in self.teacher_conflicts:
                            self.teacher_conflicts[current_teacher] = []
                
                # Match day line
                elif line.startswith('Day:'):
                    current_day = line.replace('Day:', '').strip()
                
                # Match conflict course line
                elif line.startswith('•') and current_teacher:
                    conflict_text = line.replace('•', '').strip()
                    
                    self.teacher_conflicts[current_teacher].append({
                        'day': current_day,
                        'conflict': conflict_text
                    })
            
        except Exception as e:
            logging.getLogger('ScheduleChatbot').debug(f"Error parsing teacher conflicts: {e}")
    
    def _parse_room_conflicts(self, content):
        """Extract room conflicts from report."""
        try:
            import re
            
            # Find room conflicts section
            if 'DETAILED ROOM CONFLICTS' not in content:
                return
            
            room_section = content.split('DETAILED ROOM CONFLICTS')[1]
            
            current_room = None
            current_day = None
            
            for line in room_section.split('\n'):
                line = line.strip()
                
                # Match room line
                if line.startswith('Room:'):
                    current_room = line.replace('Room:', '').strip()
                    if current_room not in self.room_conflicts:
                        self.room_conflicts[current_room] = []
                
                # Match day line
                elif line.startswith('Day:'):
                    current_day = line.replace('Day:', '').strip()
                
                # Match conflict course line
                elif line.startswith('•') and current_room:
                    conflict_text = line.replace('•', '').strip()
                    
                    self.room_conflicts[current_room].append({
                        'day': current_day,
                        'conflict': conflict_text
                    })
            
        except Exception as e:
            logging.getLogger('ScheduleChatbot').debug(f"Error parsing room conflicts: {e}")
    
    def get_teacher_conflicts(self, teacher_name):
        """Get conflicts for a specific teacher."""
        if teacher_name in self.teacher_conflicts:
            return self.teacher_conflicts[teacher_name]
        
        # Try fuzzy match if exact match fails
        from rapidfuzz import fuzz
        
        best_match = None
        best_score = 0
        
        for stored_teacher in self.teacher_conflicts.keys():
            score = fuzz.ratio(teacher_name.lower(), stored_teacher.lower())
            if score > best_score:
                best_score = score
                best_match = stored_teacher
        
        if best_match and best_score > 60:
            return self.teacher_conflicts[best_match]
        
        return []
    
    def get_room_conflicts(self, room_name):
        """Get conflicts for a specific room."""
        if room_name in self.room_conflicts:
            return self.room_conflicts[room_name]
        
        # Try fuzzy match if exact match fails
        from rapidfuzz import fuzz
        
        best_match = None
        best_score = 0
        
        for stored_room in self.room_conflicts.keys():
            score = fuzz.ratio(room_name.lower(), stored_room.lower())
            if score > best_score:
                best_score = score
                best_match = stored_room
        
        if best_match and best_score > 60:
            return self.room_conflicts[best_match]
        
        return []
    
    def get_overall_stats(self):
        """Get overall statistics."""
        return self.overall_stats


# ==============================================================================
# MAIN CHATBOT CLASS - Router & Tools Architecture
# ==============================================================================

class ScheduleChatbot:
    """
    Intelligent Schedule Assistant with three-layer architecture.
    
    Layer 1: Router (Gemini) - Intent detection + entity extraction
    Layer 2: Tools (Python) - Execution (lookup, availability, reports)
    Layer 3: Synthesizer (Gemini) - Natural language generation
    """
    
    def __init__(self, output_schedule_file, conflict_report_file=None, log_file=None, gemini_api_key=None):
        """
        Initialize the chatbot.
        
        Args:
            output_schedule_file (str): Path to generated schedule CSV
            conflict_report_file (str): Path to conflict report text file
            log_file (str): Path to log file
            gemini_api_key (str): Gemini API key
        """
        self.logger = setup_chatbot_logger(log_file)
        self.df = None
        self.model = None
        self.schedule_file = output_schedule_file
        self.conflict_file = conflict_report_file
        
        # Data loading state tracking
        self.data_loaded = False
        self.time_queries_enabled = True
        
        # Initialize column name mappings (will be set during load_data)
        self._time_start_col = 'h_ini'
        self._time_end_col = 'h_fin'
        self._day_col = 'dia'
        self._room_col = 'c_codaula'
        self._teacher_col = 'docente'
        
        # Lookup indexes for fast queries
        self.teacher_index = {}
        self.room_index = {}
        self.course_index = {}
        
        # Initialize conflict report parser
        self.conflict_parser = ConflictReportParser(conflict_report_file)
        
        self.logger.info("=" * 70)
        self.logger.info("🤖 ScheduleChatbot Initializing (Router & Tools Architecture)")
        self.logger.info("=" * 70)
        
        # Load schedule data
        if output_schedule_file and os.path.exists(output_schedule_file):
            self.load_data(output_schedule_file)
        else:
            self.logger.warning(f"⚠️  Schedule file not found: {output_schedule_file}")
        
        # Initialize Gemini (Router + Synthesizer)
        if GEMINI_AVAILABLE and gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                # Try newer models first
                try:
                    self.model = genai.GenerativeModel('gemini-2.5-flash')
                    self.logger.info("✅ Brain (Gemini 2.5 Flash) Online - Router & Synthesizer Ready")
                except:
                    self.model = genai.GenerativeModel('gemini-1.5-flash')
                    self.logger.info("✅ Brain (Gemini 1.5 Flash) Online - Router & Synthesizer Ready")
            except Exception as e:
                self.logger.error(f"❌ Gemini initialization failed: {e}")
                self.model = None
        else:
            if not GEMINI_AVAILABLE:
                self.logger.warning("⚠️  Gemini not installed - using fallback keyword routing")
            elif not gemini_api_key:
                self.logger.warning("⚠️  Gemini API key not provided - using fallback keyword routing")
    
    def load_data(self, filepath):
        """Load schedule data and pre-calculate time objects for fast queries."""
        try:
            self.logger.debug(f"Loading schedule from: {filepath}")
            self.df = pd.read_csv(filepath, dtype=str).fillna('')
            
            # Detect which columns are available and map them
            # The actual schedule uses: h_ini, h_fin, dia, c_codaula, docente
            # But also support new schema: start_time, end_time, day_of_week, room_id, teacher_names
            
            # Determine the correct column names
            if 'h_ini' in self.df.columns:
                # Legacy/current format
                time_start_col = 'h_ini'
                time_end_col = 'h_fin'
                day_col = 'dia'
                room_col = 'c_codaula'
                teacher_col = 'docente'
            else:
                # New format
                time_start_col = 'start_time' if 'start_time' in self.df.columns else 'h_ini'
                time_end_col = 'end_time' if 'end_time' in self.df.columns else 'h_fin'
                day_col = 'day_of_week' if 'day_of_week' in self.df.columns else 'dia'
                room_col = 'room_id' if 'room_id' in self.df.columns else 'c_codaula'
                teacher_col = 'teacher_names' if 'teacher_names' in self.df.columns else 'docente'
            
            # Store column names for later use
            self._time_start_col = time_start_col
            self._time_end_col = time_end_col
            self._day_col = day_col
            self._room_col = room_col
            self._teacher_col = teacher_col
            
            # Validate critical columns exist
            required_cols = [time_start_col, time_end_col, day_col, room_col, teacher_col]
            missing_cols = [col for col in required_cols if col not in self.df.columns]
            
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Pre-calculate time objects for O(1) comparisons
            self.df['t_start'] = pd.to_datetime(self.df[time_start_col], format='%H:%M', errors='coerce').dt.time
            self.df['t_end'] = pd.to_datetime(self.df[time_end_col], format='%H:%M', errors='coerce').dt.time
            
            # Log time parsing failures
            failed_start = self.df['t_start'].isna().sum()
            failed_end = self.df['t_end'].isna().sum()
            
            if failed_start > 0 or failed_end > 0:
                self.logger.warning(f"⚠️  Time parsing failures: {failed_start} start times, {failed_end} end times")
                # Remove invalid rows
                initial_count = len(self.df)
                self.df = self.df[self.df['t_start'].notna() & self.df['t_end'].notna()]
                removed_count = initial_count - len(self.df)
                self.logger.info(f"Removed {removed_count} rows with invalid times. {len(self.df)} valid records remain")
                self.time_queries_enabled = True if len(self.df) > 0 else False
            else:
                self.logger.debug("✅ All time values parsed successfully")
                self.time_queries_enabled = True
            
            # Build lookup indexes
            self._build_indexes()
            
            self.data_loaded = True
            self.logger.info(f"✅ Data Loaded: {len(self.df)} records")
            self.logger.debug(f"   Columns: {list(self.df.columns)[:8]}...")
            
            # Log data summary
            if day_col in self.df.columns:
                days = self.df[day_col].unique()
                self.logger.debug(f"   Days: {list(days)}")
            if room_col in self.df.columns:
                rooms = self.df[room_col].nunique()
                self.logger.debug(f"   Unique rooms: {rooms}")
            if teacher_col in self.df.columns:
                teachers = self.df[teacher_col].nunique()
                self.logger.debug(f"   Unique teachers: {teachers}")
                
        except Exception as e:
            self.logger.error(f"❌ Data Load Error: {e}", exc_info=True)
            self.df = None
            self.data_loaded = False
            raise
    
    def _build_indexes(self):
        """Build lookup indexes for fast queries."""
        if self.df is None or len(self.df) == 0:
            return
        
        try:
            self.logger.debug("Building lookup indexes...")
            
            # Teacher index
            self.teacher_index = {}
            for idx, row in self.df.iterrows():
                teacher = row.get(self._teacher_col, '')
                if teacher and not pd.isna(teacher):
                    if teacher not in self.teacher_index:
                        self.teacher_index[teacher] = []
                    self.teacher_index[teacher].append(idx)
            
            # Room index
            self.room_index = {}
            for idx, row in self.df.iterrows():
                room = row.get(self._room_col, '')
                if room and not pd.isna(room) and 'SIN AULA' not in str(room).upper():
                    if room not in self.room_index:
                        self.room_index[room] = []
                    self.room_index[room].append(idx)
            
            # Course index
            self.course_index = {}
            for idx, row in self.df.iterrows():
                course = row.get('c_nomcur', '')
                if course and not pd.isna(course):
                    if course not in self.course_index:
                        self.course_index[course] = []
                    self.course_index[course].append(idx)
            
            self.logger.info(f"✅ Indexes built: {len(self.teacher_index)} teachers, "
                           f"{len(self.room_index)} rooms, {len(self.course_index)} courses")
            
        except Exception as e:
            self.logger.error(f"Error building indexes: {e}")
            # Continue anyway - indexes are optional
    
    def _get_column_name(self, new_name, old_name):
        """Get the correct column name supporting both old and new schemas."""
        if self.df is not None and new_name in self.df.columns:
            return new_name
        return old_name
    
    @property
    def col_time_start(self):
        """Get start time column name."""
        return self._time_start_col
    
    @property
    def col_time_end(self):
        """Get end time column name."""
        return self._time_end_col
    
    @property
    def col_day(self):
        """Get day column name."""
        return self._day_col
    
    @property
    def col_room(self):
        """Get room column name."""
        return self._room_col
    
    @property
    def col_teacher(self):
        """Get teacher column name."""
        return self._teacher_col
    
    def reload_data(self, filepath):
        """Reload schedule data (useful after scheduler generates new data)."""
        self.logger.info("🔄 Reloading schedule data...")
        self.load_data(filepath)
    
    def update_record(self, session_id, payload):
        """
        Update a specific record in the chatbot's dataframe.
        
        This is called when a schedule entry is modified via the API.
        Syncs the chatbot's in-memory data with the updated CSV.
        
        Args:
            session_id (int): The session_id of the record to update
            payload (dict): Dictionary of field:value pairs to update
        """
        if self.df is None or len(self.df) == 0:
            self.logger.warning("⚠️  No data loaded - cannot update record")
            return False
        
        try:
            self.logger.debug(f"🔄 Updating record {session_id} with payload: {payload}")
            
            # Find the record by session_id
            if 'session_id' not in self.df.columns:
                self.logger.warning("⚠️  session_id column not found in dataframe")
                return False
            
            mask = self.df['session_id'] == session_id
            
            if not mask.any():
                self.logger.warning(f"⚠️  Record with session_id {session_id} not found")
                return False
            
            idx = self.df.index[mask][0]
            
            # Update the fields
            for key, value in payload.items():
                if key in self.df.columns:
                    self.df.at[idx, key] = value
                    self.logger.debug(f"   Updated {key} → {value}")
            
            # Rebuild indexes since data changed
            self._build_indexes()
            
            self.logger.info(f"✅ Record {session_id} updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error updating record {session_id}: {e}", exc_info=True)
            return False
    
    # ==========================================================================
    # LAYER 1: THE SEMANTIC ROUTER (Gemini Intent Detection)
    # ==========================================================================
    
    def router(self, query, history):
        """
        Route user query to appropriate intent.
        
        Extracts intent and entities using Gemini (if available) or fallback.
        
        Returns:
            dict: {intent, entities}
        """
        if not self.model:
            # Fallback: keyword-based routing
            self.logger.debug("Using keyword-based fallback routing (Gemini unavailable)")
            return self._fallback_router(query)
        
        current_day = datetime.now().strftime('%A, %Y-%m-%d')
        
        prompt = f"""System: You are a University Scheduler Assistant.
Current Date: {current_day}

User Query: "{query}"
Conversation History: {history if history else "(No previous context)"}

Analyze the query and extract Intent and Entities.

INTENTS:
1. "lookup": Find specific class/teacher/room/course usage
   Examples: "Where is Prof García?", "Who has the lab Monday?", "When is Bromatología?"
   
2. "availability": User wants to SCHEDULE something, check FREE rooms, or find time slots
   Examples: "Can I schedule a lab Monday at 3pm?", "Emergency: need a room", "Is 00-LB-01 free?"
   
3. "conflict_report": User asks about errors, conflicts, collisions, issues
   Examples: "How many conflicts are there?", "What went wrong?", "Show conflicts"
   
4. "stats": General statistics or counts
   Examples: "How many classes total?", "Count rooms"
   
5. "greeting": Hi, hello, thanks, etc.
   Examples: "Hello!", "Hi there"

ENTITIES (Extract ONLY what you see in the query):
- day: Day name (English or Spanish, e.g., "Monday", "Lunes", "tomorrow")
- time: Time or time range (HH:MM format, e.g., "14:00" or "14:00-16:00")
- room: Specific room code (e.g., "00-LB-01", "Aula 5")
- room_type: Type hint (e.g., "lab", "classroom", "aula")
- course: Subject/course name (e.g., "Bromatología", "Python", "Database")
- teacher: Person name (e.g., "García", "López")

IMPORTANT RULES:
- Only extract entities EXPLICITLY mentioned in the query
- Return null for missing entities
- For availability queries, include day/time/room_type
- Be lenient with fuzzy matches

Return ONLY valid JSON (no markdown):
{{
  "intent": "lookup|availability|conflict_report|stats|greeting",
  "entities": {{
    "day": "...",
    "time": "...",
    "room": "...",
    "room_type": "...",
    "course": "...",
    "teacher": "..."
  }}
}}"""
        
        try:
            self.logger.debug(f"🧠 Routing query with Gemini...")
            response = self.model.generate_content(prompt)
            parsed = self._safe_parse_gemini_response(response.text)
            
            self.logger.info(f"✅ Intent: {parsed.get('intent', 'unknown')} | Entities: {list(parsed.get('entities', {}).keys())}")
            
            return parsed
            
        except Exception as e:
            self.logger.error(f"❌ Router error: {e}")
            return self._fallback_router(query)
    
    def _safe_parse_gemini_response(self, response_text, max_attempts=3):
        """
        Safely parse Gemini JSON response with retries and validation.
        
        Args:
            response_text (str): Raw response from Gemini
            max_attempts (int): Number of parse attempts before fallback
            
        Returns:
            dict: Parsed JSON with intent and entities
        """
        for attempt in range(max_attempts):
            try:
                # Clean markdown
                clean = response_text.strip()
                if '```' in clean:
                    # Extract content between code blocks
                    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean, re.DOTALL)
                    if match:
                        clean = match.group(1)
                    else:
                        clean = clean.replace('```json', '').replace('```', '')
                
                # Parse JSON
                parsed = json.loads(clean)
                
                # Validate schema
                if 'intent' not in parsed or 'entities' not in parsed:
                    raise ValueError("Missing required fields: intent or entities")
                
                # Validate intent value
                valid_intents = ['lookup', 'availability', 'conflict_report', 'stats', 'greeting']
                if parsed['intent'] not in valid_intents:
                    raise ValueError(f"Invalid intent: {parsed['intent']}")
                
                self.logger.debug(f"✅ JSON parsed successfully on attempt {attempt + 1}")
                return parsed
                
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Parse attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    self.logger.error(f"All parse attempts failed. Raw response: {response_text[:200]}")
                    return {"intent": "lookup", "entities": {}}
        
        return {"intent": "lookup", "entities": {}}
    
    def _fallback_router(self, query):
        """Fallback keyword-based routing when Gemini is unavailable."""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['hi', 'hello', 'hey', 'thanks', 'gracias']):
            return {"intent": "greeting", "entities": {}}
        
        if any(word in query_lower for word in ['conflict', 'error', 'wrong', 'issue', 'problem']):
            return {"intent": "conflict_report", "entities": {}}
        
        if any(word in query_lower for word in ['can i', 'schedule', 'free', 'available', 'emergency']):
            return {"intent": "availability", "entities": {}}
        
        if any(word in query_lower for word in ['how many', 'count', 'total', 'stats']):
            return {"intent": "stats", "entities": {}}
        
        return {"intent": "lookup", "entities": {}}
    
    # ==========================================================================
    # LAYER 2: THE TOOL BELT (Python/Pandas Tools)
    # ==========================================================================
    
    def tool_conflict_report(self):
        """
        Tool A: Intelligent Conflict Analysis (Optimized with Vectorized Operations).
        
        Instead of dumping raw report files, this analyzes conflicts in real-time
        with actionable insights:
        - Specific conflict examples
        - Top problematic teachers/rooms
        - Clear recommendations
        """
        if self.df is None or len(self.df) == 0:
            self.logger.warning("⚠️  No schedule data loaded")
            return "⚠️ Schedule data not available. Please run the scheduler first."
        
        try:
            self.logger.info(f"🔍 Analyzing conflicts in {len(self.df)} classes...")
            
            report_lines = []
            report_lines.append("📊 INTELLIGENT CONFLICT ANALYSIS REPORT\n")
            
            # Get the actual column names we're using
            day_col = self._day_col
            teacher_col = self._teacher_col
            room_col = self._room_col
            time_start_col = self._time_start_col
            time_end_col = self._time_end_col
            course_col = 'c_nomcur' if 'c_nomcur' in self.df.columns else 'curso'
            
            total_classes = len(self.df)
            report_lines.append("🔢 Overall Statistics")
            report_lines.append(f"- Total Classes: {total_classes}")
            
            # ===== OPTIMIZED: Use vectorized groupby + size =====
            # Teacher Conflicts
            teacher_groups = self.df.groupby([teacher_col, day_col, time_start_col]).size()
            teacher_conflicts = teacher_groups[teacher_groups > 1]
            
            # Room Conflicts
            room_conflicts_df = self.df[~self.df[room_col].str.upper().str.contains('SIN AULA', na=False)]
            room_groups = room_conflicts_df.groupby([room_col, day_col, time_start_col]).size()
            room_conflicts = room_groups[room_groups > 1]
            
            # ===== Teacher Conflicts Section =====
            if len(teacher_conflicts) > 0:
                report_lines.append(f"- Teacher Conflicts: {len(teacher_conflicts)} instances")
                
                # Aggregate by teacher (fast)
                teacher_issue_counts = {}
                for (teacher, day, time_slot), count in teacher_conflicts.items():
                    if teacher not in teacher_issue_counts:
                        teacher_issue_counts[teacher] = 0
                    teacher_issue_counts[teacher] += count
                
                # Top 5 most affected teachers
                sorted_teachers = sorted(teacher_issue_counts.items(), 
                                        key=lambda x: x[1], reverse=True)[:5]
                if sorted_teachers:
                    report_lines.append("\n👨‍🏫 Top 5 Most Affected Teachers:")
                    for i, (teacher, count) in enumerate(sorted_teachers, 1):
                        report_lines.append(f"  {i}. {teacher}: {count} conflicts")
                
                # Specific Examples (only top 3)
                report_lines.append("\n📌 Conflict Examples:")
                for idx, ((teacher, day, time_slot), _) in enumerate(
                    list(teacher_conflicts.items())[:3], 1):
                    # Get classes for this conflict
                    conflict_classes = self.df[
                        (self.df[teacher_col] == teacher) & 
                        (self.df[day_col] == day) & 
                        (self.df[time_start_col] == time_slot)
                    ]
                    
                    report_lines.append(f"\n  Example {idx}:")
                    report_lines.append(f"  - Teacher: {teacher}")
                    report_lines.append(f"  - Day: {day} at {time_slot}")
                    report_lines.append(f"  - Conflicting Classes ({len(conflict_classes)}):")
                    
                    for _, row in conflict_classes.head(3).iterrows():
                        course = row.get(course_col, "Unknown")
                        room = row.get(room_col, "SIN AULA")
                        report_lines.append(f"    • {course} in {room}")
            else:
                report_lines.append("- Teacher Conflicts: None detected ✅")
            
            # ===== Room Conflicts Section =====
            if len(room_conflicts) > 0:
                report_lines.append(f"\n🏛️  Room Conflicts: {len(room_conflicts)} instances")
                
                # Aggregate by room (fast)
                room_issue_counts = {}
                for (room, day, time_slot), count in room_conflicts.items():
                    if room not in room_issue_counts:
                        room_issue_counts[room] = 0
                    room_issue_counts[room] += count
                
                # Top 5 most problematic rooms
                sorted_rooms = sorted(room_issue_counts.items(), 
                                     key=lambda x: x[1], reverse=True)[:5]
                if sorted_rooms:
                    report_lines.append("\n  Most Problematic Rooms:")
                    for i, (room, count) in enumerate(sorted_rooms, 1):
                        report_lines.append(f"  {i}. {room}: {count} double-bookings")
            else:
                report_lines.append("\n🏛️  Room Conflicts: None detected ✅")
            
            # ===== Unassigned Classes =====
            unassigned_count = len(self.df[self.df[room_col].str.upper().str.contains('SIN AULA', na=False)])
            
            if unassigned_count > 0:
                report_lines.append(f"\n⚠️  Unassigned Classes: {unassigned_count} classes without a room")
            
            # ===== Recommendations =====
            report_lines.append("\n\n💡 Recommendations:")
            
            if len(teacher_conflicts) > 0 or len(room_conflicts) > 0 or unassigned_count > 0:
                if len(teacher_conflicts) > 0:
                    top_teachers = sorted(teacher_issue_counts.items(), 
                                        key=lambda x: x[1], reverse=True)[:3]
                    teacher_names = ", ".join([t[0] for t in top_teachers])
                    report_lines.append(f"1. ⚠️  Fix teacher conflicts first")
                    report_lines.append(f"   Priority: {teacher_names}")
                
                if len(room_conflicts) > 0:
                    top_rooms = sorted(room_issue_counts.items(), 
                                     key=lambda x: x[1], reverse=True)[:3]
                    room_names = ", ".join([r[0] for r in top_rooms])
                    report_lines.append(f"2. ⚠️  Reassign high-conflict rooms")
                    report_lines.append(f"   Priority: {room_names}")
                
                if unassigned_count > 0:
                    report_lines.append(f"3. ⚠️  Assign remaining {unassigned_count} classes to available rooms")
            else:
                report_lines.append("✅ No conflicts detected! Schedule is clean.")
            
            report_text = "\n".join(report_lines)
            self.logger.info(f"✅ Conflict analysis complete")
            return report_text
            
        except Exception as e:
            self.logger.error(f"Error analyzing conflicts: {e}", exc_info=True)
            return f"Error analyzing conflicts: {e}"
    
    def tool_lookup(self, entities):
        """Tool B: Flexible lookup using fuzzy matching."""
        if self.df is None or len(self.df) == 0:
            self.logger.warning("❌ No data loaded")
            return "Data offline."
        
        self.logger.debug("🔍 Executing lookup tool...")
        
        results = self.df.copy()
        filters_applied = []
        
        # Apply fuzzy filters
        if entities.get('day'):
            normalized_day = EntityNormalizer.get_day(entities['day'])
            if normalized_day:
                results = results[results[self.col_day].str.contains(normalized_day, case=False, na=False)]
                filters_applied.append(f"Day={normalized_day}")
                self.logger.debug(f"   Applied day filter → {len(results)} rows")
        
        if entities.get('course'):
            course_term = str(entities['course'])
            results = results[results['c_nomcur'].str.contains(course_term, case=False, na=False)]
            filters_applied.append(f"Course contains '{course_term}'")
            self.logger.debug(f"   Applied course filter → {len(results)} rows")
        
        if entities.get('teacher'):
            teacher_term = str(entities['teacher'])
            
            # Get all teachers from dataframe
            all_teachers = [str(t) for t in self.df[self.col_teacher].unique() if t and not pd.isna(t)]
            
            # Try fuzzy matching
            if RAPIDFUZZ_AVAILABLE:
                best_match, score = find_best_fuzzy_match(teacher_term, all_teachers, threshold=60)
                
                if best_match:
                    results = results[results[self.col_teacher] == best_match]
                    filters_applied.append(f"Teacher≈'{best_match}' (score: {score}%)")
                    self.logger.info(f"✅ Fuzzy matched '{teacher_term}' → '{best_match}' (score: {score}%)")
                else:
                    # Show suggestions
                    suggestions = find_all_fuzzy_matches(teacher_term, all_teachers, threshold=40, limit=3)
                    
                    if suggestions:
                        suggestion_text = ", ".join([f"'{s[0]}' ({s[1]}%)" for s in suggestions])
                        self.logger.info(f"❌ No close match for '{teacher_term}'. Suggestions: {suggestion_text}")
                        return f"Teacher '{teacher_term}' not found. Did you mean: {suggestion_text}?"
                    
                    self.logger.info(f"❌ No teacher matching '{teacher_term}' found.")
                    return f"No teacher matching '{teacher_term}' found in the system."
            else:
                # Fallback to exact substring matching
                results = results[results[self.col_teacher].str.contains(teacher_term, case=False, na=False)]
                filters_applied.append(f"Teacher contains '{teacher_term}'")
                self.logger.debug(f"   Applied teacher filter → {len(results)} rows")
        
        if entities.get('room'):
            room_term = str(entities['room']).upper().replace(" ", "")
            results = results[results[self.col_room].str.contains(room_term, case=False, na=False)]
            filters_applied.append(f"Room='{room_term}'")
            self.logger.debug(f"   Applied room filter → {len(results)} rows")
        
        if results.empty:
            self.logger.info(f"❌ No matches found for: {', '.join(filters_applied)}")
            return f"No classes found matching: {', '.join(filters_applied)}"
        
        self.logger.info(f"✅ Found {len(results)} classes")
        
        # Format for LLM
        summary = []
        for idx, (_, row) in enumerate(results.head(10).iterrows(), 1):
            summary.append(
                f"{idx}. {row.get('c_nomcur', 'Unknown')} | "
                f"{row.get('dia', '?')} {row.get(self.col_time_start, '?')}-{row.get(self.col_time_end, '?')} | "
                f"Room: {row.get(self.col_room, 'TBD')} | "
                f"Prof: {row.get(self.col_teacher, 'Unknown')}"
            )
        
        if len(results) > 10:
            summary.append(f"\n... and {len(results) - 10} more classes")
        
        return "\n".join(summary)
    
    def tool_teacher_detailed_stats(self, teacher_name):
        """
        Tool B-Extended: Get detailed statistics for a specific teacher.
        
        Returns: assigned, conflicting, virtual, labs, theory, total classes
        """
        if self.df is None or len(self.df) == 0:
            self.logger.warning("❌ No data loaded")
            return None
        
        self.logger.debug(f"📊 Getting detailed stats for teacher: {teacher_name}")
        
        # Fuzzy match teacher name
        all_teachers = [str(t) for t in self.df[self.col_teacher].unique() if t and not pd.isna(t)]
        
        if RAPIDFUZZ_AVAILABLE:
            best_match, score = find_best_fuzzy_match(teacher_name, all_teachers, threshold=60)
            if not best_match:
                self.logger.debug(f"No teacher found matching '{teacher_name}'")
                return None
            matched_teacher = best_match
            self.logger.info(f"✅ Matched '{teacher_name}' → '{matched_teacher}'")
        else:
            # Fallback: exact substring
            matching = [t for t in all_teachers if teacher_name.lower() in t.lower()]
            if not matching:
                return None
            matched_teacher = matching[0]
        
        # Get all classes for this teacher
        teacher_classes = self.df[self.df[self.col_teacher] == matched_teacher].copy()
        
        if len(teacher_classes) == 0:
            return None
        
        # Calculate statistics
        stats = {
            'teacher_name': matched_teacher,
            'total_classes': len(teacher_classes),
            'assigned': 0,
            'conflicting': 0,
            'virtual': 0,
            'labs': 0,
            'theory': 0
        }
        
        # Count assigned vs unassigned
        assigned = teacher_classes[~teacher_classes[self.col_room].str.contains('SIN AULA|UNSCHEDULED|VIRTUAL', na=False)]
        stats['assigned'] = len(assigned)
        stats['unassigned'] = len(teacher_classes) - stats['assigned']
        
        # Count virtual classes
        virtual = teacher_classes[teacher_classes[self.col_room].str.contains('VIRTUAL', na=False)]
        stats['virtual'] = len(virtual)
        
        # Count labs vs theory (based on room codes)
        for _, row in teacher_classes.iterrows():
            room = str(row[self.col_room]).upper() if not pd.isna(row[self.col_room]) else ''
            
            if 'LB' in room:
                stats['labs'] += 1
            elif 'CL' in room or 'AU' in room:
                stats['theory'] += 1
        
        # Get teacher ID(s) to lookup conflicts
        teacher_ids = teacher_classes['teacher_ids'].unique()
        conflict_by_day = {}
        total_conflicts = 0
        
        for teacher_id in teacher_ids:
            if pd.isna(teacher_id):
                continue
            
            teacher_id_str = str(teacher_id).strip()
            teacher_conflicts = self.conflict_parser.get_teacher_conflicts(teacher_id_str)
            
            for conflict in teacher_conflicts:
                total_conflicts += 1
                day = conflict.get('day', 'Unknown')
                if day not in conflict_by_day:
                    conflict_by_day[day] = 0
                conflict_by_day[day] += 1
        
        stats['conflicting'] = total_conflicts
        stats['conflicts_by_day'] = conflict_by_day
        
        self.logger.info(f"✅ Teacher stats: {stats['total_classes']} classes, {stats['conflicting']} conflicts")
        
        return stats
    
    def tool_check_availability(self, entities):
        """Tool C: Smart availability checking for scheduling."""
        if self.df is None or len(self.df) == 0:
            self.logger.warning("❌ No data for availability check")
            return "Data offline."
        
        self.logger.debug("🏛️  Executing availability tool...")
        
        # 1. Parse requirements
        day_str = entities.get('day')
        time_str = entities.get('time')
        room_type_hint = entities.get('room_type')
        
        if not day_str:
            self.logger.info("⚠️  No day specified")
            return "⚠️ I need a **day** to check availability. (e.g., Monday, Lunes, tomorrow)"
        
        # Normalize day
        target_day = EntityNormalizer.get_day(day_str)
        if not target_day:
            self.logger.info(f"❌ Invalid day: {day_str}")
            return f"❌ I don't understand the day '{day_str}'. Use: Monday-Saturday or Spanish names."
        
        self.logger.debug(f"Checking availability for: {target_day}")
        
        # 2. Filter by day
        day_df = self.df[self.df[self.col_day] == target_day]
        if day_df.empty:
            self.logger.info(f"No classes scheduled on {target_day}")
            return f"No classes scheduled on {target_day}. All rooms are free!"
        
        self.logger.debug(f"   {len(day_df)} classes on {target_day}")
        
        # 3. Get all rooms (from schedule data)
        all_rooms = sorted(set(
            self.df[~self.df[self.col_room].str.contains("SIN AULA|UNSCHEDULED|VIRTUAL", na=False)][self.col_room].unique()
        ))
        
        self.logger.debug(f"   Total rooms in system: {len(all_rooms)}")
        
        # 4. Filter by room type if specified
        target_rooms = all_rooms
        if room_type_hint:
            room_type_code = EntityNormalizer.get_room_type(room_type_hint)
            if room_type_code:
                target_rooms = [r for r in all_rooms if f"-{room_type_code}-" in r]
                self.logger.debug(f"   Filtered to {len(target_rooms)} {room_type_hint} rooms")
        
        if not target_rooms:
            return f"No {room_type_hint or 'rooms'} found in the system."
        
        # 5. If no time specified, show fully free rooms
        if not time_str:
            self.logger.debug("No time specified - checking all-day availability")
            occupied_on_day = set(day_df[self.col_room].unique())
            free_rooms = [r for r in target_rooms if r not in occupied_on_day]
            
            if not free_rooms:
                return f"❌ All {room_type_hint or 'rooms'} are occupied on {target_day}."
            
            result = f"✅ On **{target_day}**, these {len(free_rooms)} {room_type_hint or 'rooms'} are FREE ALL DAY:\n"
            result += ", ".join(sorted(free_rooms)[:15])
            
            if len(free_rooms) > 15:
                result += f"\n... and {len(free_rooms) - 15} more"
            
            self.logger.info(f"✅ Found {len(free_rooms)} free rooms for {target_day}")
            return result
        
        # 6. Parse time range
        req_start, req_end = EntityNormalizer.parse_time_range(time_str)
        
        if req_start is None:
            self.logger.info(f"Invalid time format: {time_str}")
            return f"❌ I don't understand the time '{time_str}'. Use HH:MM format (e.g., 14:00 or 14:00-16:00)."
        
        self.logger.debug(f"Checking time slot: {req_start}-{req_end}")
        
        # 7. Find occupied rooms in this time slot
        # Logic: A class occupies a slot if (Class_Start < Req_End) AND (Class_End > Req_Start)
        occupied_in_slot = set()
        
        for _, row in day_df.iterrows():
            try:
                class_start = row['t_start']
                class_end = row['t_end']
                
                # Check for overlap
                if class_start < req_end and class_end > req_start:
                    occupied_in_slot.add(row[self.col_room])
            except Exception as e:
                self.logger.debug(f"Time parsing error: {e}")
                continue
        
        self.logger.debug(f"   {len(occupied_in_slot)} rooms occupied in slot")
        
        # 8. Calculate available rooms
        available = [r for r in target_rooms if r not in occupied_in_slot]
        
        if not available:
            return f"❌ No {room_type_hint or 'rooms'} available on {target_day} at {time_str}."
        
        result = f"✅ Yes! Found **{len(available)}** available {room_type_hint or 'rooms'} on {target_day} ({time_str}):\n"
        result += ", ".join(sorted(available)[:10])
        
        if len(available) > 10:
            result += f"\n... and {len(available) - 10} more"
        
        self.logger.info(f"✅ Found {len(available)} available rooms")
        return result
    
    def tool_stats(self):
        """Tool D: Return basic statistics."""
        if self.df is None or len(self.df) == 0:
            return "No data available."
        
        total = len(self.df)
        unassigned = len(self.df[self.df[self.col_room].str.contains('SIN AULA|UNSCHEDULED|VIRTUAL', na=False)])
        assigned = total - unassigned
        rooms = self.df[self.col_room].nunique()
        teachers = self.df[self.col_teacher].nunique()
        courses = self.df['c_nomcur'].nunique()
        
        stats = f"""📊 **Schedule Statistics:**
- Total Classes: {total}
- Assigned Rooms: {assigned}
- Unassigned: {unassigned}
- Unique Rooms: {rooms}
- Unique Teachers: {teachers}
- Unique Courses: {courses}
- Assignment Rate: {(assigned/total*100):.1f}%"""
        
        self.logger.info(f"✅ Stats computed: {total} classes, {assigned} assigned")
        return stats
    
    # ==========================================================================
    # HEALTH CHECK & DIAGNOSTICS
    # ==========================================================================
    
    def health_check(self):
        """
        Comprehensive health check for diagnostics.
        
        Returns:
            dict: Health status with detailed information
        """
        health = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        # 1. Check data loaded
        if self.df is None or len(self.df) == 0:
            health['checks']['data_loaded'] = {
                'status': 'error',
                'message': 'No data loaded',
                'record_count': 0
            }
            health['overall_status'] = 'error'
        else:
            health['checks']['data_loaded'] = {
                'status': 'ok',
                'message': f'Data loaded successfully',
                'record_count': len(self.df)
            }
        
        # 2. Check critical columns
        required_cols = [self._time_start_col, self._time_end_col, self._day_col, 
                        self._room_col, self._teacher_col]
        
        missing_cols = [col for col in required_cols if col not in self.df.columns] if self.df is not None else required_cols
        
        if missing_cols:
            health['checks']['columns'] = {
                'status': 'error',
                'message': f'Missing columns: {missing_cols}',
                'missing_count': len(missing_cols)
            }
            health['overall_status'] = 'error'
        else:
            health['checks']['columns'] = {
                'status': 'ok',
                'message': 'All required columns present',
                'columns': required_cols
            }
        
        # 3. Check time parsing
        if self.df is not None and 't_start' in self.df.columns:
            null_count = self.df['t_start'].isna().sum()
            if null_count > 0:
                health['checks']['time_parsing'] = {
                    'status': 'warning',
                    'message': f'{null_count} rows have invalid start times',
                    'invalid_count': null_count,
                    'valid_count': len(self.df) - null_count
                }
            else:
                health['checks']['time_parsing'] = {
                    'status': 'ok',
                    'message': 'All times parsed successfully',
                    'valid_count': len(self.df)
                }
        else:
            health['checks']['time_parsing'] = {
                'status': 'error',
                'message': 'Time columns not found'
            }
        
        # 4. Check Gemini availability
        health['checks']['gemini'] = {
            'status': 'ok' if self.model else 'warning',
            'available': bool(self.model),
            'message': 'Gemini AI available' if self.model else 'Gemini not available (using fallback)'
        }
        
        # 5. Check fuzzy matching library
        health['checks']['fuzzy_matching'] = {
            'status': 'ok' if RAPIDFUZZ_AVAILABLE else 'warning',
            'available': RAPIDFUZZ_AVAILABLE,
            'message': 'RapidFuzz library available' if RAPIDFUZZ_AVAILABLE else 'RapidFuzz not available (using fallback)'
        }
        
        # 6. Check indexes
        if self.df is not None:
            health['checks']['indexes'] = {
                'status': 'ok',
                'teacher_index': len(self.teacher_index),
                'room_index': len(self.room_index),
                'course_index': len(self.course_index),
                'message': 'Lookup indexes built'
            }
        else:
            health['checks']['indexes'] = {
                'status': 'warning',
                'message': 'Indexes not built (no data loaded)'
            }
        
        # 7. Check data state
        health['checks']['data_state'] = {
            'status': 'ok',
            'data_loaded': self.data_loaded,
            'time_queries_enabled': self.time_queries_enabled,
            'message': 'System ready' if self.data_loaded else 'Waiting for data'
        }
        
        return health
    
    # ==========================================================================
    # LAYER 3: THE SYNTHESIZER (Natural Language Response Generation)
    # ==========================================================================
    
    def generate_response(self, query, history_str):
        """
        Main handler: Routes query → Executes tool → Synthesizes natural response.
        
        Args:
            query (str): User's question
            history_str (str): Recent conversation for context
            
        Returns:
            str: Natural language response
        """
        
        if self.df is None or len(self.df) == 0:
            return "❌ Schedule data not loaded. Please run the scheduler first."
        
        # Input validation
        is_valid, validation_msg = EntityNormalizer.validate_query_length(query)
        if not is_valid:
            self.logger.warning(f"Invalid query: {validation_msg}")
            return f"❌ {validation_msg}"
        
        # Sanitize input
        query = sanitize_input(query)
        
        self.logger.info("\n" + "=" * 70)
        self.logger.info(f"📩 User Query: {query}")
        self.logger.info("=" * 70)
        
        # Step 1: Route (Layer 1)
        parsed = self.router(query, history_str)
        intent = parsed.get('intent', 'lookup')
        entities = parsed.get('entities', {})
        
        self.logger.debug(f"Intent: {intent} | Entities: {entities}")
        
        # Step 2: Execute Tool (Layer 2)
        raw_data = ""
        
        # Check if this is a teacher stats query (has both teacher entity and stats keywords)
        # This takes precedence over conflict_report intent
        stats_keywords = ['assigned', 'conflicting', 'virtual', 'lab', 'theory', 'statistics', 'stats', 'total', 'count', 'how many']
        is_teacher_stats_query = entities.get('teacher') and any(keyword in query.lower() for keyword in stats_keywords)
        
        if intent == "greeting":
            self.logger.info("✅ Greeting detected")
            return "� Hello! I'm your Scheduler Assistant. I can help you find classes, check room availability, view conflicts, or get statistics. What would you like to know?"
        
        elif is_teacher_stats_query:
            self.logger.info("📊 Teacher detailed stats query detected")
            teacher_stats = self.tool_teacher_detailed_stats(entities['teacher'])
            
            if teacher_stats:
                # Format stats for display
                raw_data = f"""📊 **DETAILED STATISTICS FOR {teacher_stats['teacher_name'].upper()}**

Total Classes:        {teacher_stats['total_classes']}
├─ Assigned:          {teacher_stats['assigned']}
├─ Unassigned:        {teacher_stats['unassigned']}
├─ Virtual:           {teacher_stats['virtual']}
├─ Labs:              {teacher_stats['labs']}
└─ Theory:            {teacher_stats['theory']}

Scheduling Conflicts: {teacher_stats['conflicting']}"""
                
                if teacher_stats.get('conflicts_by_day'):
                    raw_data += "\n\nConflicts by Day:"
                    for day, count in teacher_stats['conflicts_by_day'].items():
                        raw_data += f"\n  • {day}: {count} conflicts"
            else:
                raw_data = f"Teacher '{entities['teacher']}' not found in the system."
        
        elif intent == "conflict_report":
            self.logger.info("📋 Retrieving conflict report...")
            raw_data = self.tool_conflict_report()
        
        elif intent == "availability":
            self.logger.info("🏛️  Checking availability...")
            raw_data = self.tool_check_availability(entities)
        
        elif intent == "stats":
            self.logger.info("📊 Computing statistics...")
            raw_data = self.tool_stats()
        
        else:  # lookup
            self.logger.info("🔍 Performing lookup...")
            raw_data = self.tool_lookup(entities)
        
        # Step 3: Synthesize (Layer 3)
        if self.model and GEMINI_AVAILABLE and intent not in ["greeting"]:
            try:
                self.logger.debug("🎯 Synthesizing with Gemini...")
                
                # Guard against huge data
                if len(raw_data) > 5000:
                    raw_data = raw_data[:5000] + "\n\n...(truncated for length)"
                
                final_prompt = f"""User Query: "{query}"
System Intent: {intent}
Raw System Data:

{raw_data}

Task: Answer the user naturally and kindly based ONLY on the System Data provided.
- Be concise but complete
- Use formatting for readability
- If data is empty/unavailable, explain why in a helpful way
- Do NOT make up information"""
                
                response = self.model.generate_content(final_prompt)
                self.logger.info("✅ Response synthesized by Gemini")
                return response.text
                
            except Exception as e:
                self.logger.error(f"❌ Synthesis error: {e}")
                self.logger.info("Falling back to raw data")
                return raw_data
        
        self.logger.info("✅ Response ready (no synthesis)")
        return raw_data
    
    def check_room_availability_for_ui(self, day=None, start_time=None, end_time=None, room_type=None):
        """
        Helper for UI Availability Tool.
        
        Returns structured availability data for web interface.
        """
        if self.df is None or len(self.df) == 0:
            return {'error': 'Schedule data not loaded'}
        
        try:
            # Determine all available rooms
            all_rooms = sorted(set(
                self.df[~self.df[self.col_room].str.contains("SIN AULA|UNSCHEDULED|VIRTUAL", na=False)][self.col_room].unique()
            ))
            
            # Filter by room type if specified
            filtered_rooms = all_rooms
            if room_type:
                if 'lab' in room_type.lower():
                    filtered_rooms = [r for r in all_rooms if '-LB-' in r]
                elif 'class' in room_type.lower():
                    filtered_rooms = [r for r in all_rooms if '-CL-' in r or '-AU-' in r]
            
            # If no day/time specified, return all rooms as available
            if not day or not start_time or not end_time:
                return {
                    'available': filtered_rooms,
                    'occupied': [],
                    'conflict_details': [],
                    'total_rooms': len(filtered_rooms),
                    'available_count': len(filtered_rooms),
                    'occupied_count': 0,
                    'utilization': 0
                }
            
            # Parse day and time
            target_day = EntityNormalizer.get_day(day)
            if not target_day:
                return {'error': f'Invalid day: {day}'}
            
            # Get day's schedule
            day_schedule = self.df[self.df[self.col_day].str.contains(target_day, case=False, na=False)]
            
            # Parse times
            req_start = pd.to_datetime(start_time, format='%H:%M').time()
            req_end = pd.to_datetime(end_time, format='%H:%M').time()
            
            # Find conflicts
            occupied_rooms = set()
            details = []
            
            for _, row in day_schedule.iterrows():
                room = str(row[self.col_room])
                if room not in filtered_rooms:
                    continue
                
                try:
                    class_start = pd.to_datetime(row[self.col_time_start], format='%H:%M').time()
                    class_end = pd.to_datetime(row[self.col_time_end], format='%H:%M').time()
                    
                    # Check overlap
                    if class_start < req_end and class_end > req_start:
                        occupied_rooms.add(room)
                        details.append({
                            'room': room,
                            'course': row.get('c_nomcur', 'Unknown'),
                            'time': f"{row[self.col_time_start]}-{row[self.col_time_end]}"
                        })
                except:
                    continue
            
            available = [r for r in filtered_rooms if r not in occupied_rooms]
            
            return {
                'available': sorted(available),
                'occupied': sorted(list(occupied_rooms)),
                'conflict_details': details,
                'total_rooms': len(filtered_rooms),
                'available_count': len(available),
                'occupied_count': len(occupied_rooms),
                'utilization': round((len(occupied_rooms) / len(filtered_rooms)) * 100, 1) if filtered_rooms else 0
            }
            
        except Exception as e:
            self.logger.error(f"UI availability check error: {e}")
            return {'error': str(e)}
