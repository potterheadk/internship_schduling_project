"""
app.py - Main Flask Application
Features:
- Scheduler Engine Integration (with Manual Locking)
- Chatbot Logic (Agentic LLM)
- Dashboard Analytics
- Interactive Scheduler Viewer (Drag & Drop)
- Secure API Endpoints
"""

import os
import json
import logging
import traceback
from datetime import datetime
from threading import Lock
from functools import wraps
from analytics_engine import AnalyticsEngine

from flask import Flask, render_template, redirect, url_for, flash, session, jsonify, request, send_file
import pandas as pd
from dotenv import load_dotenv

# --- CUSTOM MODULES ---
# 1. Scheduler Engine & Constants
from scheduler_engine import UMA_Scheduler_Engine, OUTPUT_CSV, LOG_FILE

load_dotenv()
# 2. Chatbot Logic
try:
    from chatbot_logic import ScheduleChatbot
    CHATBOT_AVAILABLE = True
except ImportError:
    CHATBOT_AVAILABLE = False

# Check Gemini Availability
GEMINI_AVAILABLE = bool(os.getenv('GOOGLE_API_KEY', None))

# --- CONFIGURATION ---
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Paths
LOCKS_FILE = 'data/manual_locks.json'  # Stores user manual edits
DEBUG_LOG_FILE = LOG_FILE 
LOGS_DIR = 'data'



# Locks
schedule_lock = Lock()

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = app.logger

# ==============================================================================
# CHATBOT INITIALIZATION
# ==============================================================================
chatbot = None

def initialize_chatbot():
    """Initialize the ScheduleChatbot if available."""
    global chatbot
    if not CHATBOT_AVAILABLE:
        logger.warning("⚠️ Chatbot logic module not found.")
        return

    try:
        # Get API Key from env or config
        gemini_key = os.getenv('GOOGLE_API_KEY', None)
        
        chatbot = ScheduleChatbot(
            output_schedule_file=OUTPUT_CSV,
            conflict_report_file='data/scheduling_conflicts.json',
            log_file='data/chatbot.log',
            gemini_api_key=gemini_key
        )
        logger.info("✅ Chatbot initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize chatbot: {e}")

# Try to init immediately (will fail gracefully if CSV doesn't exist yet)
if os.path.exists(OUTPUT_CSV):
    initialize_chatbot()


# ==============================================================================
# DECORATORS & HELPERS
# ==============================================================================

