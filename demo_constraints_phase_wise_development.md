This plan follows the standard software testing pyramid, starting with small, isolated components and building up to a full system test with real users.

---

### **Phase 0: Prerequisite - Test Data Setup**

Before writing a single test, you need a controlled and predictable dataset. This is the most critical step for testing a complex system like a scheduler.

**Step 1: Create a Seed Script or Test Database Snapshot**
This script should populate the database with a diverse set of entities that cover all your key scenarios.

**Step 2: Define Your Cast of Characters**
*   **Teachers (`Docente`):**
    *   **Teacher A (Standard):** Dr. Evans. Qualified for `CS101`, `CS201`. Available Mon-Fri, 9am-5pm.
    *   **Teacher B (Limited Hours):** Prof. Smith. Qualified for `PHY200`. Max hours (`h_max`) set to 10. Currently has 8 hours assigned.
    *   **Teacher C (Specific Availability):** Dr. Jones. Qualified for `CHEM300`. Only available Tue/Thu afternoons (`teacher_availability`).
    *   **Teacher D (Exclusive):** Dr. Research. Flagged as `exclusive = true`. Should not be auto-assigned.
    *   **Teacher E (Unqualified):** Mr. Davis. Not qualified for any advanced courses in the test `turno`.
*   **Classrooms (`Aula`):**
    *   **Room 101:** Standard classroom. Capacity: 30.
    *   **Room 202:** Large lecture hall. Capacity: 150.
    *   **Room 301-LAB:** Chemistry Lab. Capacity: 20. Has `classroom_capability` "LAB_CHEM".
    *   **Room 302-LAB:** Another Chemistry Lab. Capacity: 20. Has `classroom_capability` "LAB_CHEM".
*   **Courses (`Curso`):**
    *   **CS101:** Intro to CS. Enrolled: 25. Requires 4 hours/week.
    *   **PHY200:** Physics II. Enrolled: 120. Requires 3 hours/week.
    *   **CHEM300:** Organic Chemistry. Enrolled: 18. Requires a "LAB_CHEM" room (`course_requirements`).
    *   **CHEM301:** Another lab course that will create a conflict. Enrolled: 15. Also requires "LAB_CHEM".
*   **Shift (`Turno`):**
    *   Create a specific `turno` for the upcoming semester (e.g., `id=99`, Period `20251`) that will be the target for all tests.

---

### **Phase 1: Unit Testing (Backend Logic)**

Focus on the smallest pieces of your code: the individual functions that check constraints and calculate scores. These tests should be fast and isolated.

**Step 3: Test the Hard Constraint Checkers**
For each function, test the "true", "false", and edge cases.
*   **`checkTeacherOverlap(new_schedule, existing_schedules)`:**
    *   **Pass:** `new_schedule` is Mon 10-12, an existing one is Mon 8-10 (back-to-back).
    *   **Fail:** `new_schedule` is Mon 10-12, an existing one is Mon 11-1.
    *   **Edge Case:** `new_schedule` is Mon 10-12, an existing one is Mon 12-2 (should pass).
*   **`checkRoomOverlap(...)`:** Use the same logic as the teacher overlap.
*   **`checkTeacherQualification(teacher_A, CS101)`:** Should return `true`.
*   **`checkTeacherQualification(teacher_E, CHEM300)`:** Should return `false`.
*   **`checkRoomCapacity(Room_101, CS101)`:** Should return `true` (30 > 25).
*   **`checkRoomCapacity(Room_101, PHY200)`:** Should return `false` (30 < 120).
*   **`checkRoomResources(Room_301_LAB, CHEM300)`:** Should return `true`.
*   **`checkRoomResources(Room_101, CHEM300)`:** Should return `false`.

**Step 4: Test the Soft Constraint Scoring Function**
*   **`calculateScore(proposal)`:**
    *   Verify a proposal assigning a course to a teacher during their preferred time gets a higher score.
    *   Verify a proposal assigning `PHY200` (120 students) to the lecture hall (capacity 150) gets a better score than assigning `CS101` (25 students) to it.
    *   Verify a proposal that places two of a teacher's classes back-to-back gets a "continuity bonus".

---

### **Phase 2: API / Integration Testing**

Test the API endpoints to ensure they correctly use the underlying logic and interact with the database. Use tools like Postman, Insomnia, or an automated framework like Jest with Supertest.

**Step 5: Test the Validation Endpoint (`POST /horario/validate`)**
*   **Scenario 1 (Valid):** Send a payload to assign `CS101` to `Teacher A` in `Room 101` on Monday at 2pm. Expect a `200 OK` with `{"success": true}`.
*   **Scenario 2 (Invalid - Teacher Conflict):** Manually create a schedule for `Teacher A` at that time, then send the same payload. Expect `200 OK` (or `400 Bad Request`) with `{"success": false, "errors": ["Teacher time conflict..."]}`.

