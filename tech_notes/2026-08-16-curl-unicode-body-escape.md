# bash 单引号 + curl + 中文 unicode body = 400 —— 真 HTTP smoke 才会暴露的工程坑

> **日期**：2026-08-16（周六补周五内容）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D40（SQLite in-memory for tests，与本坑同期发现）；本坑独立 tech_notes 沉淀，无对应 D 决策编号
> **关联 commit**：`9f4f927`（smoke 脚本固化方案 A：body 写到临时文件 + `curl --data-binary @file`）
> **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md` §3.7-§3.10 + §3.11
> **目的**：面试前复习 + bash ↔ curl ↔ Python 字节流边界 + pytest 为什么测不到真 HTTP 坑 + CI smoke 国际化方案

---

## 1. 症状：curl POST 含中文 → 400 There was an error parsing the body

跑 smoke 脚本时遇到：

```bash
curl -s -X POST http://127.0.0.1:8000/user-goals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"cut","notes":"3 个月减到 75kg"}'
```

响应：

```
400 Bad Request
{"detail":"There was an error parsing the body"}
```

**诡异之处**：

- 同样的 JSON 在 Python `requests.post()` 里能成功
- 同样的 schema 在 pytest httpx AsyncClient 里 e2e 测试全过
- 直接 `python -c "print(json.dumps({...}))"` 也能解析

这是**真 HTTP smoke 才会暴露**的字符编码坑。

---

## 2. 复现路径：bash 单引号 → curl → Python FastAPI 三层字符编码转换

### 2.1 bash 单引号的字符编码

```bash
# bash 在 Git Bash / WSL / Linux 都是 UTF-8 locale
echo '中文' | xxd
# 期望: e4 b8 ad e6 96 87 (UTF-8 字节序列)
```

bash 字符串的字符编码 = 当前 locale（`LANG=zh_CN.UTF-8`）= UTF-8。

### 2.2 curl 接收 body

curl 接收 `-d '...'` 参数时，**不会**对字符串做任何编码转换。它把字节流直接发给 server。

但 curl 内部有个细节：

- `-d` 默认走 `Content-Type: application/x-www-form-urlencoded`
- 加 `-H "Content-Type: application/json"` 后，curl 仍按"原始字节"发送
- **不发 `charset` 信息**——只发 `Content-Type: application/json`

### 2.3 Python FastAPI 接收

FastAPI 用 Starlette 解析 HTTP body：

```python
# Starlette 内部
body_bytes = await request.body()  # 原始字节（可能不完整或不正确）
body_str = body_bytes.decode("utf-8")  # 默认假设 UTF-8
data = json.loads(body_str)
```

如果 curl 发出的字节流**不是合法 UTF-8**（比如 bash 单引号里 `\` 转义出错、Windows CRLF、字节流被截断），`json.loads()` 抛 `JSONDecodeError` → FastAPI 返回 400。

### 2.4 真实失败场景

**场景 A**：bash 单引号里的 `$variable` 被解释（虽然单引号不该解释）

```bash
# ❌ 错误：单引号里的 $ 不会被解释，但 [...] 会被某些 shell 扩展
curl -d '{"notes":"[系统提示]"}'
# 实际发送: '{"notes":"[系统提示]"}' （没问题）

# 但如果是：
curl -d '{"notes":"a$b"}'  # bash 单引号，$b 不被解释
# 实际发送: '{"notes":"a$b"}' （没问题）

# 但如果双引号：
curl -d "{\"notes\":\"a$b\"}"  # bash 双引号，$b 被解释！
# 实际发送: '{"notes":"a"}'（$b 是空变量） → JSON 错误
```

**场景 B**：bash 单引号里**嵌套**单引号（最常见 bug）

```bash
# ❌ 错误：can't 包含单引号
curl -d '{"notes":"can't"}'
# bash 报错：syntax error