def handle_errors(f):
    """Decorator to handle errors in routes gracefully."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in route {f.__name__}: {e}\n{traceback.format_exc()}")
            if request.is_json:
                return jsonify({"error": str(e)}), 500
            flash(f"An unexpected error occurred: {str(e)}", "danger")
            return redirect(url_for('home'))
    return decorated_function

# ==============================================================================
# HELPERS: LOCKING & CSV MANAGEMENT
# ==============================================================================

def load_locks():
    """Load manual overrides from JSON."""
    if not os.path.exists(LOCKS_FILE):
        return {}
    try:
        with open(LOCKS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_lock(session_data, updates):
    """
    Save a manual edit as a 'lock' so the engine respects it later.
    Key Format: "n_codper|c_codcur|division|activity_type"
    """
    locks = load_locks()
    
    # Create composite key
    key = f"{session_data['n_codper']}|{session_data['c_codcur']}|{session_data['division']}|{session_data['activity_type']}"
    
    if key not in locks:
        locks[key] = {}
    
    # Update only changed fields
    if 'day_of_week' in updates: locks[key]['day_of_week'] = updates['day_of_week']
    if 'start_time' in updates: locks[key]['start_time'] = updates['start_time']
    if 'room_id' in updates: locks[key]['room_id'] = updates['room_id']
        
    try:
        with open(LOCKS_FILE, 'w') as f:
            json.dump(locks, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save lock: {e}")

def generate_schedule():
    """Run UMA_Scheduler_Engine to create/update final_schedule.csv."""
    engine = UMA_Scheduler_Engine()
    logger.info("⚙️ Generating schedule (Engine running)...")
    engine.run() # This reads locks automatically
    logger.info("✅ Schedule generation completed.")
    
    # Reload chatbot with new data
    if chatbot:
        chatbot.reload_data(OUTPUT_CSV)
    elif CHATBOT_AVAILABLE:
        initialize_chatbot()

def ensure_schedule_exists():
    """Lazy-init the CSV."""
    if os.path.exists(OUTPUT_CSV): return
    with schedule_lock:
        if not os.path.exists(OUTPUT_CSV):
            logger.info("CSV not found. Triggering generation...")
            generate_schedule()

def load_schedule_df():
    """Load CSV safely with session_id."""
    ensure_schedule_exists()
    try:
        df = pd.read_csv(OUTPUT_CSV)
        # Ensure ID column
        if "session_id" not in df.columns:
            df.insert(0, "session_id", range(1, len(df) + 1))
            df.to_csv(OUTPUT_CSV, index=False)
        return df.fillna("")
    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        return pd.DataFrame()

def save_schedule_df(df: pd.DataFrame):
    df.to_csv(OUTPUT_CSV, index=False)


# ==============================================================================
# ROUTES: VIEWS
# ==============================================================================

@app.route("/")
def home():
    """Landing Page."""
    return render_template("home.html")

@app.route("/viewer")
def viewer():
    """Interactive Scheduler Grid (Drag & Drop)."""
    return render_template("index.html")

@app.route("/editor")
def editor():
    """Manual Data Editor."""
    return render_template("editor.html")

@app.route("/dashboard")
# @handle_errors (Keep your existing decorator)
def dashboard():
    """
    Renders the Command Center Dashboard.
    """
    # Ensure data exists (using your existing helper)
    # ensure_schedule_exists() 
    
    engine = AnalyticsEngine()
    payload = engine.get_dashboard_payload()
    
    if payload.get('status') == 'error':
        flash(f"Dashboard Error: {payload.get('message')}", 'danger')
        return redirect(url_for('home')) # Redirect if data is broken

    # Pass the data payload to the template as a JSON string
    return render_template('dashboard.html', viz_data=json.dumps(payload))


    

# ==============================================================================
# ROUTES: CORE ACTIONS
# ==============================================================================

@app.route("/final_schedule.csv")
def final_schedule():
    """Serve CSV for PapaParse in frontend."""
    ensure_schedule_exists()
    return send_file(OUTPUT_CSV, mimetype="text/csv")

@app.route("/regenerate", methods=["POST"])
def regenerate():
    """
    Regenerate schedule. 
    Overwrites CSV but respects 'manual_locks.json'.
    """
    try:
        with schedule_lock:
            generate_schedule()
        return jsonify({"status": "ok", "message": "Schedule regenerated. Manual edits preserved."})
    except Exception as e:
        logger.exception("Regeneration failed")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "csv_exists": os.path.exists(OUTPUT_CSV),
        "chatbot_ready": chatbot is not None
    })

# ==============================================================================
# ROUTES: CRUD API (For Editor & Drag-n-Drop)
# ==============================================================================

@app.route("/api/schedule", methods=["GET"])
def api_list_schedule():
    """List sessions with filtering & pagination for the editor/viewer."""
    with schedule_lock:
        df = load_schedule_df()

    # Filters
    day = request.args.get("day")
    room = request.args.get("room")
    teacher = request.args.get("teacher")
    period = request.args.get("period")

    if day and day != 'all':
        df = df[df["day_of_week"] == day]
    if room and room != 'all':
        df = df[df["room_id"] == room]
    if period and period != 'all':
        df = df[df["n_codper"].astype(str) == str(period)]
    if teacher and teacher != 'all':
        df = df[df["teacher_names"].astype(str).str.contains(teacher, case=False, na=False)]

    # Pagination
    total = int(df.shape[0])
    try:
        limit = int(request.args.get("limit", 10000))  # Default high limit for viewer
        offset = int(request.args.get("offset", 0))
    except ValueError:
        limit, offset = 10000, 0

    if limit < 0:
        limit = 10000
    if offset < 0:
        offset = 0

    df_page = df.iloc[offset:offset + limit]
    items = df_page.fillna("").to_dict(orient="records")

    return jsonify({"total": total, "limit": limit, "offset": offset, "items": items})


@app.route("/api/schedule/<int:session_id>", methods=["GET"])
def api_get_session(session_id):
    """
    Return a single session row as JSON for the editor modal.
    Used by the Edit button in editor.html.
    """
    with schedule_lock:
        df = load_schedule_df()
        mask = df["session_id"] == session_id
        if not mask.any():
            return jsonify({"error": "Not found"}), 404

        row = df[mask].iloc[0].fillna("")
        return jsonify(row.to_dict())


@app.route("/api/schedule/<int:session_id>", methods=["PATCH", "PUT"])
def api_update_session(session_id):
    """
    Update session AND save lock for persistence.
    """
    payload = request.get_json(silent=True) or {}
    # Never allow changing the primary key
    payload.pop("session_id", None)

    with schedule_lock:
        df = load_schedule_df()
        mask = df["session_id"] == session_id
        if not mask.any():
            return jsonify({"error": "Not found"}), 404

        idx = df.index[mask][0]

        # 1. Update CSV (Instant Feedback)
        for key, value in payload.items():
            if key in df.columns:
                df.at[idx, key] = value
        save_schedule_df(df)

        # 2. Save Lock (Persistent)
        full_row = df.iloc[idx].to_dict()
        save_lock(full_row, payload)

        # 3. Update Chatbot (Sync)
        if chatbot:
            chatbot.update_record(session_id, payload)

    return jsonify({"status": "ok", "session_id": session_id})


@app.route("/api/schedule/<int:session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    """Delete session."""
    with schedule_lock:
        df = load_schedule_df()
        df = df[df["session_id"] != session_id]
        save_schedule_df(df)
    return jsonify({"status": "ok", "deleted": session_id})


@app.route("/api/schedule", methods=["POST"])
def api_create_session():
    """Create session."""
    payload = request.get_json(silent=True) or {}
    with schedule_lock:
        df = load_schedule_df()
        next_id = int(df["session_id"].max() + 1) if not df.empty else 1

        if df.empty:
            # If for some reason df is empty (shouldn't happen after engine run),
            # just create a row from payload + session_id.
            row_data = dict(payload)
            row_data["session_id"] = next_id
            df = pd.DataFrame([row_data])
        else:
            # Create row using existing columns, fill missing with "".
            row_data = {col: payload.get(col, "") for col in df.columns}
            row_data["session_id"] = next_id  # enforce primary key
            df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

        save_schedule_df(df)

    return jsonify({"status": "ok", "session_id": next_id}), 201



# ==============================================================================
# ROUTES: API - SCHEDULE DATA (SECURE ENDPOINT)
# ==============================================================================

@app.route('/api/schedule-data')
@handle_errors
def get_schedule_data():
    """
    🔒 SECURE API ENDPOINT - Serve schedule data as JSON
    """
    try:
        ensure_schedule_exists()
        df = load_schedule_df()
        
        if df.empty:
            return jsonify({'error': 'Schedule is empty'}), 400
        
        data = df.to_dict('records')
        return jsonify({
            'success': True,
            'count': len(data),
            'data': data,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error serving schedule data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==============================================================================
# ROUTES: API - TEACHER DETAILED STATISTICS
# ==============================================================================

@app.route('/api/teacher-stats', methods=['POST'])
@handle_errors
def get_teacher_stats():
    """
    Get detailed statistics for a specific teacher.
    
    Request body:
    {
        "teacher_name": "KELLY HERNÁNDEZ SÁNCHEZ"  (required)
    }
    
    Response:
    {
        "success": true,
        "data": {
            "teacher_name": "KELLY HERNÁNDEZ SÁNCHEZ",
            "total_classes": 171,
            "assigned": 58,
            "unassigned": 113,
            "virtual": 97,
            "labs": 58,
            "theory": 0,
            "conflicting": 3072,
            "conflicts_by_day": {
                "Lunes": 578,
                "Martes": 106,
                ...
            }
        }
    }
    """
    try:
        if not chatbot or chatbot.df is None or len(chatbot.df) == 0:
            logger.warning("⚠️  Schedule data not loaded for teacher stats")
            return jsonify({
                'success': False,
                'error': 'Schedule data not loaded. Please run the scheduler first.',
                'timestamp': datetime.now().isoformat()
            }), 503
        
        data = request.get_json()
        teacher_name = data.get('teacher_name', '').strip()
        
        if not teacher_name:
            logger.warning("❌ Teacher name not provided in teacher stats request")
            return jsonify({
                'success': False,
                'error': 'teacher_name is required',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        logger.info(f"📊 Fetching stats for teacher: {teacher_name}")
        
        # Get teacher stats from chatbot
        stats = chatbot.tool_teacher_detailed_stats(teacher_name)
        
        if not stats:
            logger.warning(f"⚠️  Teacher '{teacher_name}' not found")
            return jsonify({
                'success': False,
                'error': f"Teacher '{teacher_name}' not found in the system",
                'timestamp': datetime.now().isoformat()
            }), 404
        
        logger.info(f"✅ Teacher stats retrieved: {stats['total_classes']} classes, "
                   f"{stats['conflicting']} conflicts")
        
        return jsonify({
            'success': True,
            'data': stats,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error getting teacher stats: {e}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while retrieving teacher statistics',
            'details': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ==============================================================================
# ROUTES: CHATBOT API
# ==============================================================================

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    LLM Agent-based chatbot endpoint (Modularized).
    
    ARCHITECTURE:
    1. ScheduleChatbot (chatbot_logic.py) handles all LLM + Pandas logic
    2. This route only handles HTTP/Session management
    3. Strict Filter Pattern: No vague queries without specific parameters
    """
    try:
        data = request.get_json()
        user_query = data.get('question', data.get('message', '')).strip()
        
        logger.info(f"💬 Chat request: {user_query[:80]}...")
        
        if not user_query:
            logger.warning("Empty chat query received")
            return jsonify({'error': 'Empty question'}), 400
        
        # Check if chatbot and data are ready
        if not chatbot or chatbot.df is None or len(chatbot.df) == 0:
            logger.warning("⚠️  Schedule data not loaded for chat")
            return jsonify({
                'response': '⚠️ Schedule data not loaded yet. Please run the scheduler first.',
                'source': 'error'
            }), 503
        
        # Get conversation history from session
        if 'chat_history' not in session:
            session['chat_history'] = []
        
        # Keep last 3 exchanges for context (stateful memory)
        history_context = "\n".join([
            f"User: {h['user']}\nAI: {h['ai']}" 
            for h in session['chat_history'][-3:]
        ])
        
        logger.debug(f"📝 Chat history: {len(session['chat_history'])} exchanges")
        
        # Generate response using modularized chatbot
        response_text = chatbot.generate_response(user_query, history_context)
        
        # Update session history
        session['chat_history'].append({
            'user': user_query,
            'ai': response_text
        })
        session.modified = True
        
        logger.info(f"✅ Chat response sent ({len(response_text)} chars)")
        
        return jsonify({
            'response': response_text,
            'source': 'agentic_pandas_llm',
            'architecture': 'Modularized (chatbot_logic.py + Pandas)',
            'strict_filters': 'enabled',
            'gemini_available': GEMINI_AVAILABLE,
            'conversation_turn': len(session['chat_history']),
            'debug': {
                'query_parsed': True,
                'data_loaded': True,
                'history_used': len(session['chat_history']) > 1,
                'filters_applied': 'strict (no vague queries)'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {e}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'An error occurred while processing your query',
            'details': str(e)
        }), 500


@app.route('/api/chatbot-status')
def chatbot_status():
    """Check chatbot agent status (Data loaded + Gemini connection)."""
    try:
        if not chatbot:
            logger.warning("Chatbot not initialized")
            return jsonify({
                'available': False,
                'kb_documents': 0,
                'error': 'Chatbot not initialized'
            }), 500
        
        # Check if Pandas DataFrame is loaded
        data_loaded = chatbot.df is not None and len(chatbot.df) > 0
        
        status = {
            'available': data_loaded, 
            'kb_documents': len(chatbot.df) if data_loaded else 0,
            'kb_path': OUTPUT_CSV,
            'gemini_available': GEMINI_AVAILABLE,
            'architecture': 'Modularized (chatbot_logic.py + Pandas)',
            'vector_db': 'disabled (Pandas is more accurate)',
            'strict_filters': 'enabled',
            'requires_setup': not data_loaded
        }
        
        logger.info(f"📊 Chatbot status: {'Ready' if data_loaded else 'Waiting for schedule'}")
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"❌ Error getting chatbot status: {e}")
        return jsonify({'error': str(e), 'available': False}), 500


