db_horrario

### 1. `curso`

| Column         | Type         | Meaning                                                                  |
| -------------- | ------------ | ------------------------------------------------------------------------ |
| id             | int, PK, AI  | Internal ID (row identifier)                                             |
| n\_codper      | varchar(191) | Academic period/year (e.g., 2025)                                        |
| c\_codmod      | int          | Modality code (1 = presencial, 2 = semi, 3 = virtual, etc.)              |
| c\_codfac      | varchar(191) | Faculty code (e.g., S = Ciencias de la Salud, E = Ingeniería y Negocios) |
| nom\_fac       | varchar(191) | Faculty name (full)                                                      |
| c\_codesp      | varchar(191) | Program/specialty code (e.g., S1 = Enfermería, E6 = IA)                  |
| nomesp         | varchar(191) | Program/specialty name (e.g., Ingeniería de Inteligencia Artificial)     |
| c\_codcur      | varchar(191) | Course code (structured: prefix + cycle + unique ID)                     |
| c\_nomcur      | varchar(191) | Course name (subject title)                                              |
| n\_ciclo       | int          | Cycle/semester number (e.g., 3 = third semester)                         |
| c\_area        | varchar(191) | Course area code (EC, EF, FG, PP)                                        |
| n\_codper\_equ | varchar(191) | Equivalent academic period (if mapped)                                   |
| c\_codmod\_equ | int          | Equivalent modality (if mapped)                                          |
| c\_codfac\_equ | varchar(191) | Equivalent faculty (if mapped)                                           |
| c\_codesp\_equ | varchar(191) | Equivalent specialty (if mapped)                                         |
| c\_codcur\_equ | varchar(191) | Equivalent course code                                                   |
| c\_nomcur\_equ | varchar(191) | Equivalent course name                                                   |
| turno\_id      | int          | Shift/turn (morning, afternoon, night)                                   |
| c\_alu         | int          | Number of students (optional tracking)                                   |

---

### 2. `docente`

| Column       | Type         | Meaning                                                    |
| ------------ | ------------ | ---------------------------------------------------------- |
| id           | int, PK, AI  | Teacher ID                                                 |
| c\_codfac    | varchar(191) | Faculty code (S, E, etc.)                                  |
| nom\_fac     | varchar(191) | Faculty name                                               |
| c\_nomdoc    | varchar(191) | Teacher’s full name                                        |
| h\_min       | int          | Minimum weekly hours required                              |
| h\_max       | int          | Maximum weekly hours allowed                               |
| tipo         | int          | Contract type (0 = ordinario, 1 = contratado, 2 = parcial) |
| h\_total     | double       | Total assigned hours                                       |
| c\_dnidoc    | char(8)      | DNI (national ID)                                          |
| h\_rectorado | int          | Hours for rectorado/admin duties                           |
| v1           | int          | Custom field                                               |
| v2           | int          | Custom field                                               |
| id\_funcion  | int          | Teacher’s function/role (1 = docente, 2 = coordinador…)    |

---

### 3. `horario`

| Column      | Type         | Meaning                                       |
| ----------- | ------------ | --------------------------------------------- |
| id          | int, PK, AI  | Schedule ID                                   |
| dia         | varchar(191) | Day of the week                               |
| h\_inicio   | datetime(3)  | Start time                                    |
| h\_fin      | datetime(3)  | End time                                      |
| n\_horas    | double       | Total hours                                   |
| c\_color    | varchar(191) | Color code for UI/timetable                   |
| tipo        | varchar(191) | Schedule type (lecture, lab, etc.)            |
| h\_umaPlus  | double       | Hours synced with UMA+ system                 |
| aula\_id    | int          | Linked classroom ID                           |
| docente\_id | int          | Linked teacher ID (FK to `docente.id`)        |
| curso\_id   | int          | Linked course ID (FK to `curso.id`)           |
| turno\_id   | int          | Shift (morning, afternoon, night)             |
| modalidad   | varchar(191) | Teaching modality (presencial, virtual, etc.) |

