/* viewer.js */

// --- Configuration ---
const CONFIG = {
    API_URL: '/api/schedule',
    DAYS: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    HOURS_START: 6,
    HOURS_END: 22,
    // UPDATE: Added Term (n_codper) and Division
    FILTERS: [
        { key: 'n_codper', label: 'Term' },
        { key: 'division', label: 'Division' },
        { key: 'n_ciclo', label: 'Cycle' },
        { key: 'c_nomcur', label: 'Course' },
        { key: 'teacher_names', label: 'Teacher' },
        { key: 'room_id', label: 'Room' },
        { key: 'nomesp', label: 'Specialty' }
    ]
};

// --- State ---
let allSessions = [];
let filteredSessions = [];
let activeFilters = {};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initFilters();
    buildGridStructure();
    loadData();
    setupEventListeners();
});

// --- 1. Data Loading ---
async function loadData() {
    updateStatus("Loading data...", true);
    try {
        // Fetch unlimited rows
        const res = await fetch(`${CONFIG.API_URL}?limit=10000`);
        const data = await res.json();
        
        // Normalize Data
        allSessions = data.items.map(item => ({
            ...item,
            id: item.session_id, // Ensure we have a stable ID
            start_time: (item.start_time || "00:00").substring(0, 5),
            day_of_week: item.day_of_week || "Unscheduled",
            // Ensure these fields exist for filtering even if empty
            n_codper: item.n_codper || "",
            division: item.division || ""
        }));

        populateFilterOptions();
        applyFilters();
        updateStatus("System Ready", true);
    } catch (err) {
        console.error(err);
        updateStatus("Error loading data", false);
    }
}

