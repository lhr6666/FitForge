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

# ============================================================
# /auth/login + refresh + logout + me 新增测试
# ============================================================

echo ""
echo "Test 8: POST /auth/login (success -> 200)"
# 先注册测试用户
curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_loginuser","email":"smoke_login@example.com","password":"Password123"}' > /dev/null
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke_login@example.com","password":"Password123"}')
ACCESS_TOKEN=$(echo "$LOGIN_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
REFRESH_TOKEN=$(echo "$LOGIN_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
echo "  access_token:  ${ACCESS_TOKEN:0:30}..."
echo "  refresh_token: ${REFRESH_TOKEN:0:30}..."

echo ""
echo "Test 9: POST /auth/login (wrong password -> 401)"
curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke_login@example.com","password":"WrongPass1"}' \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 10: GET /auth/me (with Bearer -> 200)"
curl -s "$BASE_URL/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 11: GET /auth/me (without Bearer -> 401)"
curl -s "$BASE_URL/auth/me" -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 12: POST /auth/refresh (rotate -> 200)"
NEW_REFRESH_RESP=$(curl -s -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}")
NEW_REFRESH=$(echo "$NEW_REFRESH_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
echo "  new_refresh: ${NEW_REFRESH:0:30}..."

echo ""
echo "Test 13: POST /auth/refresh (old revoked -> 401)"
curl -s -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}" \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 14: POST /auth/logout (revoke -> 204)"
curl -s -X POST "$BASE_URL/auth/logout" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$NEW_REFRESH\"}" \
  -w "  HTTP %{http_code}\n"

echo ""
echo "=== Done ==="