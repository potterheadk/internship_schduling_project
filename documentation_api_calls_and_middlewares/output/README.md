# API Endpoint Manifest Generator

This directory contains generated documentation and scripts for your API.

## Files

- routes.json: Structured JSON of all endpoints, DTOs, and frontend callers.
- routes.md: Markdown table of endpoints, DTOs, curl samples, and frontend usage.
- curl_samples.sh: Bash script with curl commands for each endpoint.
- fetch_responses.sh: Bash script to run curl_samples.sh and save responses.

## Usage

1. Set your JWT token in the scripts:

   export TOKEN="<PUT_JWT_HERE>"

2. Run curl samples:

   ./curl_samples.sh

3. Fetch and save responses (GET only by default):

   ./fetch_responses.sh

   To run destructive requests (POST/PUT/DELETE/PATCH):

   ./fetch_responses.sh --force

4. To regenerate, run:

   node ../generate_routes.js

