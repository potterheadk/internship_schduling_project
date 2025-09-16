from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from datetime import datetime
import asyncio
from cachetools import TTLCache

app = FastAPI(
    title="UMA Schedule Management FastAPI Integration",
    description="FastAPI middleware for UMA's scheduling system",
    version="1.0.0"
)

# Cache for API responses
cache = TTLCache(maxsize=100, ttl=300)  # Cache for 5 minutes

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base configuration
NEST_API_URL = "http://localhost:3000"

# Models
class ScheduleFilter(BaseModel):
    n_codper: Optional[str] = None
    c_codfac: Optional[str] = None
    c_codesp: Optional[str] = None
    c_codcur: Optional[str] = None
    n_ciclo: Optional[int] = None
    turno_id: Optional[int] = None
    modalidad: Optional[str] = None
    estado: Optional[int] = None
    page: Optional[int] = 1
    limit: Optional[int] = 10

class TeacherFilter(BaseModel):
    c_codfac: Optional[str] = None
    c_codesp: Optional[str] = None
    include_schedule: Optional[bool] = False
    include_courses: Optional[bool] = False
    include_classrooms: Optional[bool] = False

class ClassroomFilter(BaseModel):
    building: Optional[str] = None
    floor: Optional[int] = None
    capacity_min: Optional[int] = None
    capacity_max: Optional[int] = None
    include_schedule: Optional[bool] = False
    include_teachers: Optional[bool] = False

class ScheduleOptimizationRules(BaseModel):
    max_hours_per_day: int = 8
    preferred_start_time: str = "08:00"
    preferred_end_time: str = "18:00"
    lunch_break: bool = True
    lunch_break_duration: int = 60  # minutes

# Helper functions
async def fetch_from_nest(endpoint: str, method: str = "GET", data: Dict = None, params: Dict = None) -> Dict:
    """Fetch data from NestJS backend with caching."""
    cache_key = f"{method}:{endpoint}:{str(data)}:{str(params)}"
    
    if method == "GET" and cache_key in cache:
        return cache[cache_key]
    
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                response = await client.get(f"{NEST_API_URL}{endpoint}", params=params)
            else:
                response = await client.post(f"{NEST_API_URL}{endpoint}", json=data)
            
            response.raise_for_status()
            result = response.json()
            
            if method == "GET":
                cache[cache_key] = result
            
            if not result:
                return [] if endpoint.startswith("/docente") or endpoint.startswith("/aula") else {}
            
            return result
        except httpx.HTTPError as e:
            print(f"Error calling {endpoint}: {str(e)}")
            return [] if endpoint.startswith("/docente") or endpoint.startswith("/aula") else {}
        except Exception as e:
            print(f"Unexpected error calling {endpoint}: {str(e)}")
            return [] if endpoint.startswith("/docente") or endpoint.startswith("/aula") else {}

def optimize_schedule(schedule: Dict, rules: ScheduleOptimizationRules) -> Dict:
    """Apply schedule optimization rules."""
    # Implement optimization logic here
    # This is a placeholder for your actual optimization algorithm
    return schedule

def validate_schedule_conflicts(schedule: Dict) -> List[str]:
    """Check for scheduling conflicts."""
    conflicts = []
    # Implement conflict detection logic here
    return conflicts

# API endpoints
@app.get("/api/schedule/optimize/{turno_id}")
async def get_optimized_schedule(
    turno_id: int,
    rules: ScheduleOptimizationRules = Depends()
) -> Dict:
    """Get and optimize schedule for a specific turn."""
    # Fetch original schedule
    schedule = await fetch_from_nest(f"/horario/turno/{turno_id}")
    
    # Apply optimization
    optimized = optimize_schedule(schedule, rules)
    
    # Check for conflicts
    conflicts = validate_schedule_conflicts(optimized)
    if conflicts:
        return {
            "original": schedule,
            "optimized": optimized,
            "conflicts": conflicts,
            "status": "conflicts_detected"
        }
    
    return {
        "original": schedule,
        "optimized": optimized,
        "conflicts": [],
        "status": "success"
    }

