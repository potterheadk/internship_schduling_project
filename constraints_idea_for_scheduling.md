### non-code plan you can paste into your docs and hand to the backend/frontend teams (or use yourself) to **improve and partially automate course assignment**. It covers:

* constraints (hard vs soft)
* new data entities / tables to add (fields & intent)
* how to represent special courses (labs, virtual, practica)
* teacher capability/availability modeling (including exclusives)
* scheduling algorithm approach (practical, no ML required)
* API and UX workflows to support safe automation & manual override
* testing, rollout and monitoring

Everything below is implementation-agnostic — no code — and ready to become tickets.

---

# 1. Rules: Hard vs Soft constraints

Separate constraints into those the scheduler **must** obey (hard) and those it **should prefer** (soft). Always enforce hard constraints on the server.

## Hard constraints (must-block / fail)

* **Time overlap (teacher):** a teacher cannot be assigned to two horario records with overlapping time windows on the same day.
* **Time overlap (room):** a classroom cannot be double-booked for overlapping time windows.
* **Course-group conflict:** courses in the same `grupo_sincro` (parent/child) that must not be scheduled simultaneously.
* **Teacher qualification:** teacher must be qualified to teach the course (subject/specialty match).
* **Teacher exclusivity:** some teachers are marked exclusive/unavailable for other assignments (e.g., research-only).
* **Teacher max hours:** `Docente.h_total + new_hours <= Docente.h_max`.
* **Room capacity:** `Aula.n_capacidad` must be >= enrolled students for the course (use numeric conversion).
* **Resource requirement match:** course requiring specific resources (lab equipment, networked IP, practica benches) must be assigned to rooms that have those resources.
* **Period/turno matching:** schedules must belong to the same `turno` / `periodo` constraints.
* **Legal/policy constraints:** any institutional rules (e.g., exam week blackout) must be enforced.

## Soft constraints (preferences / scored penalties)

* Minimize teacher’s idle time fragmentation (prefer contiguous blocks).
* Keep teacher load balanced across days.
* Prefer rooms of appropriate size (avoid huge rooms for small course).
* Prefer teacher’s preferred time windows.
* Minimize movement (assign same room for repeated sessions).
* Prefer virtual/hybrid modality if requested or if room lacks capacity.
* Respect "preferred" modality of the course (if set).

---

# 2. Data model additions (tables / fields) — what to add & why

If you can add database tables/fields, these will let the scheduler reason clearly.

> Note: match column naming to your Prisma/DB conventions; below is conceptual.

## 2.1 `teacher_qualification` (map teachers → courses/specialties)

* `id`, `docente_id`, `c_codcur` or `specialty_code`, `can_teach` (boolean), `proficiency_level` (enum: primary/secondary), `notes`.
  **Purpose:** explicit mapping of which courses a teacher may teach. Use for hard qualification checks.

## 2.2 `teacher_availability`

* `id`, `docente_id`, `day_of_week` (Mon..Sun), `start_time`, `end_time`, `type` (available/blocked), `recurrence` (weekly, single), `source` (manual/HR).
  **Purpose:** precise per-teacher hours and "exclusive" blocks (meeting, research). Use to find candidate teachers.

## 2.3 `classroom_capability` (normalize Aula resources)

* `id`, `aula_id`, `resource` (e.g., "lab\_chem", "virtual\_ip", "projector"), `value` (optional), `notes`.
  **Purpose:** query for rooms that support special courses.

## 2.4 `course_requirements`

* `id`, `curso_id`, `required_resource` (enum or text), `min_capacity`, `preferred_modality` (PRESENCIAL / VIRTUAL / HYBRID / PRACTICAL), `sessions_per_week`, `hours_per_session`.
  **Purpose:** lets scheduler match resources/time slots.

## 2.5 `teacher_exclusivity` or flag on `Docente`

* Add `exclusive` boolean and `exclusive_reason` text (or `type` enum).
  **Purpose:** mark teachers who must not be assigned except specific cases.

## 2.6 `scheduled_proposals` (staging)

* `id`, `periodo`, `turno_id`, `curso_id`, `proposed_horario_json`, `status` (proposed/accepted/rejected), `created_by`, `created_at`.
  **Purpose:** allow previewing many assignments before applying (review, audit).

## 2.7 `audit_override` (log admin overrides)

* `id`, `horario_id`, `user_id`, `reason`, `before`, `after`, `created_at`.
  **Purpose:** mandatory logging of forced assignments.

---

# 3. Special courses & classroom types

Define a taxonomy and capture it in `course_requirements` and `classroom_capability`.

* Tag courses with types: `THEORETICAL`, `PRACTICAL/LAB`, `VIRTUAL`, `HYBRID`, `FIELDWORK`.
* Tag classrooms with capabilities: `LAB_CHEM`, `LAB_COMPUTER`, `NETWORK_IP`, `VR`, `CHEM_FUMEHOOD`, `PROJECTOR`, `VIDEO_CONF`.
* For `PRACTICAL` courses: require at least one `LAB_*` capability; treat these as hard constraints.
* For `VIRTUAL` courses: allow assignment to virtual modality and `aula.ip` presence can mark rooms as hybrid; virtual-only classes could be flagged as not requiring physical aula.

---

# 4. Teacher model: specialties & exclusives

* Maintain `teacher_qualification` relationships (see 2.1).
* Store `teacher_roles`/types: `FULL_TIME`, `PART_TIME`, `GUEST`, `EXCLUSIVE`.
* Store `teacher_priority` (score) to rank teachers when multiple candidates exist.
* Track `h_total`, `h_max`, and weekly availability windows.

