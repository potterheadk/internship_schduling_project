#!/usr/bin/env bash

# Usage: TOKEN="<PUT_JWT_HERE>" ./fetch_responses.sh [--force]
# This script runs curl_samples.sh and saves output to output/responses/<endpoint>.json
# Destructive requests (POST/PUT/DELETE/PATCH) require --force.

TOKEN="<PUT_JWT_HERE>"
mkdir -p output/responses

echo "# GET /user"
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/user' | jq . > output/responses/user.json
echo "# GET /sigu/especialidades"
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/sigu/especialidades' | jq . > output/responses/sigu-especialidades.json
echo "# GET /sigu/carreras-ciclo"
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/sigu/carreras-ciclo' | jq . > output/responses/sigu-carreras-ciclo.json
if [[ "$1" == "--force" ]]; then
  echo "# POST /sigu/curso"
  curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/sigu/curso' -X POST -H "Content-Type: application/json" -d '{ /* PLEASE FILL */ }' | jq . > output/responses/sigu-curso.json
fi
echo "# GET /periodo"
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/periodo' | jq . > output/responses/periodo.json
echo "# GET /docente"
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/docente' | jq . > output/responses/docente.json
echo "# GET /dashboard/1"
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/dashboard/1' | jq . > output/responses/dashboard-1.json
echo "# GET /auth/google"
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/auth/google' | jq . > output/responses/auth-google.json
echo "# GET /auth/google/callback"
curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/auth/google/callback' | jq . > output/responses/auth-google-callback.json
if [[ "$1" == "--force" ]]; then
  echo "# POST /admin/permisos"
  curl -sS -H "Authorization: Bearer $TOKEN" 'http://localhost:3000/admin/permisos' -X POST -H "Content-Type: application/json" -d '{ /* PLEASE FILL */ }' | jq . > output/responses/admin-permisos.json
fi