**Step 6: Test the Preview Endpoint (`POST /scheduler/preview`)**
*   **Scenario 1 (Happy Path):** Call the endpoint targeting your clean test `turno`. Expect a `200 OK` response with:
    *   `proposals`: An array of proposed schedule assignments.
    *   `conflicts`: An empty array.
    *   Verify that `CHEM300` was assigned to a LAB room and `PHY200` was assigned to the large lecture hall.
*   **Scenario 2 (Guaranteed Conflict):** Add `CHEM301` to the `turno`. Now there are two courses needing a lab, but maybe you only make one lab room available in the test data. Call the endpoint. Expect a `200 OK` response with:
    *   `proposals`: A partial list of assignments.
    *   `conflicts`: An array containing an object explaining that `CHEM301` could not be scheduled due to "No available rooms with required capability: LAB_CHEM".
*   **Scenario 3 (Exclusive Teacher):** Verify that `Teacher D` (Dr. Research) was not assigned any courses in the proposals.

**Step 7: Test the Apply Endpoint (`POST /scheduler/apply`)**
*   **Scenario 1 (Successful Apply):**
    1.  Call `/scheduler/preview` to get a valid `proposalId`.
    2.  Call `/scheduler/apply` with that `proposalId`.
    3.  Expect a `201 Created` response.
    4.  Query the database directly (or via `GET /schedule/shift/:shift_id`) to confirm that the `Horario` records were actually created and match the proposal.
*   **Scenario 2 (Stale Proposal - TOCTOU defense):**
    1.  Call `/scheduler/preview` to get a `proposalId`.
    2.  Manually assign `Teacher A` to a conflicting time slot via `POST /schedule`.
    3.  Call `/scheduler/apply` with the now-stale `proposalId`.
    4.  Expect a `409 Conflict` response explaining that the proposal could not be committed due to a conflict discovered at the last second. Verify the database transaction was rolled back (no partial data was saved).

---

### **Phase 3: End-to-End (E2E) Testing**

Simulate a complete user workflow from the perspective of the frontend. Use a browser automation tool like Cypress or Playwright.

**Step 8: The Full "Happy Path" Workflow**
1.  Log in as an admin user.
2.  Navigate to the `/coa/asignarhorario` page for your test `turno`.
3.  Assert that the schedule view is empty.
4.  Click the "Preview Auto-Assign" button.
5.  Assert that the UI updates to show a table with the proposed assignments and a message saying "No conflicts found."
6.  Click the "Apply Schedule" button.
7.  Assert that a success modal appears and the main schedule view now shows the newly created, permanent schedule blocks.

**Step 9: The Conflict Resolution Workflow**
1.  Set up the data to have the lab room conflict from Step 6.
2.  Log in and navigate to the scheduling page.
3.  Click "Preview Auto-Assign."
4.  Assert that the UI displays a clear, human-readable conflict report: "Conflict: Course 'Organic Chemistry II' could not be scheduled. Reason: No available rooms with required resources (LAB_CHEM)."
5.  In the UI, manually assign one of the lab courses to an evening slot.
6.  Click "Preview Auto-Assign" again.
7.  Assert that the conflict message is gone and a full proposal is now displayed.

---

### **Phase 4: User Acceptance Testing (UAT)**

This is where you hand the feature over to the people who will actually use it.

**Step 10: Create User Scenarios**
Provide your academic coordinators with a list of tasks to perform, without telling them exactly how to do it.
*   "Generate a draft schedule for the Engineering department's 1st-year students."
*   "Prof. Smith just informed you she can no longer teach on Fridays. Update her availability and see how it affects the draft schedule."
*   "The enrollment for PHY200 just increased to 160. Find a room that can accommodate the class."

**Step 11: Observe and Collect Feedback**
*   Watch them use the tool. Where do they struggle? Is the conflict report clear to them?
*   Ask for qualitative feedback. Does the generated schedule "feel" right? Are the soft constraint priorities aligned with their real-world needs? Use this feedback to tune the scoring weights in your algorithm.

---

### **Phase 5: Performance Testing**

**Step 12: Test the Scheduler Under Load**
*   Create a test dataset that mirrors your production scale (e.g., 1000 courses, 200 teachers, 100 rooms for a large university).
*   Use a load testing tool (k6, JMeter) to hammer the `POST /scheduler/preview` endpoint.
*   **Measure:**
    *   **Response Time:** How long does it take to generate a proposal? It should be within an acceptable threshold for a user (e.g., under 30-60 seconds).
    *   **Server Resources:** Monitor CPU and memory usage during the run to ensure it doesn't crash the server. If performance is poor, investigate optimizing database queries or the algorithm itself.