@app.get("/api/schedule/summary")
async def get_schedule_summary(
    filters: ScheduleFilter = Depends(),
    include_stats: bool = False
) -> Dict:
    """
    Get a summary of schedules with optional filtering and statistics.
    
    Parameters:
    - filters: Standard schedule filters (period, faculty, etc.)
    - include_stats: Include additional statistics about schedules
    """
    try:
        # Build query parameters
        params = {k: v for k, v in filters.dict().items() if v is not None}
        
        # Fetch data sequentially for better error handling
        results = {}
        try:
            results["turns"] = await fetch_from_nest("/turno", params=params)
            if not isinstance(results["turns"], list):
                results["turns"] = []
        except Exception as e:
            print(f"Error fetching turns: {str(e)}")
            results["turns"] = []
            
        try:
            results["courses"] = await fetch_from_nest("/horario/curso", params=params)
            if not isinstance(results["courses"], list):
                results["courses"] = []
        except Exception as e:
            print(f"Error fetching courses: {str(e)}")
            results["courses"] = []
            
        try:
            results["teachers"] = await fetch_from_nest("/docente")
            if not isinstance(results["teachers"], list):
                results["teachers"] = []
        except Exception as e:
            print(f"Error fetching teachers: {str(e)}")
            results["teachers"] = []
            
        try:
            results["classrooms"] = await fetch_from_nest("/aula")
            if not isinstance(results["classrooms"], list):
                results["classrooms"] = []
        except Exception as e:
            print(f"Error fetching classrooms: {str(e)}")
            results["classrooms"] = []
        
        # Calculate schedule statistics
        stats = {}
        if include_stats:
            try:
                dashboard = await fetch_from_nest("/dashboard/1")
                stats = {
                    "classroom_utilization": calculate_classroom_utilization(results["classrooms"], results["courses"]),
                    "teacher_load": calculate_teacher_load(results["teachers"], results["courses"]),
                    "schedule_distribution": calculate_schedule_distribution(results["courses"]),
                    "dashboard_metrics": dashboard if isinstance(dashboard, dict) else {}
                }
            except Exception as e:
                print(f"Error calculating stats: {str(e)}")
                stats = {
                    "classroom_utilization": {"utilization_rate": 0.0},
                    "teacher_load": {"average_hours": 0.0},
                    "schedule_distribution": {"distribution": {}},
                    "dashboard_metrics": {}
                }
        
        # Generate summary
        summary = {
            "total_turns": len(results.get("turns", [])),
            "total_courses": len(results.get("courses", [])),
            "total_teachers": len(results.get("teachers", [])),
            "total_classrooms": len(results.get("classrooms", [])),
            "page": filters.page,
            "limit": filters.limit,
            "data": results
        }
        
        if include_stats:
            summary["statistics"] = stats
        
        return summary
        
    except Exception as e:
        print(f"Error in get_schedule_summary: {str(e)}")
        return {
            "total_turns": 0,
            "total_courses": 0,
            "total_teachers": 0,
            "total_classrooms": 0,
            "page": filters.page,
            "limit": filters.limit,
            "data": {"turns": [], "courses": [], "teachers": [], "classrooms": []},
            "error": str(e)
        }