**Operational rule:** allow admin to mark teacher as `exclusive` (means cannot be auto-assigned) or to mark `auto_assign_allowed` boolean.

---

# 5. Scheduler algorithm (practical approach — deterministic, no ML)

Use a deterministic multi-stage algorithm that is transparent and auditable.

## Overview (preferred path)

1. **Pre-filter**: For each course create list of candidate teachers and candidate rooms filtered by hard constraints (qualification, capacity, resources, availability).
2. **Time slots generation**: Translate `turno` definitions into discrete candidate time windows (e.g., \[Mon 08:00-10:00], \[Mon 10:00-12:00], ...). If turnos have start/end ranges, split into session-sized windows based on course hours.
3. **Greedy + scoring**: For each course (order by heuristic: largest enrollment, rare resource requirement, transversal group first), pick the best slot+room+teacher triple that satisfies hard constraints and minimizes a cost function for soft constraints (teacher load, room fit, continuity).
4. **Backtracking / local search**: If greedy finds conflicts later, attempt limited backtracking: move lower-priority assignments to alternate slots to accommodate higher-priority ones.
5. **Conflict report**: Produce a priority-sorted conflict list (why it failed — no teacher with qualification available, no lab room available, teacher hour limit).
6. **Propose & stage**: Store proposals in `scheduled_proposals` for review. Admin can accept, reject, or manually modify.
7. **Commit in transaction**: When applying, perform final overlap checks and insert in a DB transaction. On conflict at commit time, fail and return details.

## Score function (for soft constraints)

Give weighted sum:

* teacher\_preference\_match (+)
* room\_size\_penalty (abs(logical-size-match))
* continuity bonus (if adjacent slots assigned to same teacher)
* preferred modality matched
* teacher\_extra\_cost (if teacher is part-time or external)

Tune weights empirically.

## Scaling

* For thousands of courses, implement batched scheduling by `turno` or `faculty`.
* Use memoization for availability checks (cache per timeslot) and invalidate when assignments are tested.

---

# 6. API & UX to support automated assignment

Add/document endpoints and UI flows that let admins preview/execute:

## Suggested endpoints (document-only)

* `POST /scheduler/preview` — input: `periodoId`, optional filters, returns proposed assignments + conflict list (no DB writes).
* `POST /scheduler/apply` — input: `proposalId` or `periodoId` & options; executes staging proposals and returns created records (atomic).
* `GET /scheduler/conflicts?periodoId=...` — return current conflicts for period (useful for dashboard).
* `GET /scheduler/proposals/:id` — fetch staged proposals for review.
* `POST /horario/validate` — quick check for a single proposed slot (for realtime UI checks).

## UI behavior (assign page `/coa/asignarhorario`)

* Add a “Preview auto-assign” button that calls `POST /scheduler/preview` and shows:

  * proposed schedule table,
  * conflict heatmap,
  * clickable suggestions: “suggest alternate room”, “suggest alternate teacher”, “accept”.
* Allow filters: prioritize by resource type, restrict to specific teachers, or exclude certain classrooms.
* Provide explicit admin override controls with a mandatory reason (log to `audit_override`).

---

# 7. Validation & safety (server-side)

* **Always** validate on server regardless of frontend checks.
* Run conflict detection again in the same transaction before commit (TOCTOU defense).
* Rate-limit bulk endpoints (async scheduler) and convert heavy operations to background jobs if long-running.
* Log all auto-assign runs (who ran them, parameters, runtime, counts) to `Log`.

---

# 8. Testing checklist (manual & automated)

* Unit tests for overlap detection (edge cases for exact touching times: end == start).
* Unit tests for qualification filtering & capacity checks.
* Integration tests for `scheduler/preview` that use a small sample DB with known conflicts.
* Performance test: run scheduler on realistic dataset and measure time + memory; add pagination for proposals if data grows.
* QA manual tests:

  * Assign a lab-only course and ensure it picks lab rooms only.
  * Simulate teacher with limited hours and verify it refuses assignments beyond `h_max`.
  * Test admin override flow and confirm `audit_override` is recorded.

---

# 9. Monitoring & metrics

* Track:

  * scheduler run duration
  * number of conflicts per run
  * number of proposals accepted / rejected
  * top reasons for conflicts (no teacher, no room, hours)
* Expose a simple dashboard (or `GET /dashboard/scheduler-stats`) for operations.

---

# 10. Prioritized next steps (practical roadmap)

1. **Data model**: add `teacher_availability`, `teacher_qualification`, `course_requirements`, `classroom_capability` — minimal fields first.
2. **Validation endpoints**: add `POST /horario/validate` for single-slot checks.
3. **Preview scheduler**: implement `POST /scheduler/preview` (non-destructive) that uses greedy + backtracking — return proposals + conflicts.
4. **UI**: wire Preview into `/coa/asignarhorario` as “Preview Auto-Assign” and show suggestion UI.
5. **Audit & logging**: ensure `createLog` + `audit_override` capture proposals & overrides.
6. **Test**: run integration tests and a performance pass on realistic data.
7. **Iterate**: tune scoring weights based on feedback from admin users.

---

# 11. Example documentation snippets to paste into your docs

### “Hard constraints” list (copy to policy doc)

* No overlapping teacher assignments.
* No overlapping room assignments.
* Teacher must be qualified for the course.
* Teacher hours must not exceed `h_max`.
* Room must have required resources and capacity.

### “API addition” brief (copy to API docs)

* `POST /scheduler/preview` — body: `{ periodoId, turnoId?, filters? }` returns `{ proposals: [...], conflicts: [...] }`
* `POST /scheduler/apply` — body: `{ proposalId }` returns commit results or errors.