# 常见 workaround（错的）：
curl -d '{"notes":"can\'t"}'  # bash 单引号里 \' 不转义！
# 实际发送: '{"notes":"can\'t"}' → JSON 错误（合法 JSON 不该有 \')
```

**场景 C**：bash 单引号字符串 + UTF-8 多字节 + curl `--data-urlencode`

```bash
# 中文"测试"在 UTF-8 是 6 字节：e6 b5 8b e8 af 95
# bash 单引号里原样保留这 6 字节
# 但如果用了 --data-urlencode，curl 会把中文 URL-encode 成 %E6%B5%8B%E8%AF%95
# 此时 Content-Type 是 application/x-www-form-urlencoded
# 但你又加了 -H "Content-Type: application/json" → 矛盾
```

**场景 D（最隐蔽）**：Windows Git Bash + UTF-8 BOM

```
文件保存为 UTF-8 BOM: EF BB BF + '{"notes":"测试"}'
curl -d @file.json
# curl 看到前 3 字节是 BOM，json.loads() 解析失败
```

---

## 3. 排查过程：为什么 pytest httpx 测不到

### 3.1 pytest httpx AsyncClient 走 in-process

```python
# tests/conftest.py
@pytest_asyncio.fixture
async def client(engine):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

`ASGITransport` 直接调用 FastAPI app 对象，**不经过 TCP/HTTP 层**——它在内存里把 `request` 对象传给 FastAPI handler。

**字符编码路径**：

```
pytest 测试代码
   ↓ json.dumps({"notes": "测试"})
Python str（已是 Unicode codepoint）
   ↓ str.encode("utf-8")
bytes
   ↓ ASGI scope["body"]
FastAPI 接收（已经是合法 UTF-8 字节流）
   ↓ json.loads(bytes.decode("utf-8"))
成功解析
```

**没有任何"bash → curl → 字节流"环节**——pytest 永远测不到 bash 单引号的字符编码坑。

### 3.2 Pydantic 直接 validate `'测试'` 没问题

```python
from schemas.goal import UserGoalCreate
UserGoalCreate(type="cut", notes="测试")  # 直接 OK
```

Pydantic 在 Python 内存层操作 string codepoint，不涉及字节编码。这又一层"测不到"。

### 3.3 FastAPI TestClient 同样测不到

```python
from fastapi.testclient import TestClient
client = TestClient(app)
client.post("/user-goals", json={"type": "cut", "notes": "测试"})
# 也走 in-process
```

**结论**：**只有真 HTTP smoke（curl / Postman / 浏览器）才能暴露 bash 单引号 + UTF-8 + HTTP 字节流的组合坑**。

---

## 4. 根因分析：bash ↔ curl 字节流边界

### 4.1 字节流边界在哪切断

```
bash 进程内存（str: '{"notes":"测试"}'）
   ↓ str.encode("utf-8")  ← bash 内部
bytes: 7b 22 6e 6f 74 65 73 22 3a 22 e6 b5 8b e8 af 95 22 7d
   ↓ bash 调用 execvp("curl", ...)
   ↓ OS fork() 子进程
   ↓ 子进程 exec curl
curl 进程内存（接收 argv[2] = -d 后面的字符串）
   ↓ curl 把它当作 Content-Body
   ↓ curl 调用 send() 系统调用
   ↓ 内核 TCP 栈发送字节流
HTTP 响应服务器收到 bytes
```

**潜在切断点**：

1. **bash → curl argv 传递**：bash 用 `execvp` 传字符串，理论上**字节流连续**（不会切断 UTF-8 多字节序列），但...
2. **bash 单引号 + escape 处理**：bash 处理 `\\\'` 时可能生成意外字节
3. **curl 内部处理**：curl 看到 `-d` 默认 form-encode，但加了 `Content-Type: application/json` 后**应该**保留原字节

### 4.2 真正失败的根因（具体到 Git Bash + Windows）

**Git Bash on Windows + Windows console**：

```
Windows 默认 console code page = 936 (GBK) 或 65001 (UTF-8)
   ↓ 但 git bash 内部用的是 MSYS2，bash 的 str → bytes 用 UTF-8
   ↓ MSYS2 调用 curl.exe (Windows native binary)
   ↓ Windows curl.exe 看到 argv 是 UTF-8 bytes
   ↓ 但 Windows console API 默认 GBK...
   ↓ 字节流可能在某个环节被错误地重新解释为 GBK
```

**结果**：UTF-8 字节 `e6 b5 8b` 在 GBK 看来是 `娴` 或乱码 → 服务端 JSON 解析失败。

### 4.3 为什么 PowerShell 没事但 bash 失败

PowerShell 用 .NET 字符串（UTF-16），转 bytes 时显式选 encoding。bash + native curl.exe 跨进程有 encoding 不一致问题。

