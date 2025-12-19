"""
utils.py - Utility Functions for Data Processing

Helper functions for data preparation, duration calculation, and formatting
"""

import os
import pandas as pd
import logging
from config import OUTPUT_SCHEDULE_FILE, logger

# ==============================================================================
# DATA PREPARATION HELPERS
# ==============================================================================

def load_and_prepare_schedule_data():
    """
    Load and clean the generated schedule CSV file.
    
    Returns:
        DataFrame: Clean, ready-to-use schedule data
        
    Raises:
        FileNotFoundError: If output schedule file doesn't exist
        Exception: If data processing fails
    """
    try:
        if not os.path.exists(OUTPUT_SCHEDULE_FILE):
            raise FileNotFoundError(f"Schedule file not found: {OUTPUT_SCHEDULE_FILE}")
        
        # Load the CSV
        df = pd.read_csv(OUTPUT_SCHEDULE_FILE, dtype=str).fillna('')
        
        # Clean and prepare the data
        # Ensure required columns exist (NEW SCHEDULER FORMAT)
        required_cols = ['n_codper', 'c_nomcur', 'teacher_names', 'day_of_week', 'start_time', 'end_time', 'room_id', 'activity_type']
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"⚠️  Missing column in schedule: {col}")
        
        # Convert time columns to proper format if needed
        if 'start_time' in df.columns:
            df['start_time'] = df['start_time'].astype(str).str.strip()
        if 'end_time' in df.columns:
            df['end_time'] = df['end_time'].astype(str).str.strip()
        
        # Create useful derived columns
        if 'start_time' in df.columns and 'end_time' in df.columns:
            df['duration'] = df.apply(
                lambda row: calculate_duration(row['start_time'], row['end_time']) 
                if row['start_time'] and row['end_time'] else '0h',
                axis=1
            )
        
        # Add time period category
        if 'start_time' in df.columns:
            df['time_period'] = df['start_time'].apply(get_time_period)
        
        logger.info(f"✅ Successfully loaded and prepared schedule data ({len(df)} rows)")
        return df
        
    except Exception as e:
        logger.error(f"❌ Error preparing schedule data: {e}")
        raise


def calculate_duration(start_time, end_time):
    """
    Calculate duration between two times (HH:MM format).
    
    Args:
        start_time (str): Start time in HH:MM format
        end_time (str): End time in HH:MM format
        
    Returns:
        str: Duration string (e.g., "1h30m", "2h")
    """
    try:
        if not start_time or not end_time:
            return '0h'
        start_h, start_m = map(int, start_time.split(':'))
        end_h, end_m = map(int, end_time.split(':'))
        duration_m = (end_h * 60 + end_m) - (start_h * 60 + start_m)
        hours = duration_m // 60
        mins = duration_m % 60
        return f"{hours}h{mins}m" if mins > 0 else f"{hours}h"
    except Exception:
        return "0h"


def get_time_period(time_str):
    """
    Get time period category based on hour.
    
    Args:
        time_str (str): Time in HH:MM format
        
    Returns:
        str: 'morning', 'afternoon', 'evening', or ''
    """
    try:
        if not time_str:
            return ''
        hour = int(time_str.split(':')[0])
        if 7 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 18:
            return 'afternoon'
        elif 18 <= hour <= 22:
            return 'evening'
        return ''
    except Exception:
        return ''


# ==============================================================================
# DATA ANALYSIS HELPERS
# ==============================================================================

def get_filter_options_from_schedule(df):
    """
    Extract unique values for filtering from schedule DataFrame.
    
    Args:
        df (DataFrame): Schedule data
        
    Returns:
        dict: Filter options for UI
    """
    try:
        filters = {
            'terms': sorted(df['n_codper'].unique().tolist()) if 'n_codper' in df.columns else [],
            'courses': sorted(df['c_nomcur'].unique().tolist()) if 'c_nomcur' in df.columns else [],
            'teachers': sorted(df[df.get('teacher_names', '') != '']['teacher_names'].unique().tolist()) if 'teacher_names' in df.columns else [],
            'rooms': sorted(df[df.get('room_id', '') != 'UNASSIGNED']['room_id'].unique().tolist()) if 'room_id' in df.columns else [],
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        }
        return filters
    except Exception as e:
        logger.error(f"Error extracting filter options: {e}")
        return {
            'terms': [],
            'courses': [],
            'teachers': [],
            'rooms': [],
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        }
