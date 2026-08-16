# FitForge body_measurements + user_goals 部署清单（2026-08-16 周六）

> **日期**：2026-08-16（周六补周五 body CRUD 落地后的部署）
> **作者**：LHR6666（与 Claude Code 配对产出）
> **关联决策**：D26（Docker 容器化）/ D27（密码 lhr076200）/ D28-D31（JWT 已部署）/ D40（SQLite in-memory 测试，**不**影响服务器）
> **关联 commit**：22 个本会话 commit（Phase 1-5 全部）
> **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md`
> **目的**：把 11 个 body+goal 端点部署到腾讯云 CVM（114.132.83.99）的可执行 checklist
> **状态**：⏳ 部署待执行（本文当 checklist 用，**不**自动执行）

---

## 0. 部署前必备 sanity（5 分钟）

| 检查 | 命令 | 预期 |
|------|------|------|
| 本地 pytest | `pytest tests/` | 39 passed |
| 本地 smoke | `bash scripts/smoke_body_crud.sh` | 13 步全 200/201/204/404 |
| Git 状态 | `git status --short` | 21 M + 7 ??（与 phase 5 结束一致） |
| 当前 HEAD | `git rev-parse --short HEAD` | `3f2c572`（D41 fix 后） |

**本会话 commit 链（22 个）**：
```
3f2c572  docs(notes): fix D41 hallucination #2            ← D41 修复
e183b96  docs(notes): add curl unicode body escape         ← T16 文件 4
3932264  docs(notes): add batch API design pattern (D33)  ← T16 文件 3
36e3f00  docs(notes): add get_current_user refactor (D39) ← T16 文件 2
8709df4  docs(notes): add extra=forbid deep-dive (D34)    ← T16 文件 1
9f4f927  test(smoke): add curl smoke tests for 11 endpoints ← Phase 5 T15
0e49e55  docs: fix D41 -> D40 + add D40                    ← D40 + 修复
db4e682  test(routes): 7 user-goals e2e                   ← Phase 4 T14
dc98286  test(routes): 10 body-measurements e2e           ← Phase 4 T13
81d85d6  test(service): 13 service unit tests             ← Phase 4 T12
4c62212  test: conftest with 5 fixtures                   ← Phase 4 T11
c0a7ccb  docs(error-log): main.py incident                 ← Phase 3 事故
7f44b0c  docs: restore user's 2 M-marked comment lines     ← Phase 3 恢复
d9e20cd  feat(main): include body+goal routers             ← Phase 3 T10
8462a34  feat(api): 4 user-goals routes                   ← Phase 3 T9
429ac6e  feat(api): 6 body-measurements routes            ← Phase 3 T8
c96ecbb  refactor: get_current_user → core (D39)           ← Phase 2 T7
9c28db0  feat(service): 4 user_goals service              ← Phase 2 T6
3238d5d  feat(service): 6 body_measurements service       ← Phase 2 T5
718bad2  chore: rm body.py stub                           ← Phase 1 清理
701869a  feat(schemas): 4 user_goals schemas              ← Phase 1 T4
9304333  feat(schemas): 6 body_measurements schemas        ← Phase 1 T3
```

---

## 1. 部署目标 + 不做什么

### 1.1 部署目标

服务器获得与本地相同的 11 端点能力：
- 6 body_measurements 端点（POST 单 + POST /batch + GET 列表 + GET {id} + PATCH {id} + DELETE {id}）
- 4 user_goals 端点（POST + GET + GET {id} + PATCH {id}，**无 DELETE** by D36）
- `get_current_user` 已迁移到 `core/security.py`（D39）

### 1.2 不做什么

- ❌ **不**改服务器 MySQL 密码（D27 已 sync 到 `lhr076200`，本次无变更）
- ❌ **不**改服务器 `.env`（已就位，不需要新变量）
- ❌ **不**跑 `alembic upgrade head`（schema 没改 D17 已落盘）
- ❌ **不**给 fitforge 加全局权限（D40 决策：测试用 SQLite，server 仍用 MySQL `fitforge` 库）
- ❌ **不**重启 MySQL 容器

---

## 2. 部署步骤（按 2026-08-13 周三部署模式，本日复用 tar 方式）

### Step 1: 本地打包

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform"
tar -czf /tmp/fitforge_2026-08-16.tar.gz \
  --exclude='.git' --exclude='venv' --exclude='__pycache__' \
  --exclude='.env' --exclude='keys' \
  --exclude='tests/' \
  .
```

