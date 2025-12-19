import pandas as pd
import numpy as np
import logging
import json
import ast
import os
from datetime import datetime
from collections import defaultdict

# --- CONFIGURATION ---
LOG_FILE = 'data/timetabling.log'
OUTPUT_CSV = 'Output/final_schedule.csv'
LOCKS_FILE = 'data/manual_locks.json'

# Filenames
FILE_CLASSES = 'data/final_schedular_correct.csv'
FILE_ROOMS = 'data/classrooms.csv'
FILE_LABS = 'data/lab_backend.csv'

# Time Configuration
LUNCH_HOUR = 13
MAX_BLOCK_SIZE = 4
DEFAULT_CAPACITY = 15

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class UMA_Scheduler_Engine:
    def __init__(self):
        self.df_classes = None
        self.df_rooms = None
        self.df_labs = None
        self.lab_preferences = {}
        self.manual_locks = {}

        # Global State Maps
        self.state_rooms = defaultdict(list)
        self.state_teachers = defaultdict(list)
        self.state_students = defaultdict(list)
        
        # Load Balancer
        self.teacher_hours = defaultdict(int) 
        self.teacher_id_to_name = {} 

        self.schedule_results = []
        self.conflict_stats = {
            "labs_moved_to_virtual": 0,
            "theory_moved_to_virtual": 0,
            "fully_unscheduled": 0,
        }

        self.standard_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        self.day_rotation_index = 0

    def get_rotated_days(self):
        rotated = self.standard_days[self.day_rotation_index:] + self.standard_days[:self.day_rotation_index]
        self.day_rotation_index = (self.day_rotation_index + 1) % 6
        return rotated

    def load_data(self):
        logger.info("Loading data files...")
        try:
            self.df_classes = pd.read_csv(FILE_CLASSES)
            self.df_rooms = pd.read_csv(FILE_ROOMS)
            self.df_labs = pd.read_csv(FILE_LABS)

            self.df_rooms['Capacity'] = pd.to_numeric(
                self.df_rooms['Capacity'], errors='coerce'
            ).fillna(0)

            for _, row in self.df_labs.iterrows():
                try:
                    raw_courses = row['c_codcur']
                    if isinstance(raw_courses, str) and raw_courses.startswith('['):
                        courses = ast.literal_eval(raw_courses)
                    else:
                        courses = [str(raw_courses)]
                    room_id = row['c_codaula']
                    for c in courses:
                        self.lab_preferences[str(c).strip()] = room_id
                except Exception:
                    pass

            if os.path.exists(LOCKS_FILE):
                try:
                    with open(LOCKS_FILE, 'r') as f:
                        self.manual_locks = json.load(f)
                    logger.info(f"Loaded {len(self.manual_locks)} manual locks.")
                except Exception as e:
                    logger.warning(f"Could not load locks file: {e}")

        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise

    def preprocess(self):
        logger.info("Preprocessing data...")
        
        # Handle Date Parsing with generic coerce
        self.df_classes['dt_start'] = pd.to_datetime(self.df_classes['start_period'], errors='coerce')
        self.df_classes['dt_end'] = pd.to_datetime(self.df_classes['end_period'], errors='coerce')

        # Fallback for missing dates
        if self.df_classes['dt_start'].isna().any():
            self.df_classes['dt_start'].fillna(datetime(2025, 1, 1), inplace=True)
            self.df_classes['dt_end'].fillna(datetime(2025, 12, 31), inplace=True)

        self.df_classes['phys_load_theory'] = self.df_classes['total_physical_hrs_theory'].fillna(0).astype(int)
        self.df_classes['phys_load_lab'] = self.df_classes['total_physical_hrs_lab'].fillna(0).astype(int)
        self.df_classes['virt_load'] = self.df_classes['total_virtual_hrs'].fillna(0).astype(int)
        
        # --- FIX: Robust check for division_size ---
        if 'division_size' not in self.df_classes.columns:
            self.df_classes['division_size'] = DEFAULT_CAPACITY
        else:
            self.df_classes['division_size'] = pd.to_numeric(
                self.df_classes['division_size'], errors='coerce'
            ).fillna(DEFAULT_CAPACITY).astype(int)

        def clean_list_col(val):
            if pd.isna(val): return []
            val = str(val).strip()
            if val.startswith('[') and val.endswith(']'):
                try: return [str(x).strip() for x in ast.literal_eval(val)]
                except: return [val]
            return [val]

        self.df_classes['teacher_ids_clean'] = self.df_classes['c_dnidoc'].apply(clean_list_col)
        self.df_classes['teacher_names_clean'] = self.df_classes['docente'].apply(clean_list_col)

        # Build ID -> Name map
        for _, row in self.df_classes.iterrows():
            ids = row['teacher_ids_clean']
            names = row['teacher_names_clean']
            if len(ids) == len(names):
                for i, tid in enumerate(ids):
                    self.teacher_id_to_name[tid] = names[i]

    def _dates_overlap(self, start_a, end_a, booking_list):
        for start_b, end_b in booking_list:
            if max(start_a, start_b) < min(end_a, end_b): return True
        return False

    def check_non_teacher_conflict(self, task, room_id, day, hour_block, check_room=True):
        start_dt, end_dt = task['dt_start'], task['dt_end']
        student_key = (task['n_codper'], task['c_codesp'], task['n_ciclo'], task['division'])

        for h in hour_block:
            if h == LUNCH_HOUR: return True
            if task['turno'] == 'Diurno' and not (6 <= h < 18): return True
            if task['turno'] == 'Nocturno' and not (18 <= h < 22): return True

            if check_room and room_id != "VIRTUAL":
                if self._dates_overlap(start_dt, end_dt, self.state_rooms.get((room_id, day, h), [])):
                    return True

            if self._dates_overlap(start_dt, end_dt, self.state_students.get((student_key, day, h), [])):
                return True
                
        return False

    def select_best_teacher(self, task, day, hour_block):
        candidates = task.get('teacher_ids_clean', [])
        if not candidates:
            return "No Teacher Assigned"
            
        # Sort candidates: Primary sort key is current workload (asc), Secondary is ID
        candidates.sort(key=lambda tid: (self.teacher_hours[tid], tid))
        
        start_dt, end_dt = task['dt_start'], task['dt_end']
        
        for tid in candidates:
            is_busy = False
            for h in hour_block:
                if self._dates_overlap(start_dt, end_dt, self.state_teachers.get((tid, day, h), [])):
                    is_busy = True
                    break
            
            if not is_busy:
                return tid 
                
        return None

    def record_session(self, task, room_id, day, start_h, end_h, assigned_teacher_id, activity_override=None):
        adm_entry = str(task['n_codper'])
        if len(adm_entry) == 5: adm_entry = f"{adm_entry[:4]}-{adm_entry[4]}"
        act_type = activity_override if activity_override else task.get('activity_type', 'theory')

        s_time = f"{start_h:02d}:00" if start_h != "00:00" else "00:00"
        e_time = f"{end_h:02d}:00" if start_h != "00:00" else "00:00"

        t_name = self.teacher_id_to_name.get(assigned_teacher_id, assigned_teacher_id)

        record = {
            "n_codper": task['n_codper'],
            "admission_entry": adm_entry,
            "start_period": task['start_period'],
            "end_period": task['end_period'],
            "c_codesp": task['c_codesp'],
            "nomesp": task['nomesp'],
            "n_ciclo": task['n_ciclo'],
            "division": task['division'],
            "c_codcur": task['c_codcur'],
            "c_nomcur": task['c_nomcur'],
            "activity_type": act_type,
            "turno": task['turno'],
            "day_of_week": day,
            "start_time": s_time,
            "end_time": e_time,
            "room_id": room_id,
            "division_size": task['division_size'],
            "teacher_ids": str(assigned_teacher_id),
            "teacher_names": str(t_name),
        }
        self.schedule_results.append(record)

    def commit_booking(self, task, room_id, day, hour_block, specific_teacher_id=None):
        start_dt, end_dt = task['dt_start'], task['dt_end']
        student_key = (task['n_codper'], task['c_codesp'], task['n_ciclo'], task['division'])
        
        active_tid = specific_teacher_id
        if not active_tid:
             active_tid = task.get('teacher_ids_clean', ['TBA'])[0] if task.get('teacher_ids_clean') else 'TBA'

        duration = len(hour_block)

        for h in hour_block:
            date_range = (start_dt, end_dt)
            if room_id != "VIRTUAL" and not room_id.startswith("VIRTUAL"):
                self.state_rooms[(room_id, day, h)].append(date_range)
            self.state_students[(student_key, day, h)].append(date_range)
            
            if active_tid != "No Teacher Assigned" and active_tid != 'TBA':
                self.state_teachers[(active_tid, day, h)].append(date_range)
        
        if active_tid != "No Teacher Assigned" and active_tid != 'TBA':
            self.teacher_hours[active_tid] += duration

        self.record_session(task, room_id, day, hour_block[0], hour_block[-1] + 1, active_tid)

    # --- LOCKS ---
    def apply_locks(self, tasks):
        if not self.manual_locks: return tasks
        logger.info("PHASE 0: Applying Manual Locks...")
        
        for task in tasks:
            lab_key = f"{task['n_codper']}|{task['c_codcur']}|{task['division']}|lab"
            if lab_key in self.manual_locks and task['phys_load_lab'] > 0:
                self._process_lock(task, self.manual_locks[lab_key], 'lab', task['phys_load_lab'])
                task['phys_load_lab'] = 0 
                
            theory_key = f"{task['n_codper']}|{task['c_codcur']}|{task['division']}|theory"
            if theory_key in self.manual_locks and task['phys_load_theory'] > 0:
                self._process_lock(task, self.manual_locks[theory_key], 'theory', task['phys_load_theory'])
                task['phys_load_theory'] = 0 
        return tasks

    def _process_lock(self, task, lock_data, act_type, load_hours):
        try:
            day = lock_data.get('day_of_week')
            start_str = lock_data.get('start_time', '00:00')
            room_id = lock_data.get('room_id', 'Unassigned')
            if start_str == "00:00": return

            start_h = int(start_str.split(':')[0])
            duration = min(load_hours, MAX_BLOCK_SIZE) if load_hours > 0 else 2
            block = list(range(start_h, start_h + duration))
            
            task['activity_type'] = act_type
            
            # Select teacher for the lock as well
            tid = self.select_best_teacher(task, day, block)
            if not tid: tid = task['teacher_ids_clean'][0] if task['teacher_ids_clean'] else "Manual Lock"
                
            self.commit_booking(task, room_id, day, block, tid)
            logger.info(f"Locked {act_type}: {task['c_codcur']} -> {day} {start_str}")
        except Exception as e:
            logger.error(f"Error applying lock: {e}")

    # --- SCHEDULING LOGIC ---
    def get_candidate_rooms(self, task, is_lab):
        req_capacity = task['division_size']
        candidates = self.df_rooms[self.df_rooms['Capacity'] >= req_capacity].copy()
        if is_lab:
            course_code = str(task['c_codcur']).strip()
            if course_code in self.lab_preferences:
                preferred = self.lab_preferences[course_code]
                specific = candidates[candidates['New_ID'] == preferred]
                if not specific.empty:
                    other = candidates[candidates['New_ID'] != preferred]
                    other_labs = other[other['New_ID'].str.contains('LB|Lab', case=False)]
                    return pd.concat([specific, other_labs])
            filtered = candidates[candidates['New_ID'].str.contains('LB|Lab|SP', case=False)]
        else:
            filtered = candidates[candidates['New_ID'].str.contains('CL|AU|MR', case=False)]
        return filtered.sort_values(by='Capacity')

    def schedule_virtual_hours(self, task, hours_needed, reason_label="VIRTUAL - ONLINE"):
        days = self.get_rotated_days()
        hours_remaining = hours_needed
        for day in days:
            if hours_remaining == 0: break
            start_range = range(6, 18) if task['turno'] == 'Diurno' else range(18, 22)
            for start_h in start_range:
                if hours_remaining == 0: break
                if start_h == LUNCH_HOUR: continue
                max_possible = 0
                for i in range(min(hours_remaining, MAX_BLOCK_SIZE)):
                    h_check = start_h + i
                    if h_check == LUNCH_HOUR or (task['turno']=='Diurno' and h_check>=18) or (task['turno']=='Nocturno' and h_check>=22): break
                    max_possible += 1
                if max_possible == 0: continue
                for k in range(max_possible, 0, -1):
                    block = list(range(start_h, start_h + k))
                    
                    if self.check_non_teacher_conflict(task, "VIRTUAL", day, block, check_room=False):
                        continue

                    tid = self.select_best_teacher(task, day, block)
                    if tid:
                        self.commit_booking(task, reason_label, day, block, tid)
                        hours_remaining -= k
                        break
        if hours_remaining > 0:
            self.conflict_stats["fully_unscheduled"] += 1
            tid = task['teacher_ids_clean'][0] if task['teacher_ids_clean'] else "TBA"
            self.record_session(task, f"UNSCHEDULED ({hours_remaining}h)", "Unassigned", "00:00", "00:00", tid, "virtual")

    def schedule_task_hours(self, task, hours_needed, is_lab):
        candidates = self.get_candidate_rooms(task, is_lab)
        if candidates.empty:
            if is_lab: self.conflict_stats["labs_moved_to_virtual"] += 1
            else: self.conflict_stats["theory_moved_to_virtual"] += 1
            self.schedule_virtual_hours(task, hours_needed, reason_label="VIRTUAL - CAPACITY")
            return

        days = self.get_rotated_days()
        hours_remaining = hours_needed
        
        for _, room in candidates.iterrows():
            room_id = room['New_ID']
            if hours_remaining == 0: break
            for day in days:
                if hours_remaining == 0: break
                start_range = range(6, 18) if task['turno'] == 'Diurno' else range(18, 22)
                for start_h in start_range:
                    if hours_remaining == 0: break
                    if start_h == LUNCH_HOUR: continue
                    max_possible = 0
                    for i in range(min(hours_remaining, MAX_BLOCK_SIZE)):
                        h_check = start_h + i
                        if h_check == LUNCH_HOUR or (task['turno']=='Diurno' and h_check>=18) or (task['turno']=='Nocturno' and h_check>=22): break
                        max_possible += 1
                    if max_possible == 0: continue
                    for k in range(max_possible, 0, -1):
                        block = list(range(start_h, start_h + k))
                        
                        if self.check_non_teacher_conflict(task, room_id, day, block, check_room=True):
                            continue

                        tid = self.select_best_teacher(task, day, block)
                        if tid:
                            self.commit_booking(task, room_id, day, block, tid)
                            hours_remaining -= k
                            break

        if hours_remaining > 0:
            if is_lab: self.conflict_stats["labs_moved_to_virtual"] += 1
            else: self.conflict_stats["theory_moved_to_virtual"] += 1
            self.schedule_virtual_hours(task, hours_remaining, reason_label="VIRTUAL - CONFLICT")

    def run(self):
        self.load_data()
        self.preprocess()

        tasks = self.df_classes.to_dict('records')
        tasks.sort(key=lambda x: (-x['phys_load_lab'], x['dt_start']))

        tasks = self.apply_locks(tasks)

        logger.info("PHASE 1: Scheduling Labs...")
        for task in tasks:
            if task['phys_load_lab'] > 0:
                task['activity_type'] = 'lab'
                self.schedule_task_hours(task, task['phys_load_lab'], is_lab=True)

        logger.info("PHASE 2: Scheduling Theory...")
        for task in tasks:
            if task['phys_load_theory'] > 0:
                task['activity_type'] = 'theory'
                self.schedule_task_hours(task, task['phys_load_theory'], is_lab=False)

        logger.info("PHASE 3: Scheduling Pure Virtuals...")
        for task in tasks:
            if task['virt_load'] > 0:
                task['activity_type'] = 'virtual'
                self.schedule_virtual_hours(task, task['virt_load'], reason_label="VIRTUAL - ONLINE")

        self.save_results()

    def save_results(self):
        logger.info(f"Saving results... {len(self.schedule_results)} sessions created.")
        if self.schedule_results:
            df_out = pd.DataFrame(self.schedule_results)
            df_out.sort_values(by=['n_codper', 'c_codesp', 'division', 'day_of_week', 'start_time'], inplace=True)
            df_out.insert(0, 'session_id', range(1, 1 + len(df_out)))
            df_out.to_csv(OUTPUT_CSV, index=False)
            logger.info(f"Schedule saved to {OUTPUT_CSV}")
        else:
            logger.warning("No schedule results generated.")

if __name__ == "__main__":
    engine = UMA_Scheduler_Engine()
    engine.run()




    # /Users/jarvis/Downloads/flask-app 2/flask-app/app.py