---

## 5. 三种修复方案（按推荐度排序）

### 5.1 方案 A（推荐）：body 写到临时文件 + `curl --data-binary @file`

```bash
# 1. 把 JSON body 写到临时文件（用 Python json.dumps 保证编码正确）
BODY=$(python -c "import json; print(json.dumps({'type': 'cut', 'notes': '3 个月减到 75kg'}, ensure_ascii=False))")
echo "$BODY" > /tmp/goal_body.json

# 2. curl 用 --data-binary 读文件
curl -s -X POST http://127.0.0.1:8000/user-goals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary @/tmp/goal_body.json
```

**为什么能解决**：

- Python `json.dumps(..., ensure_ascii=False)` 输出原生 UTF-8 字节（中文直接是 UTF-8 多字节，不是 `\uXXXX`）
- 文件保存 = 字节流保持原样（不经过 shell escape）
- `curl --data-binary @file` 按文件原始字节发送，不做任何转换
- `Content-Type: application/json; charset=utf-8` 显式告诉服务端编码

**额外好处**：

- 临时文件可以调试（cat 看实际字节）
- 大 body 不受命令行长度限制
- CI 友好（文件可纳入 git，或脚本动态生成）

### 5.2 方案 B：用 Python -c 调用 requests 库跑 smoke

```bash
python -c "
import requests
import json

# 1. login 拿 token
login = requests.post('http://127.0.0.1:8000/auth/login',
                     json={'email': 'smoke@example.com', 'password': 'Smoke123'})
access = login.json()['access_token']

# 2. POST goal with 中文
resp = requests.post('http://127.0.0.1:8000/user-goals',
                     json={'type': 'cut', 'notes': '3 个月减到 75kg'},
                     headers={'Authorization': f'Bearer {access}'})
print(f'status: {resp.status_code}')
print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
"
```

**为什么能解决**：

- requests 库是 Python 内置 → 字符编码全在 Python 控制内
- `json.dumps(..., ensure_ascii=False)` 显式 UTF-8 字节
- HTTP header 自动加 `Content-Type: application/json`

**缺点**：

- 失去 curl 的"零依赖"特性（要装 requests）
- 不像 shell 脚本那么"贴近真实环境"

### 5.3 方案 C：PowerShell `[System.Text.Encoding]::UTF8.GetBytes(...)` 强制 UTF-8

```powershell
# PowerShell on Windows
$body = [System.Text.Encoding]::UTF8.GetBytes('{"type":"cut","notes":"3 个月减到 75kg"}')
Invoke-WebRequest -Uri "http://127.0.0.1:8000/user-goals" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body `
  -Headers @{"Authorization" = "Bearer $TOKEN"}
```

**为什么能解决**：

- `[System.Text.Encoding]::UTF8.GetBytes()` 显式转 UTF-8 字节
- `Invoke-WebRequest` 用 .NET HttpClient，编码处理正确

**缺点**：

- 仅限 Windows + PowerShell
- 脚本语法复杂，难维护

> **面试话术**：「bash + curl + 中文 body 失败是经典的字节流边界问题。我用方案 A（body 写到临时文件 + `curl --data-binary @file`）——因为文件保存保持字节流原样，curl 不做任何编码转换，Python `json.dumps(ensure_ascii=False)` 显式 UTF-8。这是 CI 自动化 smoke 的最佳实践：把 JSON 构造交给 Python（编码正确），把 HTTP 发送交给 curl（贴近真实）。」

---

## 6. 为什么 pytest 不会暴露这个（in-process vs 真 HTTP）

### 6.1 in-process HTTP 栈

```
pytest
   ↓ 调用 httpx.AsyncClient.post()
httpx 构造 ASGI scope（dict）
   ↓ scope["body"] = bytes (Python str.encode("utf-8"))
ASGITransport 传给 FastAPI
   ↓ FastAPI 接收 request.body()
   ↓ json.loads() 成功
```

**字符编码环节**：

- Python str → bytes：在 Python 进程内（httpx 库）
- bytes → JSON parse：在同一 Python 进程内（FastAPI/Starlette）

**没有任何跨进程字节流边界**——所有转换在 Python C 运行时内完成。

### 6.2 真 HTTP 栈

```
bash 进程
   ↓ str.encode("utf-8") + execvp("curl")
   ↓ fork() + exec()  ← 跨进程边界
