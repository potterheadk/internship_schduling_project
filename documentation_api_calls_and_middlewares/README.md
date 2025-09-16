# UMA Schedule Management System Documentation

## Documentation Guide

This repository contains comprehensive documentation and tools for the UMA Schedule Management System. Use this guide to find the information you need quickly.

### What Documentation Should I Read?

#### 1. For API Users and Developers

- **[API_DOCUMENTATION.md](./API_DOCUMENTATION.md)**
  - Complete API endpoint reference
  - Authentication methods
  - Request/response formats
  - Error handling

#### 2. For FastAPI Integration

- **[README_FASTAPI.md](./README_FASTAPI.md)**
  - FastAPI middleware setup
  - Extended API features
  - Performance optimization
  - Data models and validation

#### 3. For Tools and Scripts

- **[README_SCRIPTS.md](./README_SCRIPTS.md)**
  - API exploration tools
  - Documentation generators
  - Testing utilities
  - Development guidelines

#### 4. For Generated Content

- **[output/README.md](./output/README.md)**
  - Generated API manifests
  - Schema definitions
  - Code examples
  - Integration guides

### Quick Start Guide by Role

1. **New Developer?**

   - Start with this README
   - Then read API_DOCUMENTATION.md
   - Follow setup instructions below

2. **Backend Developer?**

   - API_DOCUMENTATION.md for core endpoints
   - README_FASTAPI.md for integration
   - Check output/ for examples

3. **Frontend Developer?**

   - API_DOCUMENTATION.md for endpoints
   - output/curl_samples.sh for examples
   - output/routes.md for quick reference

4. **DevOps/Tools Developer?**
   - README_SCRIPTS.md for automation
   - Setup instructions below
   - Check output/ for configurations

## Project Structure

```
.
├── API_DOCUMENTATION.md     # Complete API reference
├── README.md               # This guide
├── README_FASTAPI.md      # FastAPI integration
├── README_SCRIPTS.md      # Tools documentation
├── explore_endpoints.sh    # API explorer script
├── fastapi_integration.py # FastAPI middleware
└── output/               # Generated content
    ├── routes.json      # API routes (JSON)
    ├── routes.md        # API routes (Markdown)
    ├── curl_samples.sh  # cURL examples
    └── README.md        # Output guide
```

## Quick Start

1. `API_DOCUMENTATION.md` - Comprehensive API documentation
2. `explore_endpoints.sh` - Interactive bash script for API exploration
3. `fastapi_integration.py` - FastAPI middleware example for custom integrations

## Setup

### 1. Configuration

Create a configuration file:

```bash
mkdir -p ~/.config
cp uma_api_explorer.conf.example ~/.config/uma_api_explorer.conf
```

Edit the configuration:

```bash
nano ~/.config/uma_api_explorer.conf
```

Add your JWT token:

```bash
TOKEN="your.jwt.token.here"
API_HOST="http://localhost:3000"
SAVE_RESPONSES=true
OUTPUT_DIR="output"
```

### 2. Dependencies

For the bash script:

```bash
# Install jq for JSON processing
sudo apt-get install jq
```

For the FastAPI integration:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn httpx cachetools
```

## Usage

### 1. API Explorer Script

Run the interactive explorer:

```bash
./explore_endpoints.sh
```

This will present a menu with options to:

- Explore classrooms
- Explore turn details
- Explore turns with filters
- Explore filter options

### 2. FastAPI Integration

Start the FastAPI server:

```bash
python fastapi_integration.py
```

The server provides:

- Schedule optimization: `GET /api/schedule/optimize/{turno_id}`
- Schedule summary: `GET /api/schedule/summary`
- Schedule validation: `POST /api/schedule/validate`

### 3. Making Custom Requests

Using the explorer script:

```bash
# Example: Get all turns for a specific period
./explore_endpoints.sh
# Choose option 3 (Explore Turns with Filters)
# Enter period: 20252
```

Using curl directly:

```bash
# Export your token
export TOKEN="your.jwt.token.here"

# Get turns
curl -sS -H "Authorization: Bearer $TOKEN" \
  'http://localhost:3000/turno?n_codper=20252' | jq .
```

## FastAPI Integration Details

The FastAPI integration provides several features:

1. Schedule Optimization

   - Applies custom rules to schedules
   - Checks for conflicts
   - Caches responses for performance

2. Data Aggregation

   - Combines data from multiple endpoints
   - Provides summary statistics
   - Supports filtering

3. Validation
   - Validates schedules before saving
   - Checks for common issues
   - Reports conflicts

## Examples

### 1. Get and Optimize a Schedule

```python
import httpx

async def optimize_schedule(turno_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/schedule/optimize/{turno_id}",
            params={
                "max_hours_per_day": 8,
                "preferred_start_time": "08:00"
            }
        )
        return response.json()
```

### 2. Get Schedule Summary

```python
import httpx

async def get_summary(period: str, faculty: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/schedule/summary",
            params={
                "n_codper": period,
                "c_codfac": faculty
            }
        )
        return response.json()
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details
