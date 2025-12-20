This guide provides a minimal setup to get  **UMA Scheduler & AI Assistant** project running from a fresh GitHub clone.

---

# 📅 UMA Scheduler & AI Assistant

An intelligent university scheduling system featuring an automated engine, a drag-and-drop interactive viewer, an analytics dashboard, and a Gemini-powered chatbot.

##  Quick Start

### 1. Prerequisites
* **Python 3.9+**
* **Google Gemini API Key** (for the Chatbot features)

### 2. Clone and Install
```bash
# Clone the repository
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install flask pandas python-dotenv google-generativeai
```

### 3. Environment Configuration
Create a file named `.env` in the root directory:

```env
# Flask Settings
SECRET_KEY=your_super_secret_key_here

# AI Logic (Gemini)
GOOGLE_API_KEY=your_gemini_api_key_from_google_ai_studio

# Environment
FLASK_ENV=development
```

### 4. Required Project Structure
The application expects specific folders to exist for logging and data persistence. Ensure your directory looks like this:
```text
project-root/
├── app.py
├── chatbot_logic.py
├── scheduler_engine.py
├── analytics_engine.py
├── .env
├── data/                 # Stores CSVs, locks, and logs
├── templates/            # HTML files
│   ├── home.html
│   ├── index.html (Viewer)
│   ├── editor.html
│   └── dashboard.html
└── static/               # JS (Drag-n-Drop), CSS
```
*Note: `app.py` will attempt to create the `data/` folder automatically if it's missing.*

### 5. Running the Application
```bash
python app.py
```
* The app will start at `http://localhost:5050`.
* **First Run:** On the first launch, the app will automatically trigger `generate_schedule()` to create the initial `final_schedule.csv` if it doesn't exist.

---

## 🛠 Features Setup

### 1. The Scheduler Engine
The system uses `UMA_Scheduler_Engine` (from `scheduler_engine.py`). 
* If you modify schedule constraints, click **Regenerate** in the UI. 
* It respects manual edits saved in `data/manual_locks.json`.

### 2. The Chatbot (AI)
The chatbot uses **Gemini 1.5** via `chatbot_logic.py`. 
* It performs "Agentic Pandas" lookups.
* It can answer questions like: *"Which rooms are free on Monday at 10 AM?"* or *"How many conflicts does Professor Smith have?"*

### 3. Manual Locking (Persistence)
When you move a class using the **Drag & Drop Viewer** or the **Editor**, the app saves a "Lock." Even if you regenerate the whole schedule, your manual moves will remain fixed.

---

## 🛑 Troubleshooting

*   **Chatbot is disabled:** Ensure your `GOOGLE_API_KEY` is valid in the `.env` file and that you have an internet connection.
*   **CSV Not Found:** Ensure your `scheduler_engine.py` is correctly configured to output to the path defined as `OUTPUT_CSV`.
*   **Port Conflict:** If port `5050` is busy, change the `port=5050` line at the bottom of `app.py`.



