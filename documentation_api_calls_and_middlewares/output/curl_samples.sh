#!/usr/bin/env bash

# Usage: TOKEN="<PUT_JWT_HERE>" ./curl_samples.sh
# Each command prints the response.

TOKEN="<PUT_JWT_HERE>"

# GET /user
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/user' | jq .

# GET /sigu/especialidades
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/sigu/especialidades' | jq .

# GET /sigu/carreras-ciclo
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/sigu/carreras-ciclo' | jq .

# POST /sigu/curso
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/sigu/curso' -X POST -H "Content-Type: application/json" -d '{ /* PLEASE FILL */ }' | jq .

# GET /periodo
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/periodo' | jq .

# GET /docente
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/docente' | jq .

# GET /dashboard/1
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/dashboard/1' | jq .

# GET /auth/google
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/auth/google' | jq .

# GET /auth/google/callback
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/auth/google/callback' | jq .

# POST /admin/permisos
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/admin/permisos' -X POST -H "Content-Type: application/json" -d '{ /* PLEASE FILL */ }' | jq .