**为什么不 exclude `tests/`**：
- 2026-08-13 周三 include 了 tests/
- 本次也 include：服务器如果跑 e2e 也能用，且 config 文件覆盖一致
- 但本次部署**不**在服务器跑 pytest，仅 ensure dependency 一致

### Step 2: scp 上传

```bash
scp /tmp/fitforge_2026-08-16.tar.gz ubuntu@fitforge:/tmp/
```

### Step 3: SSH 服务器（fitforge 别名 + ed25519 私钥）

```bash
ssh fitforge
```

（D14 决策：SSH 别名 `fitforge`，私钥 `~/.ssh/id_ed25519` 在用户本地 D:/ssh/）

### Step 3.5: **从备份复制 .env**（新增，本次踩坑关键）

```bash
ls ~/fitforge.bak_<date>/.env 2>/dev/null && (
  echo "从备份复制 .env"
  cp ~/fitforge.bak_<date>/.env ~/fitforge/.env
) || echo "备份里没有 .env，需手动 cat > 创建（参考 08-13 部署记录）"
```

**事故教训**：本地打包时 `--exclude='.env'`（避免本地私密信息上传），但服务器上 .env 跟着旧 `fitforge` mv 走了。新 `fitforge` 没 .env → `core/config.py` 读不到 DATABASE_URL → SQLAlchemy 报 connection 错。**本次部署踩了 4 个坑，这条是第 1 个**。

**为什么不直接 scp .env 上服务器**：本地 .env 含本地数据库密码（fitforge @ localhost:3307），跟服务器 .env（fitforge @ localhost:3306 / 部署时手写）可能不同。**不要混用**。

### Step 4: 服务器备份旧代码

```bash
# 服务器端
ls -la ~/fitforge  # 确认上一版
mv ~/fitforge ~/fitforge.bak_2026-08-16  # 备份（D19 决策"备份即保险"）
```

### Step 5: 解压新代码

```bash
mkdir -p ~/fitforge
tar -xzf /tmp/fitforge_2026-08-16.tar.gz -C ~/fitforge/
rm /tmp/fitforge_2026-08-16.tar.gz
cd ~/fitforge
```

### Step 5.5: **生成 RSA 密钥对**（若服务器上没 keys/，**新增**）

```bash
cd ~/fitforge
ls keys/private.pem 2>/dev/null || (
  echo "keys/ 不存在，生成新 RSA 密钥对"
  mkdir -p keys
  openssl genrsa -out keys/private.pem 2048 2>&1 | tail -2
  openssl rsa -in keys/private.pem -pubout -out keys/public.pem 2>&1 | tail -2
  chmod 600 keys/private.pem
  chmod 644 keys/public.pem
)
ls -la keys/
```