---

## 📚 Lookup Tables (Reference)

### 4. `curso_areas`

| Column            | Type         | Meaning                                           |
| ----------------- | ------------ | ------------------------------------------------- |
| c\_cod\_cur\_area | varchar(10)  | Area code (EC, EF, FG, PP)                        |
| c\_nom\_cur\_area | varchar(191) | Area name (Especialidad, Específica, General, PP) |
| d\_borrado        | int/null     | Deleted flag (NULL = active)                      |

---

### 5. `funcion_docente`

*(not fully shown in your dump, but implied by `docente.id_funcion`)*

| Column      | Type         | Meaning                                    |
| ----------- | ------------ | ------------------------------------------ |
| id          | int, PK, AI  | Function ID                                |
| nombre      | varchar(191) | Function name (Docente, Coordinador, etc.) |
| descripcion | text         | Description of the academic role           |

---

### 6. `aula`

| Column    | Type         | Meaning                         |
| --------- | ------------ | ------------------------------- |
| id        | int, PK, AI  | Classroom ID                    |
| nombre    | varchar(191) | Classroom name/number           |
| pabellon  | varchar(191) | Building block (Pabellón A, B…) |
| capacidad | int          | Capacity (number of students)   |

---

✅ This is the **core schema** that makes your scheduling + curriculum system work:

* `curso` = what course is offered
* `docente` = who teaches
* `horario` = when and where
* `aula` = in which classroom/pavilion
* `curso_areas` & `funcion_docente` = lookup tables for classification


jaguar_db_sigu

📚 Important Columns in tb_especialidad

| Column                 | Why it matters                                                      |
| ---------------------- | ------------------------------------------------------------------- |
| **codfac**             | Faculty code → links to `tb_facultad`.                              |
| **codesp**             | Program/specialty code (unique within faculty).                     |
| **nomesp**             | Full specialty name (e.g., *Enfermería*, *Ingeniería de IA*).       |
| **estado**             | Status (1 = active, 0 = inactive).                                  |
| **c\_abrevesp**        | Abbreviation (short program code, useful in schedules and reports). |
| **codsun**             | Official SUNEDU code (gov’t accreditation).                         |
| **c\_email\_coord**    | Program coordinator email (main contact point).                     |
| **c\_den\_grad\_bach** | Denomination of the Bachelor’s degree granted.                      |
| **c\_den\_grad\_tit**  | Denomination of the Professional Title granted.                     |

📚 Extracted Explanation from tb_plan_estudio_curso

| Column        | Value              | Meaning                                                                     |
| ------------- | ------------------ | --------------------------------------------------------------------------- |
| **n\_codper** | 2025               | Academic plan year.                                                         |
| **c\_codmod** | 2                  | Modality (2 = Presencial/Semipresencial depending on config).               |
| **c\_codfac** | S                  | Faculty: Ciencias de la Salud.                                              |
| **c\_codesp** | S2, S1, S3, S4, E4 | Program codes under different faculties (e.g., Farmacia, Enfermería, etc.). |
| **c\_codcur** | SESG3031           | Course code.                                                                |
| **c\_nomcur** | INGLÉS I           | Course name.                                                                |
| **n\_ciclo**  | 3                  | Semester cycle = 3rd semester.                                              |
| **c\_ciclo**  | III                | Roman numeral version of cycle.                                             |
| **n\_ht**     | 3                  | Weekly theory hours.                                                        |
| **n\_hp**     | 0                  | Weekly practice/lab hours.                                                  |
| **n\_cr**     | —                  | Credits (not filled, usually `n_ht + n_hp`).                                |
| **c\_tipcur** | —                  | Course type (empty here).                                                   |
| **c\_area**   | FG                 | Área: *Formación General* (general education).                              |
| **n\_estado** | 3                  | Status of the course in the plan (3 = active/approved).                     |