curl.exe 进程
   ↓ 接收 argv[2] = bytes
   ↓ 调用 send() 系统调用  ← 跨内核边界
Linux kernel TCP stack
   ↓ 字节流传到对端
FastAPI 进程（uvicorn）
   ↓ recv() 系统调用
   ↓ bytes.decode("utf-8")
   ↓ json.loads()
```

**字符编码环节**：

- 4 个独立进程（bash / curl / kernel / uvicorn）
- 每次跨进程都涉及字节流重新解释
- Windows + Git Bash + native curl.exe 还有额外的 MSYS2 ↔ Win32 API 转换

### 6.3 结论

| 场景                  | 字符编码环节数  | 能暴露 bash 单引号 + UTF-8 坑？ |
| ------------------- | -------- | ---------------------- |
| pytest + httpx       | 1（Python 内部） | ❌ 永远测不到                |
| FastAPI TestClient    | 1（同上）    | ❌ 永远测不到                |
| curl（Git Bash）       | 3+（bash / curl / kernel） | ✅ 会暴露                |
| Postman / Insomnia    | 1（GUI 内部） | ⚠️ 看实现，多数 OK 但偶尔坑       |
| 浏览器                  | 1（JS 内部）  | ✅ 不会（JS 字符串处理正确）     |

> **面试话术**：「in-process 测试和真 HTTP smoke 是两套测试金字塔——in-process 快（毫秒级）、覆盖业务逻辑；真 HTTP 慢（秒级）、覆盖字节流边界。我项目里 pytest + httpx 跑业务逻辑 e2e（30+ case），但部署后必须跑 curl smoke 验证字符编码 / HTTP 协议细节。两层都不能省。」

---

## 7. CI 自动化建议：smoke 脚本统一用方案 A

### 7.1 实际落地（commit `9f4f927`）

`scripts/smoke_body_crud.sh` 全部用方案 A：

```bash
#!/bin/bash
# 1. register（无中文，简单 POST）
curl -s -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke","email":"smoke@example.com","password":"Smoke123","nickname":"smoke"}'

