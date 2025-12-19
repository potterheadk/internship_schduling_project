"""
analyze_schedule.py

Analysis script for UMA_Scheduler_Engine output.

- Reads:  Output/final_schedule.csv
- Optionally: data/classrooms.csv (if present) for room capacity info.
- Prints summary stats to console.
- Writes detailed conflict reports to Output/:
    - teacher_conflicts.csv
    - student_conflicts.csv
    - room_conflicts.csv
    - suspicious_sessions.csv
"""

import os
from collections import defaultdict, Counter

import numpy as np
import pandas as pd

# --- CONFIGURATION ---
OUTPUT_SCHEDULE = 'Output/final_schedule.csv'
ROOMS_CSV = 'data/classrooms.csv'   # optional; used if exists
EXPECTED_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


def to_hour(time_str):
    """Parse 'HH:MM' into integer hour; returns np.nan if invalid."""
    try:
        s = str(time_str)
        if ':' not in s:
            return np.nan
        h = int(s.split(':')[0])
        return h
    except Exception:
        return np.nan


def is_virtual_room(room_id):
    s = str(room_id)
    if s.startswith('VIRTUAL'):
        return True
    if 'UNSCHEDULED' in s or 'Unassigned' in s:
        return True
    return False


def is_real_teacher(tid):
    s = str(tid)
    return s not in {'No Teacher Assigned', 'TBA', 'Manual Lock', 'nan', ''}


def is_valid_day(day):
    return str(day) in EXPECTED_DAYS


