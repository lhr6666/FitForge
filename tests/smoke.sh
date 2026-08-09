#!/bin/bash
# 端到端 smoke test - 验证 /auth/register 7 个场景
# 用法：bash tests/smoke.sh

set -e

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "=== Smoke test: $BASE_URL ==="
echo ""

echo "Test 1: GET / (健康检查)"
curl -s -w "  HTTP %{http_code}\n" "$BASE_URL/"

echo ""
echo "Test 2: GET /docs (Swagger UI)"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" "$BASE_URL/docs"

echo ""
echo "Test 3: GET /openapi.json (OpenAPI schema)"
curl -s "$BASE_URL/openapi.json" | python -c "
import sys, json
d = json.load(sys.stdin)
print('  paths:', list(d.get('paths', {}).keys()))
print('  schemas:', list(d.get('components', {}).get('schemas', {}).keys()))
"

echo ""
echo "Test 4: POST /auth/register (success -> 201)"
curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_alice","email":"smoke_alice@example.com","password":"Password123","nickname":"Alice"}' \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 5: POST /auth/register (duplicate username -> 409)"
curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_alice","email":"smoke_alice2@example.com","password":"Password123"}' \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 6: POST /auth/register (weak password -> 422)"
curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_bob","email":"smoke_bob@example.com","password":"12345678"}' \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 7: POST /auth/register (missing email -> 422)"
curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_charlie","password":"Password123"}' \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "=== Done ==="