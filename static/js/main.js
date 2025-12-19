// ---------- Shared utilities ----------

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
    }
    return res.json();
}

async function putJSON(url, body) {
    const res = await fetch(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
}

// Global: keep last loaded metadata & schedule
let globalMetadata = null;
let globalSchedule = [];

// Modal state
let activeSession = null;

// Days order
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// ---------- Modal helpers (shared between calendar & sessions) ----------

function setupModalBase() {
    const modal = document.getElementById("edit-modal");
    if (!modal) return;

    const closeBtn = document.getElementById("modal-close");
    const cancelBtn = document.getElementById("modal-cancel");

    const hide = () => {
        modal.classList.add("hidden");
        activeSession = null;
        const errBox = document.getElementById("modal-error");
        if (errBox) errBox.textContent = "";
    };

    if (closeBtn) closeBtn.addEventListener("click", hide);
    if (cancelBtn) cancelBtn.addEventListener("click", hide);
    modal.querySelector(".modal-backdrop").addEventListener("click", hide);

    // Populate day options
    const daySelect = document.getElementById("modal-day");
    if (daySelect && daySelect.options.length === 0) {
        DAYS.forEach((d) => {
            const opt = document.createElement("option");
            opt.value = d;
            opt.textContent = d;
            daySelect.appendChild(opt);
        });
    }

    const saveBtn = document.getElementById("modal-save");
    if (saveBtn) {
        saveBtn.addEventListener("click", async () => {
            if (!activeSession) return;
            const errorBox = document.getElementById("modal-error");
            errorBox.textContent = "";

            const payload = {
                day_of_week: document.getElementById("modal-day").value,
                start_time: document.getElementById("modal-start-time").value,
                end_time: document.getElementById("modal-end-time").value,
                room_id: document.getElementById("modal-room").value,
                turno: document.getElementById("modal-turno").value,
                activity_type: document.getElementById("modal-activity").value,
            };

            // Basic client validation
            if (!payload.start_time || !payload.end_time) {
                errorBox.textContent = "Start and end time are required.";
                return;
            }
            if (!payload.day_of_week) {
                errorBox.textContent = "Day of week is required.";
                return;
            }

            try {
                const updated = await putJSON(`/api/session/${activeSession.id}`, payload);
                // Merge into globalSchedule
                const idx = globalSchedule.findIndex((s) => String(s.id) === String(updated.id));
                if (idx !== -1) {
                    globalSchedule[idx] = updated;
                }

                // Refresh whichever view we are on
                const page = document.body.dataset.page;
                if (page === "calendar") {
                    renderCalendar(globalSchedule);
                } else if (page === "sessions") {
                    renderSessionsTable(globalSchedule);
                }

                document.getElementById("edit-modal").classList.add("hidden");
                activeSession = null;
            } catch (err) {
                console.error(err);
                errorBox.textContent = "Failed to save. Check server logs.";
            }
        });
    }
}

function openEditModal(session) {
    activeSession = session;
    const modal = document.getElementById("edit-modal");
    if (!modal) return;

    document.getElementById("modal-course").textContent =
        `${session.c_codcur} - ${session.c_nomcur}`;
    document.getElementById("modal-program").textContent =
        `${session.c_codesp} • Ciclo ${session.n_ciclo} • Div ${session.division}`;

    document.getElementById("modal-day").value = session.day_of_week || "Monday";
    document.getElementById("modal-start-time").value = session.start_time || "06:00";
    document.getElementById("modal-end-time").value = session.end_time || "07:00";
    document.getElementById("modal-room").value = session.room_id || "";
    document.getElementById("modal-turno").value = session.turno || "Diurno";
    document.getElementById("modal-activity").value = session.activity_type || "theory";

    const errBox = document.getElementById("modal-error");
    if (errBox) errBox.textContent = "";

    modal.classList.remove("hidden");
}

// ---------- Calendar Page Logic ----------

function buildHourRows() {
    const hours = [];
    for (let h = 6; h < 22; h++) {
        if (h === 13) {
            hours.push({ hour: h, lunch: true });
        } else {
            hours.push({ hour: h, lunch: false });
        }
    }
    return hours;
}

function renderCalendar(schedule) {
    const tbody = document.getElementById("calendar-body");
    if (!tbody) return;

    const hours = buildHourRows();
    tbody.innerHTML = "";

    hours.forEach((rowInfo) => {
        const tr = document.createElement("tr");
        if (rowInfo.lunch) tr.classList.add("lunch-row");

        const timeCell = document.createElement("td");
        timeCell.classList.add("time-col");
        const labelSpan = document.createElement("span");
        labelSpan.classList.add("time-label");
        labelSpan.textContent = `${String(rowInfo.hour).padStart(2, "0")}:00`;
        timeCell.appendChild(labelSpan);
        tr.appendChild(timeCell);

        DAYS.forEach((day) => {
            const td = document.createElement("td");
            if (rowInfo.lunch) {
                td.colSpan = 1;
                td.style.background = "rgba(255,255,255,0.02)";
            } else {
                const hourStr = `${String(rowInfo.hour).padStart(2, "0")}:00`;
                const sessionsAtThisTime = schedule.filter(
                    (s) =>
                        s.day_of_week === day &&
                        s.start_time === hourStr
                );
                sessionsAtThisTime.forEach((s) => {
                    const pill = document.createElement("span");
                    pill.classList.add("session-pill");
                    if (s.activity_type === "lab") pill.classList.add("lab");
                    if (s.activity_type === "virtual") pill.classList.add("virtual");

                    pill.textContent = `${s.c_codcur} (${s.room_id || "no room"})`;
                    pill.title = `${s.c_nomcur}\n${s.teacher_names || ""}`;

                    pill.addEventListener("click", () => openEditModal(s));
                    td.appendChild(pill);
                });
            }
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });
}

async function initCalendarPage() {
    // Load metadata for filters
    const meta = await fetchJSON("/api/metadata");
    globalMetadata = meta;

    // Populate filter selects
    const periodSel = document.getElementById("filter-period");
    const progSel = document.getElementById("filter-program");
    const turnoSel = document.getElementById("filter-turno");
    const actSel = document.getElementById("filter-activity");
    const roomSel = document.getElementById("filter-room");

    const addOptions = (select, values, includeAll = true) => {
        select.innerHTML = "";
        if (includeAll) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "All";
            select.appendChild(opt);
        }
        values.forEach((v) => {
            const opt = document.createElement("option");
            opt.value = v;
            opt.textContent = v;
            select.appendChild(opt);
        });
    };

    addOptions(periodSel, meta.periods);
    addOptions(progSel, meta.programs);
    addOptions(turnoSel, meta.turnos);
    addOptions(actSel, meta.activity_types);
    addOptions(roomSel, meta.rooms);

    const loadAndRender = async () => {
        const params = new URLSearchParams();

        if (periodSel.value) params.append("period", periodSel.value);
        if (progSel.value) params.append("program", progSel.value);
        if (turnoSel.value) params.append("turno", turnoSel.value);
        if (actSel.value) params.append("activity_type", actSel.value);
        if (roomSel.value) params.append("room", roomSel.value);

        const url = `/api/schedule?${params.toString()}`;
        const data = await fetchJSON(url);
        globalSchedule = data;
        renderCalendar(data);
    };

    document.getElementById("btn-apply-filters").addEventListener("click", () => {
        loadAndRender().catch((err) => console.error(err));
    });

    // Initial load
    loadAndRender().catch((err) => console.error(err));
}

// ---------- Dashboard Page Logic ----------

function renderBarList(container, obj) {
    container.innerHTML = "";
    const entries = Object.entries(obj || {});
    if (entries.length === 0) {
        container.textContent = "No data";
        return;
    }
    const maxVal = Math.max(...entries.map(([, v]) => v));
    entries.forEach(([label, value]) => {
        const item = document.createElement("div");
        item.classList.add("stat-bar-item");

        const lbl = document.createElement("div");
        lbl.classList.add("stat-bar-label");
        lbl.textContent = label || "(empty)";

        const bar = document.createElement("div");
        bar.classList.add("stat-bar");

        const inner = document.createElement("div");
        inner.classList.add("stat-bar-inner");
        const pct = maxVal > 0 ? (value / maxVal) * 100 : 0;
        inner.style.width = `${pct}%`;
        bar.appendChild(inner);

        const valSpan = document.createElement("div");
        valSpan.classList.add("stat-bar-value");
        valSpan.textContent = value;

        item.appendChild(lbl);
        item.appendChild(bar);
        item.appendChild(valSpan);

        container.appendChild(item);
    });
}

async function initDashboardPage() {
    const loading = document.getElementById("dashboard-loading");
    const errBox = document.getElementById("dashboard-error");
    const content = document.getElementById("dashboard-content");

    try {
        const stats = await fetchJSON("/api/dashboard");
        loading.classList.add("hidden");
        content.classList.remove("hidden");

        document.getElementById("stat-total").textContent = stats.total_sessions || 0;
        renderBarList(document.getElementById("stat-activity"), stats.by_activity_type);
        renderBarList(document.getElementById("stat-turno"), stats.by_turno);
        renderBarList(document.getElementById("stat-day"), stats.by_day);

        const roomsUl = document.getElementById("stat-top-rooms");
        roomsUl.innerHTML = "";
        (stats.top_rooms || []).forEach(([room, count]) => {
            const li = document.createElement("li");
            li.textContent = `${room || "(empty)"} — ${count}`;
            roomsUl.appendChild(li);
        });

        const teachersUl = document.getElementById("stat-top-teachers");
        teachersUl.innerHTML = "";
        (stats.top_teachers || []).forEach(([name, count]) => {
            const li = document.createElement("li");
            li.textContent = `${name || "(empty)"} — ${count}`;
            teachersUl.appendChild(li);
        });
    } catch (err) {
        console.error(err);
        loading.classList.add("hidden");
        errBox.classList.remove("hidden");
        errBox.textContent = "Failed to load dashboard stats.";
    }
}

// ---------- Sessions Page Logic ----------

function renderSessionsTable(schedule) {
    const tbody = document.getElementById("sessions-table-body");
    if (!tbody) return;

    const searchVal = (document.getElementById("table-search").value || "").toLowerCase();

    tbody.innerHTML = "";

    schedule.forEach((s) => {
        const rowText = `
            ${s.c_codcur || ""} ${s.c_nomcur || ""} ${s.teacher_names || ""} ${s.room_id || ""}
        `.toLowerCase();

        if (searchVal && !rowText.includes(searchVal)) {
            return; // skip if not matching search
        }

        const tr = document.createElement("tr");

        const addCell = (text) => {
            const td = document.createElement("td");
            td.textContent = text;
            tr.appendChild(td);
        };

        addCell(s.n_codper);
        addCell(s.c_codesp);
        addCell(s.n_ciclo);
        addCell(s.division);
        addCell(`${s.c_codcur} - ${s.c_nomcur}`);
        addCell(s.activity_type);
        addCell(s.turno);
        addCell(s.day_of_week);
        addCell(s.start_time);
        addCell(s.end_time);
        addCell(s.room_id);
        addCell(s.teacher_names);

        const tdActions = document.createElement("td");
        const btnEdit = document.createElement("button");
        btnEdit.classList.add("btn-secondary");
        btnEdit.textContent = "Edit";
        btnEdit.addEventListener("click", () => openEditModal(s));
        tdActions.appendChild(btnEdit);
        tr.appendChild(tdActions);

        tbody.appendChild(tr);
    });
}

async function initSessionsPage() {
    const meta = await fetchJSON("/api/metadata");
    globalMetadata = meta;

    const periodSel = document.getElementById("table-filter-period");
    const progSel = document.getElementById("table-filter-program");
    const turnoSel = document.getElementById("table-filter-turno");
    const actSel = document.getElementById("table-filter-activity");
    const roomSel = document.getElementById("table-filter-room");

    const addOptions = (select, values, includeAll = true) => {
        select.innerHTML = "";
        if (includeAll) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "All";
            select.appendChild(opt);
        }
        values.forEach((v) => {
            const opt = document.createElement("option");
            opt.value = v;
            opt.textContent = v;
            select.appendChild(opt);
        });
    };

    addOptions(periodSel, meta.periods);
    addOptions(progSel, meta.programs);
    addOptions(turnoSel, meta.turnos);
    addOptions(actSel, meta.activity_types);
    addOptions(roomSel, meta.rooms);

    const loadAndRender = async () => {
        const params = new URLSearchParams();

        if (periodSel.value) params.append("period", periodSel.value);
        if (progSel.value) params.append("program", progSel.value);
        if (turnoSel.value) params.append("turno", turnoSel.value);
        if (actSel.value) params.append("activity_type", actSel.value);
        if (roomSel.value) params.append("room", roomSel.value);

        const url = `/api/schedule?${params.toString()}`;
        const data = await fetchJSON(url);
        globalSchedule = data;
        renderSessionsTable(data);
    };

    document.getElementById("table-apply-filters").addEventListener("click", () => {
        loadAndRender().catch((err) => console.error(err));
    });

    document.getElementById("table-search").addEventListener("input", () => {
        renderSessionsTable(globalSchedule);
    });

    // Initial load
    loadAndRender().catch((err) => console.error(err));
}

// ---------- Bootstrapping ----------

document.addEventListener("DOMContentLoaded", () => {
    setupModalBase();

    const page = document.body.dataset.page;
    if (page === "calendar") {
        initCalendarPage().catch((err) => console.error(err));
    } else if (page === "dashboard") {
        initDashboardPage().catch((err) => console.error(err));
    } else if (page === "sessions") {
        initSessionsPage().catch((err) => console.error(err));
    }
});
