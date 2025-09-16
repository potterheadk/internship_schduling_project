# UMA Schedule Management API Documentation

## Overview

This document provides comprehensive documentation for the UMA Schedule Management API endpoints.

## Related Documentation

- [FastAPI Integration Documentation](./README_FASTAPI.md) - Details about FastAPI middleware and extensions
- [API Scripts Documentation](./README_SCRIPTS.md) - Information about API exploration and documentation tools

## Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```bash
Authorization: Bearer <your_jwt_token>
```

## Core Modules

### 1. Authentication (`/auth`)

- `GET /auth/google` - Google OAuth login
- `GET /auth/google/callback` - Google OAuth callback
- `POST /auth/signin` - Local login
- `POST /auth/signup` - Register new user

### 2. Schedule Management (`/horario`)

- `GET /horario/turno/:turno_id` - Get schedules for a specific turn
- `GET /horario/curso` - Get courses with filters
  - Query params:
    - `n_codper`: Period code
    - `c_codfac`: Faculty code
    - `c_codesp`: Specialty code
    - `c_codcur`: Course code
    - `n_ciclo`: Cycle number
    - `turno_id`: Turn ID
    - `filtroBusqueda`: Search filter
    - `skip`: Pagination offset
    - `take`: Page size
    - `sortField`: Sort column
    - `sortOrder`: 'asc' or 'desc'
- `POST /horario` - Create schedule array
- `PUT /horario` - Update schedule array
- `DELETE /horario` - Delete schedule array

### 3. Academic System Integration (`/sigu`)

- `GET /sigu/especialidades` - Get all specialties
- `GET /sigu/carreras-ciclo` - Get careers by cycle
  - Query params:
    - `n_ciclo`: Cycle number
    - `c_codfac`: Faculty code
- `POST /sigu/curso` - Create/Update course from SIGU

### 4. Turn Management (`/turno`)

- `GET /turno` - Get turns with filters
  - Query params:
    - `c_codfac`: Faculty code
    - `c_codesp`: Specialty code
    - `c_codmod`: Module code
    - `n_codper`: Period code
    - `c_codpla`: Plan code
    - `n_ciclo`: Cycle number
    - `estado`: State
- `GET /turno/:id` - Get specific turn
- `POST /turno` - Create new turn
- `PUT /turno/:id` - Update turn
- `DELETE /turno/:id` - Delete turn

### 5. Classroom Management (`/aula`)

- `GET /aula` - Get all classrooms
  - Query params:
    - `horario`: Include schedule
    - `curso`: Include course
    - `docente`: Include teacher
- `GET /aula/docente` - Get teachers by classroom
  - Query params:
    - `aula_id`: Classroom ID
    - `dia`: Day
- `GET /aula/:ip` - Get classroom by IP

### 6. Teacher Management (`/docente`)

- `GET /docente` - Get all teachers
  - Query params:
    - `horario`: Include schedule
    - `curso`: Include course
    - `aula`: Include classroom
    - `c_codfac`: Faculty filter
    - `c_codesp`: Specialty filter
- `GET /docente/:id` - Get specific teacher
- `POST /docente` - Create teacher
- `PUT /docente` - Update teacher

### 7. Period Management (`/periodo`)

- `GET /periodo` - Get all periods
- `POST /periodo` - Create period
- `PUT /periodo/:n_codper` - Update period

### 8. Dashboard (`/dashboard`)

- `GET /dashboard/1` - Get main dashboard data
- `GET /dashboard/docente` - Get teacher dashboard
- `GET /dashboard/tipo_curso` - Get course type statistics
- `GET /dashboard/estado_turno` - Get turn state statistics

## Common Response Structures

### Schedule (Horario)

```typescript
interface Horario {
  id: number;
  dia: string;
  h_inicio: string;
  h_fin: string;
  n_horas: number;
  c_color: string;
  tipo: string;
  turno_id: number;
  curso_id: number;
  aula_id?: number;
  docente_id?: number;
}
```

### Course (Curso)

```typescript
interface Curso {
  id: number;
  n_codper: string;
  c_codmod: number;
  c_codfac: string;
  nom_fac: string;
  c_codesp: string;
  nomesp: string;
  c_codcur: string;
  c_nomcur: string;
  n_ciclo: number;
  c_area: string;
  turno_id: number;
}
```

### Turn (Turno)

```typescript
interface Turno {
  id: number;
  n_codper: string;
  n_codpla: string;
  c_codfac: string;
  c_codesp: string;
  n_ciclo: number;
  c_grpcur: string;
  estado: number;
}
```

## Error Handling

Common HTTP status codes:

- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

Error response format:

```json
{
  "statusCode": number,
  "message": string,
  "error": string
}
```

## FastAPI Integration Points

### Key Areas for FastAPI Middleware:

1. Schedule Optimization

```python
@app.middleware("http")
async def optimize_schedule(request: Request, call_next):
    if request.url.path.startswith("/horario"):
        # Implement schedule optimization logic
        pass
    response = await call_next(request)
    return response
```

2. Load Balancing

```python
@app.middleware("http")
async def balance_load(request: Request, call_next):
    if request.url.path.startswith("/turno"):
        # Implement load balancing logic
        pass
    response = await call_next(request)
    return response
```

3. Data Validation

```python
@app.middleware("http")
async def validate_data(request: Request, call_next):
    # Implement custom validation logic
    response = await call_next(request)
    return response
```

### Example FastAPI Integration:

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Proxy endpoint with custom logic
@app.get("/api/horario/turno/{turno_id}")
async def get_turn_schedule(turno_id: int, request: Request):
    async with httpx.AsyncClient() as client:
        # Forward request to NestJS backend
        response = await client.get(f"http://localhost:3000/horario/turno/{turno_id}")
        data = response.json()

        # Add custom processing logic here
        # Example: Optimize schedule
        optimized_data = optimize_schedule_algorithm(data)

        return optimized_data

# Custom schedule optimization
def optimize_schedule_algorithm(schedule_data: dict) -> dict:
    # Implement your schedule optimization logic here
    return schedule_data
```

## Testing with curl

See the companion script `explore_endpoints.sh` for interactive API testing.
