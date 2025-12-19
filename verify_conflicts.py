"""
verify_conflicts.py - Independent Conflict Verification Tool

This script independently analyzes the schedule to verify the conflict counts
reported by the chatbot's intelligent conflict analysis.

It uses a different methodology to double-check results.
"""

import pandas as pd
import os
from collections import defaultdict
from datetime import datetime, time

def verify_conflicts():
    """Independently verify conflict counts using different methods."""
    
    schedule_file = 'output/final_assigned_schedule_v9_date_aware.csv'
    
    if not os.path.exists(schedule_file):
        print(f"❌ Schedule file not found: {schedule_file}")
        return
    
    print("📊 INDEPENDENT CONFLICT VERIFICATION")
    print("=" * 70)
    
    # Load data
    df = pd.read_csv(schedule_file, dtype=str).fillna('')
    print(f"✅ Loaded {len(df)} classes from schedule")
    print()
    
    # Detect columns
    day_col = 'dia'
    teacher_col = 'docente'
    room_col = 'c_codaula'
    time_start_col = 'h_ini'
    time_end_col = 'h_fin'
    course_col = 'c_nomcur'
    
    # ========================================================================
    # METHOD 1: Count Teacher Conflicts (Groupby)
    # ========================================================================
    print("🔍 METHOD 1: Teacher Conflict Detection (Groupby)")
    print("-" * 70)
    
    # Group by teacher, day, start time
    teacher_grouped = df.groupby([teacher_col, day_col, time_start_col])
    
    teacher_conflicts_count = 0
    teacher_conflict_instances = {}  # {teacher: count}
    problematic_time_slots = []
    
    for (teacher, day, time_slot), group in teacher_grouped:
        num_classes = len(group)
        
        # A conflict occurs when one teacher has >1 class at same time
        if num_classes > 1 and teacher and not pd.isna(teacher) and teacher.strip():
            teacher_conflicts_count += num_classes  # Count each conflicting class
            
            if teacher not in teacher_conflict_instances:
                teacher_conflict_instances[teacher] = 0
            teacher_conflict_instances[teacher] += num_classes
            
            problematic_time_slots.append({
                'teacher': teacher,
                'day': day,
                'time': time_slot,
                'classes': num_classes
            })
    
    print(f"✅ Teacher Conflicts Found: {teacher_conflicts_count} class instances")
    print(f"   (Across {len(teacher_conflict_instances)} unique teachers)")
    print(f"   (Across {len(problematic_time_slots)} problematic time slots)")
    print()
    
    # Top teachers
    sorted_teachers = sorted(teacher_conflict_instances.items(), 
                            key=lambda x: x[1], reverse=True)[:5]
    print("   Top 5 Most Conflicted Teachers:")
    for i, (teacher, count) in enumerate(sorted_teachers, 1):
        print(f"     {i}. {teacher}: {count} conflicts")
    print()
    
    # ========================================================================
    # METHOD 2: Count Room Conflicts (Groupby)
    # ========================================================================
    print("🔍 METHOD 2: Room Conflict Detection (Groupby)")
    print("-" * 70)
    
    # Group by room, day, start time
    room_grouped = df.groupby([room_col, day_col, time_start_col])
    
    room_conflicts_count = 0
    room_conflict_instances = {}  # {room: count}
    problematic_rooms = []
    
    for (room, day, time_slot), group in room_grouped:
        num_classes = len(group)
        
        # A conflict occurs when one room has >1 class at same time
        # Exclude "SIN AULA ASIGNADA" (unassigned)
        if (num_classes > 1 and room and not pd.isna(room) and 
            room.strip() and room.upper() != 'SIN AULA ASIGNADA'):
            
            room_conflicts_count += num_classes  # Count each conflicting class
            
            if room not in room_conflict_instances:
                room_conflict_instances[room] = 0
            room_conflict_instances[room] += num_classes
            
            problematic_rooms.append({
                'room': room,
                'day': day,
                'time': time_slot,
                'classes': num_classes
            })
    
    print(f"✅ Room Conflicts Found: {room_conflicts_count} class instances")
    print(f"   (Across {len(room_conflict_instances)} unique rooms)")
    print(f"   (Across {len(problematic_rooms)} problematic time slots)")
    print()
    
    # Top rooms
    sorted_rooms = sorted(room_conflict_instances.items(), 
                         key=lambda x: x[1], reverse=True)[:5]
    print("   Top 5 Most Conflicted Rooms:")
    for i, (room, count) in enumerate(sorted_rooms, 1):
        print(f"     {i}. {room}: {count} conflicts")
    print()
    
    # ========================================================================
    # METHOD 3: Count Unique Conflict Instances
    # ========================================================================
    print("🔍 METHOD 3: Unique Conflict Instances")
    print("-" * 70)
    
    # Teacher conflicts: count each unique (teacher, day, time) slot with conflicts
    unique_teacher_conflict_slots = len(problematic_time_slots)
    print(f"✅ Unique Teacher Conflict Slots: {unique_teacher_conflict_slots}")
    
    # Room conflicts: count each unique (room, day, time) slot with conflicts
    unique_room_conflict_slots = len(problematic_rooms)
    print(f"✅ Unique Room Conflict Slots: {unique_room_conflict_slots}")
    print()
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("=" * 70)
    print("📋 VERIFICATION SUMMARY")
    print("=" * 70)
    print()
    print("If counting by CLASS INSTANCES (each class in a conflict):")
    print(f"  • Teacher conflicts: {teacher_conflicts_count} instances")
    print(f"  • Room conflicts: {room_conflicts_count} instances")
    print(f"  • TOTAL: {teacher_conflicts_count + room_conflicts_count} instances")
    print()
    
    print("If counting by CONFLICT SLOTS (each time slot with >1 class):")
    print(f"  • Teacher conflict slots: {unique_teacher_conflict_slots}")
    print(f"  • Room conflict slots: {unique_room_conflict_slots}")
    print(f"  • TOTAL: {unique_teacher_conflict_slots + unique_room_conflict_slots}")
    print()
    
    # ========================================================================
    # DETAILED EXAMPLES
    # ========================================================================
    print("=" * 70)
    print("📌 DETAILED CONFLICT EXAMPLES")
    print("=" * 70)
    print()
    
    print("🔴 Sample Teacher Conflicts:")
    for i, slot in enumerate(problematic_time_slots[:3], 1):
        print(f"\n  Example {i}:")
        print(f"    Teacher: {slot['teacher']}")
        print(f"    Day: {slot['day']}")
        print(f"    Time: {slot['time']}")
        print(f"    Classes: {slot['classes']}")
        
        # Get the actual classes in this conflict
        mask = ((df[teacher_col] == slot['teacher']) & 
                (df[day_col] == slot['day']) & 
                (df[time_start_col] == slot['time']))
        conflicting = df[mask]
        
        for idx, (_, row) in enumerate(conflicting.iterrows(), 1):
            course = row.get(course_col, "Unknown")
            room = row.get(room_col, "SIN AULA")
            print(f"      {idx}. {course} → {room}")
    
    print("\n\n🔴 Sample Room Conflicts:")
    for i, slot in enumerate(problematic_rooms[:3], 1):
        print(f"\n  Example {i}:")
        print(f"    Room: {slot['room']}")
        print(f"    Day: {slot['day']}")
        print(f"    Time: {slot['time']}")
        print(f"    Classes: {slot['classes']}")
        
        # Get the actual classes in this conflict
        mask = ((df[room_col] == slot['room']) & 
                (df[day_col] == slot['day']) & 
                (df[time_start_col] == slot['time']))
        conflicting = df[mask]
        
        for idx, (_, row) in enumerate(conflicting.iterrows(), 1):
            course = row.get(course_col, "Unknown")
            teacher = row.get(teacher_col, "Unknown")
            print(f"      {idx}. {course} ({teacher})")
    
    print("\n" + "=" * 70)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    verify_conflicts()