@app.route('/api/chatbot-health')
def chatbot_health():
    """
    Health check endpoint for chatbot diagnostics.
    
    Returns comprehensive health status including:
    - Data loading status
    - Column validation
    - Time parsing health
    - Gemini availability
    - Fuzzy matching library status
    - Lookup indexes
    """
    try:
        if not chatbot:
            logger.warning("Chatbot not initialized for health check")
            return jsonify({
                'overall_status': 'error',
                'error': 'Chatbot not initialized',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get comprehensive health check
        health = chatbot.health_check()
        
        # Log health summary
        overall = health.get('overall_status', 'unknown')
        logger.info(f"🏥 Chatbot Health: {overall.upper()}")
        for check_name, check_data in health.get('checks', {}).items():
            status_symbol = "✅" if check_data.get('status') == 'ok' else "⚠️ " if check_data.get('status') == 'warning' else "❌"
            logger.debug(f"  {status_symbol} {check_name}: {check_data.get('message', 'N/A')}")
        
        return jsonify(health), 200
        
    except Exception as e:
        logger.error(f"❌ Error in health check: {e}", exc_info=True)
        return jsonify({
            'overall_status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ==============================================================================
# RUNNER
# ==============================================================================

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    os.makedirs('Output', exist_ok=True)
    
    app.run(host="0.0.0.0", debug=True, port=5050, use_reloader=False)