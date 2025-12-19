import pandas as pd
import os
import numpy as np
from datetime import datetime

class AnalyticsEngine:
    def __init__(self, csv_path='Output/final_schedule.csv'):
        self.csv_path = csv_path

    def get_dashboard_payload(self):
        """
        Generates the complete JSON payload for the Executive Dashboard.
        Includes data cleaning, KPI calculations, and raw records for client-side filtering.
        """
        if not os.path.exists(self.csv_path):
            return {'status': 'error', 'message': 'Schedule file not found. Please regenerate.'}

        try:
            df = pd.read_csv(self.csv_path)
            
            if df.empty:
                return {'status': 'error', 'message': 'Schedule file is empty.'}

            # --- 1. DATA CLEANING & NORMALIZATION ---
            
            # Fill text fields
            df['teacher_names'] = df['teacher_names'].fillna('TBA')
            df['room_id'] = df['room_id'].fillna('Unassigned').str.strip()
            df['activity_type'] = df['activity_type'].fillna('theory').str.lower().str.strip()
            df['nomesp'] = df['nomesp'].fillna('Unknown Department')
            df['c_nomcur'] = df['c_nomcur'].fillna('Unknown Course')
            df['turno'] = df['turno'].fillna('Unknown')
            
            # Parse Cycle (Extract numbers from strings like "Cycle 5" or "10")
            df['n_ciclo'] = pd.to_numeric(
                df['n_ciclo'].astype(str).str.extract(r'(\d+)')[0], 
                errors='coerce'
            ).fillna(0).astype(int)

            # Parse Times & Duration
            # Assumes format HH:MM. Safe slicing and conversion.
            df['start_hour_int'] = pd.to_numeric(
                df['start_time'].astype(str).str.slice(0, 2), errors='coerce'
            ).fillna(0).astype(int)
            
            df['end_hour_int'] = pd.to_numeric(
                df['end_time'].astype(str).str.slice(0, 2), errors='coerce'
            ).fillna(0).astype(int)

            # Calculate Duration (minimum 1 hour)
            df['duration'] = (df['end_hour_int'] - df['start_hour_int']).clip(lower=1)

            # --- 2. STATISTICAL AGGREGATIONS ---
            
            # A. Total Counts
            total_classes = len(df)
            
            # B. Modality Rates
            # Heuristic: 'virtual' vs 'lab' vs 'theory'
            modality_counts = {
                'virtual': int(df['activity_type'].str.contains('virtual').sum()),
                'lab': int(df['activity_type'].str.contains('lab').sum()),
                'theory': 0 # Calculated below to avoid overlap issues
            }
            modality_counts['theory'] = total_classes - (modality_counts['virtual'] + modality_counts['lab'])
            
            virtual_rate = round((modality_counts['virtual'] / total_classes * 100), 1) if total_classes > 0 else 0

            # C. Peak Congestion
            # Find the hour with the most simultaneous classes
            hour_counts = df['start_hour_int'].value_counts()
            peak_hour = int(hour_counts.idxmax()) if not hour_counts.empty else 0
            
            # D. Conflicts
            # Regex for common failure modes in room assignment
            conflicts = int(df['room_id'].str.count(r'(?i)(unassigned|fail|unscheduled|error)').sum())

            # --- 3. CLIENT-SIDE RECORDS PREPARATION ---
            # We send a optimized list of dicts so the JS can do live filtering.
            records = df[[
                'day_of_week', 'start_hour_int', 'duration',
                'room_id', 'teacher_names', 'nomesp', 'n_ciclo', 
                'activity_type', 'turno', 'c_nomcur'
            ]].to_dict(orient='records')

            return {
                'status': 'success',
                'timestamp': datetime.now().strftime('%d %b %Y, %H:%M'),
                'stats': {
                    'total_classes': total_classes,
                    'virtual_rate': virtual_rate,
                    'peak_hour': f"{peak_hour:02d}:00",
                    'conflicts': conflicts
                },
                'records': records
            }

        except Exception as e:
            print(f"Analytics Engine Error: {e}")
            return {'status': 'error', 'message': str(e)}