**事故教训**：本次部署服务器上**根本没有 keys/** —— `core/security.py._load_keys()` 在 import 时找不到 `keys/private.pem` → uvicorn 启动失败。08-13 部署时没建过 keys/（register 端点不需要 JWT），本次 D39 迁移后所有端点都需要 JWT。

**若服务器上已有 keys/**：跳过此 step（说明之前部署过 login 相关功能）。

### Step 6: venv 重新 install（如有依赖变化先 diff）

```bash
# 看是否真有新依赖
diff <(grep -oP '^[a-zA-Z0-9_-]+' requirements.txt | sort) \
     <(pip list 2>/dev/null | grep -oP '^[a-zA-Z0-9_-]+' | sort)
# 如果有缺，跑：
pip install -r requirements.txt
```

**本次实际**：
- 无新增 Python 包（Schema/Service/Route/Test 全用既有：fastapi / pydantic / sqlalchemy / passlib）
- aiosqlite **仅测试用**，已通过 conftest.py 的 `os.environ.setdefault` 隔离（D40 决策）
- 服务器**不**装 aiosqlite

### Step 6.5: 验证 requirements.txt 完整（防漏包踩坑，**新增**）

```bash
cd ~/fitforge
grep -i 'jwt\|pyjwt\|cryptography' requirements.txt
# 必须看到 PyJWT[crypto] 一行
```

**若没有 PyJWT**：本地 requirements.txt 漏了核心依赖（D5 决策）。**手动装上**：
```bash
pip install 'PyJWT[crypto]==2.10.1'
# 之后手动更新本地 requirements.txt 加这行
```

**事故教训**：本次部署新 venv 缺 PyJWT 导致 uvicorn `ModuleNotFoundError`。08-13 部署时 PyJWT 装在 `~/.local/`（--user 残留），新 venv 是干净的，所以崩。**详细见** `error_logs/2026-08-16-server-deploy-4-issues.md`。

### Step 7: alembic check + upgrade（**必须跑 upgrade，不要假设**）

```bash
source venv/bin/activate
alembic current    # 看当前 HEAD
alembic history    # 看历史 migration 列表
alembic upgrade head   # **必跑**：即便觉得没改也要跑（防 schema 漂移）
```

**预期**：
- `alembic current` 显示当前 HEAD revision
- `alembic upgrade head` 若有 pending migration 会跑（如 `Running upgrade -> <new>, add refresh_tokens table`）
- 若 `alembic upgrade head` 报 "no new migrations"，说明已对齐，OK

**事故教训**：本次部署时我以为"schema 没改不需要 alembic upgrade"——**错了**。08-14 周三加了 `refresh_tokens` 表（D29 决策），08-13 部署没有这张表。本次部署 `/auth/login` 调用 `INSERT INTO refresh_tokens` 报 `Table doesn't exist` → smoke 全 401 失败。**永远跑 `alembic upgrade head`**——这是数据库 schema 漂移的最大保险。

### Step 8: restart uvicorn

```bash
# 找现有进程
ps aux | grep uvicorn | grep -v grep
# 杀掉旧进程（保留 env / 不要 SIGHUP）
pkill -f "uvicorn main:app"
sleep 2
# 后台起新进程
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ~/fitforge/uvicorn.log 2>&1 &
sleep 3
# health check
curl -s http://127.0.0.1:8000/health
```

**预期**：`{"status":"healthy"}`

### Step 9: 服务器 smoke 验证（11 端点全跑）

```bash
# 服务器端
bash scripts/smoke_body_crud.sh
```

**预期**：
- 13 个 curl 步骤全 200/201/204/404
- 无 5xx 错误
- D38 防枚举验证：DELETE 后 GET → 404（不是 403）

### Step 10: uvicorn.log 检查

```bash
tail -50 ~/fitforge/uvicorn.log
```

**预期**：
- 无 traceback
- 无 `ImportError`（get_current_user 迁移后是否所有路由能正常 import）
- 无 `IntegrityError`（on delete cascade 健在）

---

## 3. 部署回滚 plan（5 步内回到上一版）

如果服务器 smoke 失败：

```bash
ssh fitforge
pkill -f "uvicorn main:app"
rm -rf ~/fitforge
mv ~/fitforge.bak_2026-08-16 ~/fitforge
cd ~/fitforge
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ~/fitforge/uvicorn.log 2>&1 &
```

预期：5 分钟内回到 08-13 周三部署的版本（仅含 5 个 auth 端点）。

---

## 4. 部署后 smoke 输出贴在 tech_notes 里

部署成功后，把服务器 smoke 输出（13 步全 200/201 的截图/复制）追加到本文档「5. 部署记录」section，方便后续 review。

---

## 5. 部署记录

> **留空，部署完成后填**

- 部署时间：______
- 服务器 fitforge 数据库有无数据：______
- pytest 服务器跑（可选）：______
- curl smoke 全 200/201：______
- uvicorn.log 检查：______

---

## 6. 防止重蹈 main.py 事故

**部署前再确认 4 件事**（按 `error_logs/2026-08-16-main-py-user-mod-lost.md` 教训）：

| 检查 | 命令 | 预期 |
|------|------|------|
| 本地 M 文件未损 | `git status --short \| wc -l` | 21 行（与部署前一致） |
| 服务器 .env 未动 | `cat ~/fitforge/.env \| grep DATABASE_URL` | 应有 `fitforge` 库 + `lhr076200` |
| 服务器 alembic current 与本地一致 | `alembic current` | 同一 revision |
| 服务器 health 200 | `curl http://127.0.0.1:8000/health` | `{"status":"healthy"}` |

---

## 7. 关联面试话术

> "我部署用 tar 打包 + scp + 服务器解压 + uvicorn restart，**不是** `git pull`（避免 ① 服务器 inotify 触发频繁 reload；② 部署失败时方便回滚到上一版）。每次部署备份 `mv fitforge fitforge.bak_<date>` 是'5 分钟回滚'策略，比 K8s 简单但够 MVP。**部署前必跑本地 pytest 39 + 本地 smoke 13 步**——不把本地未验证的代码推到服务器。"