@app.get("/api/teachers")
async def get_teachers(
    filters: TeacherFilter = Depends(),
    include_stats: bool = False
) -> Dict:
    """
    Get teachers with optional filters and related data.
    
    Parameters:
    - filters: Teacher-specific filters
    - include_stats: Include teaching statistics
    """
    try:
        # Build query parameters for teachers
        params = {
            "c_codfac": filters.c_codfac,
            "c_codesp": filters.c_codesp,
            "include_horario": filters.include_schedule,
            "include_curso": filters.include_courses,
            "include_aula": filters.include_classrooms
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        # Fetch teacher data
        teachers = await fetch_from_nest("/docente", params=params)
        
        if not isinstance(teachers, list):
            teachers = []
            
        if include_stats:
            # Fetch courses for statistics
            courses = await fetch_from_nest("/horario/curso")
            if not isinstance(courses, list):
                courses = []
                
            stats = {
                "teaching_hours": calculate_teaching_hours(teachers, courses),
                "course_distribution": calculate_course_distribution(teachers, courses),
                "specialization_areas": analyze_specialization_areas(teachers)
            }
            return {
                "total": len(teachers),
                "teachers": teachers,
                "statistics": stats
            }
        
        return {
            "total": len(teachers),
            "teachers": teachers
        }
    except Exception as e:
        print(f"Error in get_teachers: {str(e)}")
        return {
            "total": 0,
            "teachers": [],
            "error": str(e)
        }

@app.get("/api/classrooms")
async def get_classrooms(filters: ClassroomFilter = Depends()) -> Dict:
    """
    Get classrooms with filters and schedule information.
    
    Parameters:
    - filters: Classroom-specific filters
    """
    try:
        # Build base query parameters
        params = {
            "include_horario": filters.include_schedule,
            "include_docente": filters.include_teachers
        }
        
        # Fetch classroom data
        classrooms = await fetch_from_nest("/aula", params=params)
        
        if not isinstance(classrooms, list):
            classrooms = []
        
        # Apply additional filters
        filtered_classrooms = []
        for room in classrooms:
            try:
                # Safe type conversion and null checks
                room_capacity = int(str(room.get("n_capacidad", "0")).strip() or "0")
                room_floor = int(str(room.get("n_piso", "0")).strip() or "0")
                room_building = str(room.get("pabellon", "")).strip().upper()
                
                if filters.building and room_building != str(filters.building).strip().upper():
                    continue
                    
                if filters.floor is not None and room_floor != filters.floor:
                    continue
                    
                if filters.capacity_min is not None and room_capacity < filters.capacity_min:
                    continue
                    
                if filters.capacity_max is not None and room_capacity > filters.capacity_max:
                    continue
                    
                filtered_classrooms.append(room)
            except (ValueError, TypeError) as e:
                print(f"Error processing room {room.get('id', 'unknown')}: {str(e)}")
                continue
        
        return {
            "total": len(filtered_classrooms),
            "classrooms": filtered_classrooms
        }
    except Exception as e:
        print(f"Error in get_classrooms: {str(e)}")
        return {
            "total": 0,
            "classrooms": [],
            "error": str(e)
        }

# Helper functions for statistics
def calculate_classroom_utilization(classrooms: List[Dict], courses: List[Dict]) -> Dict:
    """Calculate classroom utilization statistics."""
    # Implement utilization calculation logic
    return {"utilization_rate": 0.0}  # Placeholder

def calculate_teacher_load(teachers: List[Dict], courses: List[Dict]) -> Dict:
    """Calculate teacher workload statistics."""
    # Implement workload calculation logic
    return {"average_hours": 0.0}  # Placeholder

def calculate_schedule_distribution(courses: List[Dict]) -> Dict:
    """Analyze schedule distribution across time slots."""
    # Implement distribution analysis logic
    return {"distribution": {}}  # Placeholder

def calculate_teaching_hours(teachers: List[Dict], courses: List[Dict]) -> Dict:
    """Calculate teaching hours per teacher."""
    # Implement teaching hours calculation
    return {"hours_per_teacher": {}}  # Placeholder

def calculate_course_distribution(teachers: List[Dict], courses: List[Dict]) -> Dict:
    """Calculate course distribution among teachers."""
    # Implement course distribution analysis
    return {"courses_per_teacher": {}}  # Placeholder

def analyze_specialization_areas(teachers: List[Dict]) -> Dict:
    """Analyze teacher specialization areas."""
    # Implement specialization analysis
    return {"specialization_stats": {}}  # Placeholder

@app.post("/api/schedule/validate")
async def validate_schedule(schedule: Dict) -> Dict:
    """Validate a schedule before saving."""
    conflicts = validate_schedule_conflicts(schedule)
    return {
        "valid": not bool(conflicts),
        "conflicts": conflicts
    }

# Middleware for logging and monitoring
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log and monitor API requests."""
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds()
    
    # Log request details (implement your logging logic here)
    print(f"[{start_time}] {request.method} {request.url} - {duration}s")
    
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
