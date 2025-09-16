# FastAPI Integration for UMA Schedule Management

## Overview

This FastAPI integration provides middleware and extensions for the UMA Schedule Management System. It adds advanced features like schedule optimization, statistics calculation, and data aggregation.

## Features

### 1. Schedule Management

- Schedule optimization
- Conflict detection
- Workload balancing
- Resource utilization tracking

### 2. Data Analysis

- Teacher workload statistics
- Classroom utilization metrics
- Schedule distribution analysis
- Course allocation patterns

### 3. API Extensions

- Enhanced filtering
- Batch operations
- Statistics generation
- Data validation

## Setup

1. **Create Virtual Environment**

```bash
python -m venv venv
source venv/bin/activate
```

2. **Install Dependencies**

```bash
pip install fastapi uvicorn httpx cachetools
```

3. **Configuration**

```bash
# Create a .env file
cat > .env << EOF
NEST_API_URL="http://localhost:3000"
CACHE_TTL=300
CACHE_MAXSIZE=100
EOF
```

4. **Run the Server**

```bash
python fastapi_integration.py
```

## API Endpoints

### 1. Schedule Summary

```http
GET /api/schedule/summary
```

Parameters:

- `filters`: Schedule filters (period, faculty, etc.)
- `include_stats`: Include additional statistics

Example:

```bash
curl "http://localhost:8000/api/schedule/summary?include_stats=true&n_codper=20252"
```

### 2. Schedule Optimization

```http
GET /api/schedule/optimize/{turno_id}
```

Parameters:

- `turno_id`: Turn ID to optimize
- `rules`: Optimization rules

Example:

```bash
curl "http://localhost:8000/api/schedule/optimize/1234" \
  -H "Content-Type: application/json" \
  -d '{
    "max_hours_per_day": 8,
    "preferred_start_time": "08:00",
    "lunch_break": true
  }'
```

### 3. Teacher Information

```http
GET /api/teachers
```

Parameters:

- `filters`: Teacher filters
- `include_stats`: Include teaching statistics

Example:

```bash
curl "http://localhost:8000/api/teachers?include_stats=true&c_codfac=SALUD"
```

### 4. Classroom Management

```http
GET /api/classrooms
```

Parameters:

- `filters`: Classroom filters
- `include_schedule`: Include schedule information

Example:

```bash
curl "http://localhost:8000/api/classrooms?capacity_min=30&building=B"
```

## Data Models

### 1. Schedule Filter

```python
class ScheduleFilter(BaseModel):
    n_codper: Optional[str]        # Period code
    c_codfac: Optional[str]        # Faculty code
    c_codesp: Optional[str]        # Specialty code
    c_codcur: Optional[str]        # Course code
    n_ciclo: Optional[int]         # Cycle number
    turno_id: Optional[int]        # Turn ID
    modalidad: Optional[str]       # Modality
    estado: Optional[int]          # State
    page: Optional[int]            # Page number
    limit: Optional[int]           # Items per page
```

### 2. Optimization Rules

```python
class ScheduleOptimizationRules(BaseModel):
    max_hours_per_day: int         # Maximum teaching hours per day
    preferred_start_time: str      # Preferred day start time
    preferred_end_time: str        # Preferred day end time
    lunch_break: bool              # Include lunch break
    lunch_break_duration: int      # Break duration in minutes
```

## Customization

### 1. Adding New Endpoints

```python
@app.get("/api/custom/endpoint")
async def custom_endpoint(
    param: str,
    filter: CustomFilter = Depends()
) -> Dict:
    # Implementation
    pass
```

### 2. Extending Statistics

```python
def calculate_custom_stats(data: List[Dict]) -> Dict:
    # Custom statistics calculation
    return {"stat_name": "value"}
```

### 3. Custom Filters

```python
class CustomFilter(BaseModel):
    # Define custom filter fields
    field1: Optional[str]
    field2: Optional[int]
```

## Error Handling

The integration includes comprehensive error handling:

1. **HTTP Errors**

```python
raise HTTPException(status_code=404, detail="Resource not found")
```

2. **Validation Errors**

```python
raise ValidationError("Invalid schedule format")
```

3. **Business Logic Errors**

```python
raise BusinessLogicError("Schedule conflict detected")
```

## Performance Considerations

1. **Caching**

- Response caching with TTL
- Cache invalidation on updates
- Selective caching based on endpoint

2. **Parallel Processing**

- Async request handling
- Parallel data fetching
- Batch processing

3. **Resource Management**

- Connection pooling
- Rate limiting
- Request timeouts

## Development Guidelines

1. **Adding Features**

- Create new endpoints in relevant sections
- Add appropriate models and validators
- Include error handling
- Write documentation

2. **Testing**

```bash
# Run tests
pytest tests/

# Test specific endpoint
pytest tests/test_schedule.py -k "test_optimization"
```

3. **Documentation**

- Update this README for major changes
- Add docstrings to new functions
- Include example requests/responses

## Troubleshooting

1. **Common Issues**

- Connection errors
- Cache invalidation
- Data consistency

2. **Debugging**

- Enable debug logging
- Check request/response cycle
- Validate data formats

## Support

- GitHub Issues: [Report Issues](https://github.com/rodrigo378/nest_docente/issues)
- Documentation: See API_DOCUMENTATION.md
- Examples: See examples/ directory