# 2. login 拿 token
LOGIN=$(curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@example.com","password":"Smoke123"}')
ACCESS=$(echo "$LOGIN" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 3. POST measurement（无中文，简单）
curl -s -X POST http://127.0.0.1:8000/body-measurements \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"weight":70.5,"recorded_at":"2026-08-16T08:30:00"}'

# 4. POST goal with 中文 notes（关键：方案 A）
GOAL_BODY=$(python -c "
import json
print(json.dumps({'type': 'cut', 'notes': '3 个月减到 75kg'}, ensure_ascii=False))
")
echo "$GOAL_BODY" > /tmp/smoke_goal_body.json

curl -s -X POST http://127.0.0.1:8000/user-goals \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary @/tmp/smoke_goal_body.json

rm -f /tmp/smoke_goal_body.json
```

### 7.2 CI 集成建议

```yaml
# .github/workflows/smoke.yml
- name: Start uvicorn
  run: |
    uvicorn main:app --host 0.0.0.0 --port 8000 &
    sleep 3
- name: Run smoke
  run: bash scripts/smoke_body_crud.sh
- name: Verify responses
  run: |
    if grep -q "400" smoke_output.log; then
      echo "Smoke failed with 400"
      exit 1
    fi
```

### 7.3 多语言产品国际化必备

任何面向中文 / 日文 / 韩文 / 阿拉伯文用户的 API：

- ✅ 测试用例必须有非 ASCII 字符
- ✅ smoke 脚本必须能跑非 ASCII 数据
- ✅ CI 环境的 locale 必须设 `LANG=en_US.UTF-8` 或 `zh_CN.UTF-8`

否则：

- 开发在 macOS 上跑 OK（locale 是 UTF-8）
- CI 在 Linux docker 镜像上跑 fail（locale 是 POSIX）
- 用户在 Windows 上跑 fail（console 是 GBK）

> **面试话术**：「CI smoke 脚本统一用方案 A：Python 构造 JSON（`json.dumps(ensure_ascii=False)`）+ 写临时文件 + `curl --data-binary @file` 发送。这规避了 bash 单引号 + curl + UTF-8 字节流的全部坑。多语言产品必须做这一步——CI 环境的 locale、shell 类型、HTTP client 都可能成为字符编码的'最后一公里'。」

---

## 8. 面试话术（综合 ≥ 3 句）

> 「bash 单引号 + curl + 中文 body 失败是经典的字符编码边界问题——bash 进程内 str→bytes 是 UTF-8，但调用 native curl.exe 跨进程时（特别是 Windows Git Bash + MSYS2），字节流可能被错误地重新解释为 GBK。我用方案 A（Python `json.dumps(ensure_ascii=False)` 写临时文件 + `curl --data-binary @file`）规避——文件保持字节流原样，curl 不做转换，编码完全由 Python 控制。这是 CI smoke 国际化的必备步骤。」
>
> 「pytest + httpx 的 in-process 测试和真 HTTP smoke 是两套独立测试——前者覆盖业务逻辑（快、毫秒级），后者覆盖字节流边界（慢、秒级）。字符编码、HTTP header 细节、跨进程 IPC 这些坑，in-process 永远测不到。我项目里 30+ e2e case 跑 pytest 验证业务逻辑，但部署后必须跑 curl smoke 验证字符编码 / HTTP 协议。两层都不能省。」
>
> 「业界经验：所有面向中文 / 日文 / 韩文用户的 API，smoke 脚本必须有非 ASCII 数据验证。否则开发在 macOS 跑 OK，CI 在 Linux docker 跑 fail，用户在 Windows 跑 fail——三套环境三个 locale，三套字符编码处理。这是 W3C 国际化标准（i18n）的实际落地：测试数据要覆盖用户真实输入，不只是 ASCII happy path。」

---

## 9. 踩坑清单


| 坑                                                  | 现象                              | 解法                                          |
| -------------------------------------------------- | ------------------------------- | ------------------------------------------- |
| bash 单引号 + 中文 + curl `-d`                          | 400 parsing body                 | 方案 A：Python 写文件 + `--data-binary @file`       |
| bash 双引号 + `$variable` 被解释                          | JSON 字段值变成空                     | 单引号，或 escape                                |
| bash 单引号嵌套单引号（如 `can't`）                            | bash syntax error                | 用 `'\''` 转义，或方案 A                          |
| curl 加 `-d` 又加 `--data-binary`                       | 行为未定义                          | 二选一，不要混用                                   |
| Git Bash on Windows + native curl.exe                | UTF-8 ↔ GBK 字节流错乱              | 方案 A 完全规避（不走 bash argv 传中文）                |
| 临时文件不删                                            | /tmp 累积                        | 脚本末尾 `rm -f /tmp/xxx.json`                  |
| Content-Type 不带 charset                              | 服务端可能按默认编码解析                  | 加 `; charset=utf-8` 显式声明                  |
| CI 环境 locale 不是 UTF-8                               | 同样数据失败                         | Dockerfile 设 `ENV LANG=C.UTF-8`             |
| 用 `json.dumps(ensure_ascii=True)`（默认）               | 中文变 `\uXXXX`，body 看起来丑但功能 OK | 无所谓功能正确性，但 `ensure_ascii=False` 更易调试      |

---

## 10. 关联

- **关联决策**：
  - **D40**：SQLite in-memory for tests（让 pytest e2e 跑得快，但仍需真 HTTP smoke 兜底）
  - **D41（幻觉修订）**：本次 subagent 报告里引用了**不存在的 D41**（D40 才是正式 SQLite in-memory 决策）。本文件之前误写为"+ D41（smoke 脚本固化方案 A）"，main agent 已通过 Edit 修复为"+ 本坑独立沉淀"。决策号必须对齐 spec §11 决策表（D32-D40），不允许 subagent 自创编号。
  - **本坑**：smoke 脚本固化方案 A 的实际工程陷阱（spec §10 Task 15 输出，无对应 D 决策）
- **关联 commit**：
  - `9f4f927`：test(smoke) add curl smoke tests for 11 body+goal endpoints（含方案 A 的中文 body 测试）
- **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md` §3.10 user-goals PATCH（含 notes 字段，可能有中文）
- **关联 plan**：`docs/superpowers/plans/2026-08-16-body-crud-plan.md` Task 15（smoke + server deploy）

---

**沉淀状态**：✅ 用户于 2026-08-16 批准落盘（与 Phase 5 T16 一并 commit）