def ensure_output_dir(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def load_schedule():
    if not os.path.exists(OUTPUT_SCHEDULE):
        raise FileNotFoundError(f"Schedule file not found: {OUTPUT_SCHEDULE}")

    df = pd.read_csv(OUTPUT_SCHEDULE)

    # Ensure session_id exists
    if 'session_id' not in df.columns:
        df.insert(0, 'session_id', range(1, 1 + len(df)))

    # Parse academic period dates to match engine logic
    df['dt_start'] = pd.to_datetime(df['start_period'], errors='coerce')
    df['dt_end'] = pd.to_datetime(df['end_period'], errors='coerce')

    # Basic time parsing
    df['start_hour'] = df['start_time'].apply(to_hour)
    df['end_hour'] = df['end_time'].apply(to_hour)
    df['duration_hours'] = df['end_hour'] - df['start_hour']

    # Useful flags
    df['is_virtual'] = df['room_id'].apply(is_virtual_room)
    df['is_valid_duration'] = df['duration_hours'] > 0
    df['is_valid_day'] = df['day_of_week'].apply(is_valid_day)

    # Teacher ID normalization (string)
    df['teacher_ids'] = df['teacher_ids'].astype(str).fillna('')
    df['is_real_teacher'] = df['teacher_ids'].apply(is_real_teacher)

    return df


def load_rooms():
    if not os.path.exists(ROOMS_CSV):
        return None
    try:
        df_rooms = pd.read_csv(ROOMS_CSV)
        return df_rooms
    except Exception:
        return None


def summarize_basic(df):
    print("\n=== BASIC SUMMARY ===")
    print(f"Total sessions: {len(df)}")
    print(f"Unique student groups: {df[['n_codper', 'c_codesp', 'n_ciclo', 'division']].drop_duplicates().shape[0]}")
    print(f"Unique courses: {df['c_codcur'].nunique()}")

    # Activity type summary
    if 'activity_type' in df.columns:
        print("\nSessions by activity_type:")
        print(df['activity_type'].value_counts(dropna=False))

        hours_by_type = df[df['is_valid_duration']].groupby('activity_type')['duration_hours'].sum().sort_values(ascending=False)
        print("\nTotal hours by activity_type:")
        print(hours_by_type)

    # Virtual vs physical
    print("\nSessions by virtual/physical:")
    print(df['is_virtual'].value_counts())

    hours_virtual = df[df['is_valid_duration']].groupby('is_virtual')['duration_hours'].sum()
    print("\nTotal hours by virtual/physical:")
    print(hours_virtual)

    # Turno summary
    if 'turno' in df.columns:
        print("\nSessions by turno:")
        print(df['turno'].value_counts(dropna=False))

        hours_by_turno = df[df['is_valid_duration']].groupby('turno')['duration_hours'].sum().sort_values(ascending=False)
        print("\nTotal hours by turno:")
        print(hours_by_turno)

    # Day-of-week summary
    print("\nSessions by day_of_week:")
    print(df['day_of_week'].value_counts(dropna=False))

    hours_by_day = df[df['is_valid_duration']].groupby('day_of_week')['duration_hours'].sum().sort_values(ascending=False)
    print("\nTotal hours by day_of_week:")
    print(hours_by_day)


def analyze_teachers(df):
    print("\n=== TEACHER LOAD ANALYSIS ===")
    df_teach = df[df['is_real_teacher'] & df['is_valid_duration']].copy()

    if df_teach.empty:
        print("No sessions with real teachers found.")
        return

    teacher_hours = df_teach.groupby('teacher_ids')['duration_hours'].sum().sort_values(ascending=False)
    print("\nTop 10 teachers by assigned hours (across entire academic period):")
    print(teacher_hours.head(10))

    # Basic stats
    print("\nTeacher hours stats (summing all weeks where the slot is active):")
    print(f"  Teachers counted: {teacher_hours.index.nunique()}")
    print(f"  Min hours: {teacher_hours.min():.2f}")
    print(f"  Median hours: {teacher_hours.median():.2f}")
    print(f"  Mean hours: {teacher_hours.mean():.2f}")
    print(f"  Max hours: {teacher_hours.max():.2f}")
    print(f"  Std dev: {teacher_hours.std():.2f}")

    # Teachers with zero name mapping
    if 'teacher_names' in df.columns:
        name_map = df_teach.groupby('teacher_ids')['teacher_names'].agg(lambda x: Counter(x).most_common(1)[0][0])
        missing_name_ids = [tid for tid, name in name_map.items() if str(name).strip() in {'', 'nan'}]
        if missing_name_ids:
            print("\nTeachers with missing/blank names (IDs):")
            print(missing_name_ids[:20])
        else:
            print("\nNo teachers with missing names detected.")

    # Entries with no teacher or dummy teacher
    dummy_mask = ~df['is_real_teacher']
    if dummy_mask.any():
        print(f"\nSessions with dummy or missing teacher (No Teacher Assigned / TBA / Manual Lock): {dummy_mask.sum()}")
    else:
        print("\nNo sessions with dummy/missing teacher IDs.")


def analyze_rooms(df, df_rooms=None):
    print("\n=== ROOM UTILIZATION ANALYSIS ===")
    df_phys = df[~df['is_virtual'] & df['is_valid_duration']].copy()
    if df_phys.empty:
        print("No physical room sessions found.")
        return

    room_hours = df_phys.groupby('room_id')['duration_hours'].sum().sort_values(ascending=False)
    print("\nTop 10 rooms by scheduled hours:")
    print(room_hours.head(10))

    if df_rooms is not None and 'New_ID' in df_rooms.columns and 'Capacity' in df_rooms.columns:
        # Join by New_ID -> room_id
        df_roomcap = df_rooms[['New_ID', 'Capacity']].rename(columns={'New_ID': 'room_id'})
        merged = room_hours.reset_index().merge(df_roomcap, on='room_id', how='left')
        print("\nTop 10 rooms with capacity info:")
        print(merged.head(10))

        print("\nRooms with highest hours per capacity unit (top 10):")
        merged['hours_per_seat'] = merged['duration_hours'] / merged['Capacity'].replace(0, np.nan)
        print(merged.sort_values('hours_per_seat', ascending=False).head(10))
    else:
        print("Room capacity file not provided or missing expected columns; skipping capacity analysis.")


# ---------- Conflict detection aligned with dt_start/dt_end ----------

def build_hour_slots(df):
    """
    Expand each session into hour slots for conflict detection.

    Returns:
        teacher_slots: dict[(teacher_id, day, hour)] -> [(session_id, dt_start, dt_end), ...]
        student_slots: dict[(stu_key, day, hour)] -> [(session_id, dt_start, dt_end), ...]
        room_slots:    dict[(room_id, day, hour)] -> [(session_id, dt_start, dt_end), ...]
    """
    teacher_slots = defaultdict(list)
    student_slots = defaultdict(list)
    room_slots = defaultdict(list)

    valid = df['is_valid_duration'] & df['is_valid_day']
    df_valid = df[valid].copy()

    for _, row in df_valid.iterrows():
        sid = row['session_id']
        day = row['day_of_week']
        sh = int(row['start_hour'])
        eh = int(row['end_hour'])  # exclusive
        teacher_id = str(row['teacher_ids'])
        room_id = row['room_id']
        stu_key = (row['n_codper'], row['c_codesp'], row['n_ciclo'], row['division'])
        dt_start = row['dt_start']
        dt_end = row['dt_end']

        hours = range(sh, eh)
        for h in hours:
            # Teacher
            if is_real_teacher(teacher_id):
                teacher_slots[(teacher_id, day, h)].append((sid, dt_start, dt_end))

            # Student
            student_slots[(stu_key, day, h)].append((sid, dt_start, dt_end))

            # Room (only physical)
            if not is_virtual_room(room_id):
                room_slots[(room_id, day, h)].append((sid, dt_start, dt_end))

    return teacher_slots, student_slots, room_slots


def sessions_with_overlaps(slot_dict):
    """
    For each slot (e.g. teacher+day+hour), check all sessions in that slot and
    flag sessions that have overlapping dt_start/dt_end.

    Mirrors the engine's logic: max(start_a, start_b) < min(end_a, end_b)
    """
    conflict_sessions = set()

    for _, sess_list in slot_dict.items():
        if len(sess_list) <= 1:
            continue

        # sort by dt_start for early pruning
        sess_list_sorted = sorted(sess_list, key=lambda x: x[1])  # (sid, dt_start, dt_end)
        n = len(sess_list_sorted)
        for i in range(n):
            sid_i, s_i, e_i = sess_list_sorted[i]
            if pd.isna(s_i) or pd.isna(e_i):
                continue
            for j in range(i + 1, n):
                sid_j, s_j, e_j = sess_list_sorted[j]
                if pd.isna(s_j) or pd.isna(e_j):
                    continue
                # if the later session starts after the earlier ends, no more overlaps in this sorted list
                if s_j >= e_i:
                    break
                # overlap check
                if max(s_i, s_j) < min(e_i, e_j):
                    conflict_sessions.add(sid_i)
                    conflict_sessions.add(sid_j)

    return conflict_sessions


def detect_conflicts(df):
    print("\n=== CONFLICT DETECTION (with dt_start/dt_end) ===")
    teacher_slots, student_slots, room_slots = build_hour_slots(df)

    teacher_conf_sids = sessions_with_overlaps(teacher_slots)
    student_conf_sids = sessions_with_overlaps(student_slots)
    room_conf_sids = sessions_with_overlaps(room_slots)

    print(f"\nTeacher-conflicted sessions: {len(teacher_conf_sids)}")
    print(f"Student-conflicted sessions: {len(student_conf_sids)}")
    print(f"Room-conflicted sessions:    {len(room_conf_sids)}")

    ensure_output_dir('Output/teacher_conflicts.csv')

    if teacher_conf_sids:
        df_teacher_conf = df[df['session_id'].isin(teacher_conf_sids)].copy()
        df_teacher_conf.to_csv('Output/teacher_conflicts.csv', index=False)
        print("  -> Detailed teacher conflicts written to Output/teacher_conflicts.csv")

    if student_conf_sids:
        df_student_conf = df[df['session_id'].isin(student_conf_sids)].copy()
        df_student_conf.to_csv('Output/student_conflicts.csv', index=False)
        print("  -> Detailed student conflicts written to Output/student_conflicts.csv")

    if room_conf_sids:
        df_room_conf = df[df['session_id'].isin(room_conf_sids)].copy()
        df_room_conf.to_csv('Output/room_conflicts.csv', index=False)
        print("  -> Detailed room conflicts written to Output/room_conflicts.csv")

    if teacher_conf_sids or student_conf_sids or room_conf_sids:
        print("\nSome real conflicts (overlapping in time and date) were detected. Inspect Output/*.csv.")
    else:
        print("\nNo teacher/room/student conflicts detected when considering dt_start/dt_end.")


# ---------- Suspicious data & daily load ----------

def detect_suspicious(df):
    print("\n=== DATA INTEGRITY & SUSPICIOUS CASES ===")

    # 1) Invalid durations
    invalid_duration = df[~df['is_valid_duration']]
    print(f"\nSessions with zero or negative duration: {len(invalid_duration)}")
    if len(invalid_duration) > 0:
        print("  (This usually includes UNSCHEDULED / 00:00-00:00 entries.)")

    # 2) Days not in EXPECTED_DAYS
    bad_day = df[~df['is_valid_day']]
    print(f"Sessions with unexpected day_of_week values: {len(bad_day)}")
    if len(bad_day) > 0:
        print("  Unique unexpected days:", bad_day['day_of_week'].unique())

    # 3) Sessions in virtual rooms but marked as activity_type 'lab'/'theory'
    if 'activity_type' in df.columns:
        virtual_mismatch = df[df['is_virtual'] & df['activity_type'].isin(['lab', 'theory'])]
        print(f"\nSessions where activity_type is 'lab'/'theory' but room is virtual: {len(virtual_mismatch)}")

    # 4) Sessions with missing key identifiers
    missing_keys = df[
        df['n_codper'].isna()
        | df['c_codesp'].isna()
        | df['n_ciclo'].isna()
        | df['division'].isna()
        | df['c_codcur'].isna()
    ]
    print(f"\nSessions with missing key student/course identifiers: {len(missing_keys)}")

    # Export suspicious sessions to CSV for manual inspection
    suspicious = pd.concat(
        [
            invalid_duration,
            bad_day,
            missing_keys
        ]
    ).drop_duplicates(subset=['session_id'])

    ensure_output_dir('Output/suspicious_sessions.csv')
    suspicious.to_csv('Output/suspicious_sessions.csv', index=False)
    print("\nSuspicious sessions written to Output/suspicious_sessions.csv")


def analyze_daily_load_per_teacher(df):
    print("\n=== DAILY LOAD PER TEACHER (AGGREGATED ACROSS PERIOD) ===")

    df_teach = df[df['is_real_teacher'] & df['is_valid_duration']].copy()
    if df_teach.empty:
        print("No valid teacher sessions to analyze.")
        return

    daily = (
        df_teach.groupby(['teacher_ids', 'day_of_week'])['duration_hours']
        .sum()
        .reset_index()
    )

    # NOTE: These values are total hours across the entire academic period
    # for a given weekday, not simultaneous hours in a single calendar date.
    heavy_days = daily[daily['duration_hours'] > 8].sort_values('duration_hours', ascending=False)

    if heavy_days.empty:
        print("No teacher found with more than 8 aggregated hours on a single weekday.")
    else:
        print("Teachers with > 8 aggregated hours on a weekday (top 20 rows):")
        print(heavy_days.head(20))


def main():
    print(f"Reading schedule from: {OUTPUT_SCHEDULE}")
    df = load_schedule()
    df_rooms = load_rooms()

    summarize_basic(df)
    analyze_teachers(df)
    analyze_rooms(df, df_rooms)
    detect_conflicts(df)
    detect_suspicious(df)
    analyze_daily_load_per_teacher(df)

    print("\n=== ANALYSIS COMPLETE ===")
    print("Check the 'Output' folder for detailed conflict and suspicious-session reports.")


if __name__ == "__main__":
    main()
