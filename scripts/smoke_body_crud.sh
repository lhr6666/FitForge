#!/usr/bin/env bash
# FitForge body_measurements + user_goals smoke test (11 端点)
#
# 覆盖端点：
#   body-measurements: POST / POST batch / GET list / GET {id} / PATCH {id} / DELETE {id}
#   user-goals:        POST / GET list / GET {id} / PATCH {id} / GET ?status=completed
#
# 用法：
#   1. 本地起服务：uvicorn main:app --host 127.0.0.1 --port 8000
#   2. 跑脚本：bash scripts/smoke_body_crud.sh
#   或一行：uvicorn main:app --log-level warning & sleep 3 && bash scripts/smoke_body_crud.sh
#
# 设计要点：
#   - 用 $SUFFIX 每次跑都生成唯一 username / email（不污染现有数据）
#   - body 写临时文件 + curl --data-binary（避免 bash 单引号字符串里 unicode 转义问题）
#   - POSIX bash 语法，Windows Git Bash / Linux / macOS 通用
#   - 每步打印 HTTP_CODE；失败不立即退出，方便看到完整失败链路
set -u  # 不开 -e，保留：失败也继续打，方便看完整链路

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
SUFFIX="$(date +%s)"
USERNAME="smoke_${SUFFIX}"
EMAIL="${USERNAME}@example.com"
PASSWORD="Smoke123"

# 临时目录放 JSON body 文件
TMPDIR="${TMPDIR:-/tmp}"
BODY_FILE="${TMPDIR}/smoke_body_${SUFFIX}.json"

step() { echo ""; echo "=== $1 ==="; }

# -----------------------------------------------------------------------------
step "2.1 register ${USERNAME}"
REG_RESP=$(curl -s -X POST "${BASE_URL}/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USERNAME}\",\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"nickname\":\"smoke\"}" \
  -w "\nHTTP_CODE=%{http_code}")
echo "${REG_RESP}"
REG_CODE=$(echo "${REG_RESP}" | grep -oE 'HTTP_CODE=[0-9]+' | tail -1 | cut -d= -f2)
[ "${REG_CODE}" = "201" ] || echo "WARN: register expected 201 got ${REG_CODE}"

# -----------------------------------------------------------------------------
step "2.2 login"
LOGIN_RESP=$(curl -s -X POST "${BASE_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}")
echo "${LOGIN_RESP}" | python -m json.tool
ACCESS=$(echo "${LOGIN_RESP}" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
echo "ACCESS_TOKEN length=${#ACCESS}"

# -----------------------------------------------------------------------------
step "2.3 POST /body-measurements (single)"
printf '{"weight":70.5,"recorded_at":"2026-08-16T08:30:00","notes":"morning fasted"}' > "${BODY_FILE}"
curl -s -X POST "${BASE_URL}/body-measurements" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  --data-binary @"${BODY_FILE}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# -----------------------------------------------------------------------------
step "2.4 POST /body-measurements/batch"
printf '{"items":[{"weight":71.0,"recorded_at":"2026-08-16T09:30:00"},{"weight":71.5,"recorded_at":"2026-08-16T20:00:00"}]}' > "${BODY_FILE}"
curl -s -X POST "${BASE_URL}/body-measurements/batch" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  --data-binary @"${BODY_FILE}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# -----------------------------------------------------------------------------
step "2.5 GET /body-measurements list (limit=10)"
LIST_RESP=$(curl -s "${BASE_URL}/body-measurements?limit=10" \
  -H "Authorization: Bearer ${ACCESS}")
echo "${LIST_RESP}"
# 取本用户最新一条的 id（D38：跨用户访问 404，故严格只取自己创的）
MID=$(echo "${LIST_RESP}" | python -c "import sys, json; d=json.load(sys.stdin); print(d[0]['id'])")
echo "MID=${MID}"

# -----------------------------------------------------------------------------
step "2.6 GET /body-measurements/{MID}"
curl -s "${BASE_URL}/body-measurements/${MID}" \
  -H "Authorization: Bearer ${ACCESS}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# -----------------------------------------------------------------------------
step "2.7 PATCH /body-measurements/{MID} (notes only)"
printf '{"notes":"morning fasted, revised"}' > "${BODY_FILE}"
curl -s -X PATCH "${BASE_URL}/body-measurements/${MID}" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  --data-binary @"${BODY_FILE}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# -----------------------------------------------------------------------------
step "2.8 POST /user-goals"
printf '{"type":"cut","target_value":75.0,"deadline":"2026-12-31"}' > "${BODY_FILE}"
curl -s -X POST "${BASE_URL}/user-goals" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  --data-binary @"${BODY_FILE}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# -----------------------------------------------------------------------------
step "2.9 GET /user-goals list (limit=10)"
GOALS_RESP=$(curl -s "${BASE_URL}/user-goals?limit=10" \
  -H "Authorization: Bearer ${ACCESS}")
echo "${GOALS_RESP}"
GOAL_ID=$(echo "${GOALS_RESP}" | python -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
echo "GOAL_ID=${GOAL_ID}"

# -----------------------------------------------------------------------------
step "2.10 PATCH /user-goals/{id} -> status=completed"
printf '{"status":"completed","notes":"smoke test goal completed"}' > "${BODY_FILE}"
curl -s -X PATCH "${BASE_URL}/user-goals/${GOAL_ID}" \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "Content-Type: application/json" \
  --data-binary @"${BODY_FILE}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# -----------------------------------------------------------------------------
step "2.11 GET /user-goals?status=completed (filter)"
curl -s "${BASE_URL}/user-goals?status=completed" \
  -H "Authorization: Bearer ${ACCESS}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# -----------------------------------------------------------------------------
step "2.12 DELETE /body-measurements/{MID} (硬删)"
curl -s -X DELETE "${BASE_URL}/body-measurements/${MID}" \
  -H "Authorization: Bearer ${ACCESS}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# -----------------------------------------------------------------------------
step "2.13 verify GET after DELETE (should 404, 防 ID 枚举)"
curl -s "${BASE_URL}/body-measurements/${MID}" \
  -H "Authorization: Bearer ${ACCESS}" \
  -w "\nHTTP_CODE=%{http_code}\n"

# 清理
rm -f "${BODY_FILE}"

echo ""
echo "=== smoke test done ==="
echo "user: ${USERNAME}"
echo "email: ${EMAIL}"