// --- 2. Grid Construction ---
function buildGridStructure() {
    const tbody = document.getElementById('calendarBody');
    const timeSelect = document.getElementById('editTime');
    tbody.innerHTML = '';
    timeSelect.innerHTML = '';

    for (let h = CONFIG.HOURS_START; h < CONFIG.HOURS_END; h++) {
        const timeStr = `${String(h).padStart(2, '0')}:00`;
        
        // Populate Modal Options
        const opt = document.createElement('option');
        opt.value = timeStr;
        opt.textContent = timeStr;
        timeSelect.appendChild(opt);

        // Lunch Break Row
        if (h === 13) {
            const tr = document.createElement('tr');
            tr.className = 'lunch-row';
            tr.innerHTML = `<td class="time-col">13:00</td><td colspan="6">LUNCH BREAK</td>`;
            tbody.appendChild(tr);
            continue;
        }

        // Standard Row
        const tr = document.createElement('tr');
        tr.innerHTML = `<td class="time-col">${timeStr}</td>`;

        CONFIG.DAYS.forEach(day => {
            const td = document.createElement('td');
            td.className = 'calendar-cell';
            td.dataset.day = day;
            td.dataset.time = timeStr;
            
            // Drag Drop Events
            td.addEventListener('dragover', handleDragOver);
            td.addEventListener('dragleave', handleDragLeave);
            td.addEventListener('drop', handleDrop);

            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    }
}

// --- 3. Rendering ---
function render() {
    // Clear Grid
    document.querySelectorAll('.calendar-cell').forEach(td => td.innerHTML = '');
    const unscheduledGrid = document.getElementById('unscheduledGrid');
    unscheduledGrid.innerHTML = '';
    
    let unscheduledCount = 0;

    filteredSessions.forEach(session => {
        const card = createCard(session);
        
        // Find Cell
        if (session.start_time === "00:00" || !session.day_of_week) {
            unscheduledGrid.appendChild(card);
            unscheduledCount++;
        } else {
            const selector = `.calendar-cell[data-day="${session.day_of_week}"][data-time="${session.start_time}"]`;
            const cell = document.querySelector(selector);
            if (cell) cell.appendChild(card);
            else {
                // Fallback if time/day doesn't match grid
                unscheduledGrid.appendChild(card);
                unscheduledCount++;
            }
        }
    });

    // Toggle Unscheduled Section
    document.getElementById('unscheduledSection').classList.toggle('hidden', unscheduledCount === 0);
}

function createCard(session) {
    const div = document.createElement('div');
    
    // Determine Style Class
    let typeClass = 'theory';
    const rid = (session.room_id || "").toUpperCase();
    if (rid.includes('CONFLICT')) typeClass = 'conflict';
    else if (rid.includes('VIRTUAL')) typeClass = 'virtual';
    else if (session.activity_type === 'lab') typeClass = 'lab';

    div.className = `session-card ${typeClass}`;
    div.draggable = true;
    div.dataset.id = session.id;

    // Content
    div.innerHTML = `
        <div class="card-header">
            <span>${session.c_codcur || "?"}</span>
            <span class="card-room">${session.room_id || "No Room"}</span>
        </div>
        <div class="card-details">
            <div>${(session.teacher_names || "No Teacher").substring(0, 18)}..</div>
            <div>${session.c_nomcur || ""}</div>
        </div>
    `;

    // Events
    div.addEventListener('dragstart', handleDragStart);
    div.addEventListener('dragend', handleDragEnd);
    div.addEventListener('click', (e) => {
        e.stopPropagation(); // prevent bubbling
        openEditModal(session);
    });

    return div;
}

// --- 4. Drag and Drop Logic ---
let draggedId = null;

function handleDragStart(e) {
    draggedId = this.dataset.id;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', draggedId);
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
    draggedId = null;
    document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
}

function handleDragOver(e) {
    e.preventDefault(); // Necessary to allow dropping
    this.classList.add('drag-over');
    e.dataTransfer.dropEffect = 'move';
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

async function handleDrop(e) {
    e.preventDefault();
    this.classList.remove('drag-over');
    
    const newDay = this.dataset.day;
    const newTime = this.dataset.time;

    if (!draggedId || !newDay || !newTime) return;

    // Optimistic UI Update
    const sessionIndex = allSessions.findIndex(s => String(s.id) === String(draggedId));
    if (sessionIndex > -1) {
        const oldSession = { ...allSessions[sessionIndex] };
        
        // Update local state
        allSessions[sessionIndex].day_of_week = newDay;
        allSessions[sessionIndex].start_time = newTime;
        applyFilters(); // Re-render immediately

        // API Call
        try {
            updateStatus("Saving...", true);
            const res = await fetch(`${CONFIG.API_URL}/${draggedId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    day_of_week: newDay,
                    start_time: newTime
                })
            });

            if (!res.ok) throw new Error("Save failed");
            updateStatus("Moved successfully", true);

        } catch (err) {
            console.error(err);
            updateStatus("Move failed! Reverting...", false);
            // Revert state
            allSessions[sessionIndex] = oldSession;
            applyFilters();
        }
    }
}

// --- 5. Filtering ---
function initFilters() {
    const container = document.getElementById('filterContainer');
    container.innerHTML = ''; // Clear existing
    
    CONFIG.FILTERS.forEach(f => {
        const group = document.createElement('div');
        group.className = 'filter-group';
        group.innerHTML = `
            <label>${f.label}</label>
            <select id="filter-${f.key}" data-key="${f.key}">
                <option value="all">All</option>
            </select>
        `;
        container.appendChild(group);
        
        // Event Listener
        group.querySelector('select').addEventListener('change', (e) => {
            activeFilters[f.key] = e.target.value;
            applyFilters();
        });
    });
}

function populateFilterOptions() {
    CONFIG.FILTERS.forEach(f => {
        const select = document.getElementById(`filter-${f.key}`);
        const uniqueValues = [...new Set(allSessions.map(s => s[f.key]))].filter(Boolean).sort();
        
        // Preserve selection or default to all
        const currentVal = select.value;
        select.innerHTML = '<option value="all">All</option>';
        
        uniqueValues.forEach(val => {
            const opt = document.createElement('option');
            opt.value = val;
            opt.textContent = val;
            select.appendChild(opt);
        });
        select.value = currentVal;
    });
}

function applyFilters() {
    filteredSessions = allSessions.filter(s => {
        for (const key in activeFilters) {
            if (activeFilters[key] !== 'all' && String(s[key]) !== activeFilters[key]) {
                return false;
            }
        }
        return true;
    });
    render();
}

// --- 6. Modal / Editing ---
const modal = document.getElementById('editModal');
const editForm = document.getElementById('editForm');

function openEditModal(session) {
    document.getElementById('editSessionId').value = session.id;
    document.getElementById('editCourse').value = session.c_nomcur;
    document.getElementById('editDay').value = session.day_of_week;
    document.getElementById('editTime').value = session.start_time;
    document.getElementById('editRoom').value = session.room_id;
    document.getElementById('editTeacher').value = session.teacher_names;
    
    // Remove "hidden" class to show
    modal.classList.remove('hidden');
}

function closeEditModal() {
    // Add "hidden" class to hide
    modal.classList.add('hidden');
}

async function saveSession() {
    const id = document.getElementById('editSessionId').value;
    const payload = {
        day_of_week: document.getElementById('editDay').value,
        start_time: document.getElementById('editTime').value,
        room_id: document.getElementById('editRoom').value,
        teacher_names: document.getElementById('editTeacher').value
    };

    updateStatus("Saving...", true);
    closeEditModal();

    try {
        const res = await fetch(`${CONFIG.API_URL}/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            // Update Local
            const idx = allSessions.findIndex(s => String(s.id) === String(id));
            if (idx > -1) {
                Object.assign(allSessions[idx], payload);
                applyFilters();
            }
            updateStatus("Session updated", true);
        } else {
            throw new Error("API Error");
        }
    } catch (err) {
        alert("Failed to save changes.");
        updateStatus("Error saving", false);
    }
}

// --- 7. Utilities & Listeners ---
function setupEventListeners() {
    // Buttons
    document.getElementById('resetFiltersBtn').addEventListener('click', () => {
        document.querySelectorAll('select[id^="filter-"]').forEach(s => s.value = 'all');
        activeFilters = {};
        applyFilters();
    });

    document.getElementById('refreshBtn').addEventListener('click', loadData);
    
    document.getElementById('regenBtn').addEventListener('click', async () => {
        if(!confirm("Are you sure? This will wipe manual edits.")) return;
        updateStatus("Regenerating...", true);
        await fetch('/regenerate', { method: 'POST' });
        loadData();
    });

    // Modal
    document.querySelectorAll('.close-modal').forEach(b => b.addEventListener('click', closeEditModal));
    document.getElementById('saveSessionBtn').addEventListener('click', saveSession);
}

function updateStatus(msg, isOk) {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    text.textContent = msg;
    if (isOk) dot.className = 'dot';
    else dot.className = 'dot error';
}