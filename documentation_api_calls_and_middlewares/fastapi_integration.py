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
async def fetch_from_nest(endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
    """Fetch data from NestJS backend with caching."""
    cache_key = f"{method}:{endpoint}:{str(data)}"
    
    if method == "GET" and cache_key in cache:
        return cache[cache_key]
    
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                response = await client.get(f"{NEST_API_URL}{endpoint}")
            else:
                response = await client.post(f"{NEST_API_URL}{endpoint}", json=data)
            
            response.raise_for_status()
            result = response.json()
            
            if method == "GET":
                cache[cache_key] = result
            
            return result
        except httpx.HTTPError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))

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
    # Build query parameters
    params = {k: v for k, v in filters.dict().items() if v is not None}
    
    # Fetch data from multiple endpoints in parallel
    async with asyncio.TaskGroup() as group:
        tasks = {
            "turns": group.create_task(fetch_from_nest("/turno", params=params)),
            "courses": group.create_task(fetch_from_nest("/horario/curso", params=params)),
            "teachers": group.create_task(fetch_from_nest("/docente")),
            "classrooms": group.create_task(fetch_from_nest("/aula")),
            "dashboard": group.create_task(fetch_from_nest("/dashboard/1")) if include_stats else None
        }
    
    # Process results
    results = {k: v.result() for k, v in tasks.items() if v is not None}
    
    # Calculate schedule statistics
    if include_stats:
        dashboard_data = results.pop("dashboard", {})
        stats = {
            "classroom_utilization": calculate_classroom_utilization(results["classrooms"], results["courses"]),
            "teacher_load": calculate_teacher_load(results["teachers"], results["courses"]),
            "schedule_distribution": calculate_schedule_distribution(results["courses"]),
            "dashboard_metrics": dashboard_data
        }
    else:
        stats = {}
    
    # Generate summary with pagination info if available
    summary = {
        "total_turns": len(results["turns"]),
        "total_courses": len(results["courses"]),
        "total_teachers": len(results["teachers"]),
        "total_classrooms": len(results["classrooms"]),
        "page": filters.page,
        "limit": filters.limit,
        "data": results
    }
    
    if include_stats:
        summary["statistics"] = stats
    
    return summary

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
    # Build query parameters for teachers
    params = {}
    if filters.c_codfac:
        params["c_codfac"] = filters.c_codfac
    if filters.c_codesp:
        params["c_codesp"] = filters.c_codesp
    
    # Include additional data based on filters
    params["horario"] = filters.include_schedule
    params["curso"] = filters.include_courses
    params["aula"] = filters.include_classrooms
    
    # Fetch teacher data
    teachers = await fetch_from_nest("/docente", params=params)
    
    if include_stats:
        # Fetch and calculate statistics
        courses = await fetch_from_nest("/horario/curso")
        stats = {
            "teaching_hours": calculate_teaching_hours(teachers, courses),
            "course_distribution": calculate_course_distribution(teachers, courses),
            "specialization_areas": analyze_specialization_areas(teachers)
        }
        return {
            "teachers": teachers,
            "statistics": stats
        }
    
    return {"teachers": teachers}

@app.get("/api/classrooms")
async def get_classrooms(filters: ClassroomFilter = Depends()) -> Dict:
    """
    Get classrooms with filters and schedule information.
    
    Parameters:
    - filters: Classroom-specific filters
    """
    # Build base query parameters
    params = {
        "horario": filters.include_schedule,
        "docente": filters.include_teachers
    }
    
    # Fetch classroom data
    classrooms = await fetch_from_nest("/aula", params=params)
    
    # Apply additional filters
    filtered_classrooms = [
        room for room in classrooms
        if (not filters.building or room.get("pabellon") == filters.building) and
           (not filters.floor or room.get("n_piso") == filters.floor) and
           (not filters.capacity_min or int(room.get("n_capacidad", 0)) >= filters.capacity_min) and
           (not filters.capacity_max or int(room.get("n_capacidad", 0)) <= filters.capacity_max)
    ]
    
    return {
        "total": len(filtered_classrooms),
        "classrooms": filtered_classrooms
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
