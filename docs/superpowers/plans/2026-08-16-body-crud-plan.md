# body_measurements + user_goals CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 11 个端点（6 measurements + 5 goals，goals 无 DELETE），覆盖 MVP 业务闭环（数据录入 + 目标管理）。

**Architecture:** 严格分层（api/ 路由只做 HTTP 适配 + ORM→DTO 转换；services/ 接 Pydantic schema 出 ORM 抛业务异常；models/ ORM 模型；schemas/ 入参出参隔离；core/ 异常 + 鉴权中间件）。复用周四 /auth/login 的 get_current_user 中间件（D39：迁移到 core/security.py 避免循环 import）。复用 Q1-Q6 决策（重型 service / 业务异常 / Depends / 2 schema / 不引依赖）。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 async / MySQL 8.0 / Pydantic v2 / PyJWT (RS256) / pytest + httpx AsyncClient

**Spec:** `docs/superpowers/specs/2026-08-16-body-crud-design.md`（commit `2ab935e`，1003 行）

---

## Global Constraints

> 这些约束在 spec §4-§9 详细展开，**实施每个 task 前必读**

- **严格分层**：service 接 schema → 出 ORM → 抛业务异常；路由层只做 ORM → DTO 转换 + HTTP 状态
- **业务异常体系**：所有业务异常继承 `FitForgeException`，由 `api/exception_handlers.py` 映射 HTTP code（404 / 403 / 400）
- **鉴权粒度**：每个端点必须 `Depends(get_current_user)`；service 接 `current_user: User` 参数做权限校验
- **跨用户访问一律返回 404**：防 ID 枚举攻击（spec §6.1 决策）
- **Pydantic v2**：`ConfigDict(from_attributes=True)` + `extra="forbid"`（patch schema 拒额外字段）
- **时间戳一律 UTC**：`datetime.now(timezone.utc)`（D17-f）
- **不引新依赖**：SQLAlchemy 原生 limit/offset；pytest + httpx AsyncClient 已装
- **service 层不该依赖 FastAPI**（Q1 决策）—— 接 `current_user: User` ORM 对象而非 token str
- **测试隔离**：每个测试独立 user 避免 cross-contamination（spec §8.3）
- **commit 规范**：Conventional Commits（feat/fix/docs/refactor/test/chore）
- **CLAUDE.md 第六条自检**：每个 task 完成后，Claude **必须主动问** "需要我立刻记录这次的内容吗？"

---

## 风险与坑预警（实施前必读）

> 来源：周四 /auth/login 真实踩坑 + 本 spec 设计点的隐患

### W1. datetime naive vs aware（D17-f + 周四踩坑）

- **问题**：MySQL DateTime 是 naive（无时区），`datetime.now(UTC)` 是 aware（有时区）
- **踩坑**：service 里 `db_token.expires_at < datetime.utcnow()` 时，若 stored 是 UTC naive，要用 `datetime.utcnow()`（naive）才能比较；若混用会报 "can't compare offset-naive and offset-aware datetimes"
- **对策**：**本次统一用 `datetime.utcnow()`（naive）** 与 DB stored value 比较（D17-f）
- **Pydantic**：用 `datetime` 类型（naive），FastAPI 解析 ISO 8601 字符串后是 naive

### W2. SQLAlchemy `db.get()` vs `db.execute(select())`

- **问题**：`db.get(BodyMeasurement, measurement_id)` 简单按 PK，但自动 404 不会抛，需要手动 if None
- **对策**：service 层必须显式 `if obj is None: raise NotFoundError`，**不允许**裸 `db.get` 后直接用对象
- **关联 task**：5、6

### W3. PATCH schema 用 `extra="forbid"`（Q3 决策）

- **问题**：前端误传 `{"weight": 999}` 想改 weight，但 Pydantic 默认忽略额外字段 → 静默接受
- **对策**：`BodyMeasurementPatch` / `UserGoalUpdate` 必须 `model_config = ConfigDict(extra="forbid")`
- **关联 task**：3、4

### W4. SQLAlchemy `exclude_unset` for partial PATCH（spec §5.1 patch_measurement）

- **问题**：`update.model_dump()` 会把所有字段都含（None 也是值），可能误清空字段
- **对策**：用 `update.model_dump(exclude_unset=True)` —— 仅取 schema 里显式传了的字段
- **关联 task**：5

### W5. 批量端点的"整体事务"语义（Q2 决策）

- **问题**：单条失败时 `db.flush()` 会抛错，但默认 SQLAlchemy 不会自动回滚
- **对策**：service `create_measurements_batch` 用 `add_all + flush + commit`；若 flush 抛错，**async route 函数不显式回滚**（依赖 dependency `get_db` 的 finally 关闭 session 时回滚；本期先简单依赖全局 rollback）
- **关联 task**：5

### W6. `get_current_user` 抽到 core/security.py 时小心循环 import（spec §7.4）

- **问题**：`api/body.py` import `from core.security import get_current_user` 同时 `core/security.py` 不应 import api；
- **对策**：`get_current_user` 函数体保持不变，**只是位置迁移**；原来的 `api/auth.py` 移除该函数定义
- **关联 task**：7

### W7. 测试环境数据库

- **问题**：测试不能直接用本地 Docker MySQL（污染数据）
- **对策**：用 `tests/conftest.py` 提供 fixture，每次测试前 `Base.metadata.create_all` + 测试结束 drop；或者用 SQLite in-memory（如果 asyncmy/SQLAlchemy 完全兼容）
- **关联 task**：11
- **本次决策**：先用 MySQL（保持与生产一致），fixture 创临时 schema 用 `engine.begin()` + `await conn.run_sync(Base.metadata.drop_all)`

### W8. 鉴权测试的 token 获取（spec §8）

- **问题**：每个 e2e 测试需要先 register + login 拿 token，重复代码
- **对策**：`tests/conftest.py` 提供 `auth_headers` fixture：内部 register + login → 返回 `{"Authorization": f"Bearer {access}"}`
- **关联 task**：11

---

## File Structure（按本计划修改/新增的文件汇总）

```
FitForge/
├── core/
│   ├── exceptions.py          # 改：+3 子类（MeasurementNotFoundError / GoalNotFoundError / UnauthorizedAccessError）
│   └── security.py            # 改：迁移 get_current_user 进来（D39）
├── api/
│   ├── auth.py                # 改：移除 get_current_user 重复定义
│   ├── exception_handlers.py  # 改：+3 handler
│   ├── body.py                # 新：6 路由
│   └── goal.py                # 新：4 路由
├── models/                    # 不改（D17 schema 已定）
├── schemas/
│   ├── measurement.py         # 新：6 schema
│   └── goal.py                # 新：4 schema
├── services/
│   ├── measurement_service.py # 新：6 函数
│   └── goal_service.py        # 新：4 函数
├── main.py                    # 改：include 2 个新 router
└── tests/
    ├── conftest.py            # 新：fixture（test_db, auth_headers, sample_user 等）
    ├── test_measurement_service.py  # 新：service 单元
    ├── test_goal_service.py          # 新：service 单元
    ├── test_body_routes.py           # 新：route e2e
    └── test_goal_routes.py           # 新：route e2e
```

**总计**：8 个新文件 + 5 个修改文件 = 13 个文件

---

## 任务拆分：16 task × 6 大块

### 大块 1：异常 + handler（Task 1-2）

### Task 1: 在 `core/exceptions.py` 新增 3 个业务异常子类

**Files:**
- Modify: `core/exceptions.py`（在末尾追加 3 个子类，不改已有 4 个）

**Interfaces:**
- Consumes: 已有 `FitForgeException` 基类
- Produces:
  - `class MeasurementNotFoundError(FitForgeException)` → 路由 → HTTP 404
  - `class GoalNotFoundError(FitForgeException)` → 路由 → HTTP 404
  - `class UnauthorizedAccessError(FitForgeException)` → 路由 → HTTP 403（spec §6 防御用）

依赖：无（前置 task）

**关联 spec**：§6.1 + §3 错误码

**关联决策**：D32（隐含）

---

- [ ] **Step 1: 阅读 spec §6.1 三个异常类**

打开 `docs/superpowers/specs/2026-08-16-body-crud-design.md` 第 6.1 节，确认 3 个异常的类名、文档字符串、用途。

- [ ] **Step 2: 在 core/exceptions.py 末尾追加**

按 spec §6.1 完整定义追加（class 体保持 `pass`）。

- [ ] **Step 3: 跑回归测试确认未破坏现有 4 个异常**

```bash
pytest tests/ -v --collect-only 2>&1 | grep -i error
```

预期：现有测试无错误（仅 collect-only 输出 5 个异常类的 import 列表）。

- [ ] **Step 4: commit**

```bash
git add core/exceptions.py
git commit -m "feat(exceptions): add MeasurementNotFound/GoalNotFound/UnauthorizedAccess errors"
```

**预估 commit 数**：1

---

### Task 2: 在 `api/exception_handlers.py` 注册 3 个新 handler

**Files:**
- Modify: `api/exception_handlers.py`（在已有 5 个 handler 之后追加）

**Interfaces:**
- Consumes: 已在 Task 1 添加的 3 个异常类
- Produces:
  - `MeasurementNotFoundError` → 404 JSON `{detail: ...}`
  - `GoalNotFoundError` → 404 JSON `{detail: ...}`
  - `UnauthorizedAccessError` → 403 JSON `{detail: ...}`

依赖：Task 1

**关联 spec**：§6.2

---

- [ ] **Step 1: 阅读 spec §6.2 三个 handler 定义**

- [ ] **Step 2: 在 api/exception_handlers.py 末尾追加 3 个 handler**

按 spec §6.2 完整定义追加。注意 `@app.exception_handler(...)` 装饰器内部函数参数类型要正确（参考已有 `UsernameExistsError` handler）。

- [ ] **Step 3: 快速 sanity check（启动应用不抛错）**

```bash
uvicorn main:app --reload --log-level warning &
sleep 3
curl -s http://127.0.0.1:8000/openapi.json | python -c "import sys, json; d=json.load(sys.stdin); print('schema OK, paths=', len(d['paths']))"
kill %1 2>/dev/null
```

预期：输出 `schema OK, paths=N`（N 应 ≥ 现有 /auth/* 的端点数）

- [ ] **Step 4: 完成自检 + 询问**

按 CLAUDE.md 第六条自检清单 review 这次的改动：
- □ D 决策：追加 D32 到 project_progress.md
- □ 报错：本次没遇到
- □ 知识点：暂无新增（非琐碎）
- □ TODO 列表：勾选对应项

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 5: commit**

```bash
git add api/exception_handlers.py
git commit -m "feat(api): add 3 exception handlers (MeasurementNotFound/GoalNotFound/UnauthorizedAccess)"
```

**预估 commit 数**：1

---

### 大块 2：Schemas（Task 3-4）

### Task 3: 创建 `schemas/measurement.py`（6 schema）

**Files:**
- Create: `schemas/measurement.py`

**Interfaces:**
- Produces:
  - `class BodyMeasurementCreate(BaseModel)` — POST 单条入参（13 字段：weight + body_fat + 6 围度 + 3 RM + recorded_at + notes）
  - `class BodyMeasurementBatchCreate(BaseModel)` — POST /batch 入参（items: list, min=1 max=50）
  - `class BodyMeasurementPatch(BaseModel)` — PATCH 入参（仅 notes + recorded_at + `extra="forbid"`）
  - `class BodyMeasurementRead(BaseModel)` — 出参（17 字段含 id/user_id/全部 timestamp + from_attributes）
  - `class BodyMeasurementBatchRead(BaseModel)` — POST /batch 出参（count + items）
  - `class BodyMeasurementListQuery(BaseModel)` — GET query 参数（from_/to/limit/offset）

依赖：Task 1-2（仅保证 schema 编译通过，无逻辑依赖）

**关联 spec**：§4.1 完整伪代码

**关联决策**：D33（batch 端点）+ D34（PATCH 仅 2 字段）+ D37（query limit <= 100）

**约束**：
- Pydantic v2：`from pydantic import BaseModel, ConfigDict, Field`
- `BodyMeasurementPatch` 必须 `model_config = ConfigDict(extra="forbid")`（W3）
- 数值范围参考 spec §4.1（如 weight ge=20 le=300、body_fat ge=3 le=60）

---

- [ ] **Step 1: 阅读 spec §4.1 完整定义**

打开 `docs/superpowers/specs/2026-08-16-body-crud-design.md` 第 4.1 节，按 spec 完整复制伪代码到 `schemas/measurement.py`。

- [ ] **Step 2: 跑 schema 编译测试**

```bash
python -c "from schemas.measurement import BodyMeasurementCreate, BodyMeasurementBatchCreate, BodyMeasurementPatch, BodyMeasurementRead, BodyMeasurementBatchRead, BodyMeasurementListQuery; print('OK')"
```

预期：`OK`

- [ ] **Step 3: 跑 Pydantic 字段验证手测**

```bash
python -c "
from schemas.measurement import BodyMeasurementCreate, BodyMeasurementPatch
from datetime import datetime
from pydantic import ValidationError
# weight < 20 应失败
try:
    BodyMeasurementCreate(weight=10, recorded_at=datetime.now())
except ValidationError as e:
    print('weight < 20 rejected: OK')
# PATCH 多余字段应失败
try:
    BodyMeasurementPatch(weight=999, notes='oops')
except ValidationError as e:
    print('extra field rejected: OK')
"
```

预期：两个 `OK` 输出。

- [ ] **Step 4: 完成自检 + 询问**

按 CLAUDE.md 第六条自检（关注 Q3 PATCH 限制、Q2 batch 大小限制）。

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 5: commit**

```bash
git add schemas/measurement.py
git commit -m "feat(schemas): add 6 body_measurements schemas (Create/Batch/Create/Patch/Read/BatchRead/ListQuery)"
```

**预估 commit 数**：1

---

### Task 4: 创建 `schemas/goal.py`（4 schema）

**Files:**
- Create: `schemas/goal.py`

**Interfaces:**
- Produces:
  - `class UserGoalCreate(BaseModel)` — POST 入参（type + target_value + deadline + notes；status 默认 active）
  - `class UserGoalUpdate(BaseModel)` — PATCH 入参（5 字段均可选 + `extra="forbid"`）
  - `class UserGoalRead(BaseModel)` — 出参（id/user_id/type/target_value/status/deadline/notes/time）
  - `class UserGoalListQuery(BaseModel)` — GET query（status + limit + offset）

依赖：Task 1-2

**关联 spec**：§4.2 完整伪代码

**关联决策**：D35（PATCH 5 字段）+ D37（query）

**Literal 类型**：

```python
GOAL_TYPE = Literal["cut", "bulk", "maintain", "strength"]
GOAL_STATUS = Literal["active", "completed", "abandoned"]
```

---

- [ ] **Step 1: 阅读 spec §4.2 完整定义**

- [ ] **Step 2: 在 schemas/goal.py 写入 4 schema + 2 Literal**

按 spec §4.2 完整复制。注意 `UserGoalRead.type` / `.status` 是 `str`（不是 Literal），因为从 ORM Enum 字段读出的是 str。

- [ ] **Step 3: 跑 schema 编译测试**

```bash
python -c "from schemas.goal import UserGoalCreate, UserGoalUpdate, UserGoalRead, UserGoalListQuery, GOAL_TYPE, GOAL_STATUS; print('OK')"
```

预期：`OK`

- [ ] **Step 4: 跑 Pydantic 字段验证手测**

```bash
python -c "
from schemas.goal import UserGoalCreate, UserGoalUpdate
from pydantic import ValidationError
# type 不在枚举内应失败
try:
    UserGoalCreate(type='invalid_type')
except ValidationError as e:
    print('invalid type rejected: OK')
# PATCH 多余字段应失败
try:
    UserGoalUpdate(user_id=999)
except ValidationError as e:
    print('extra user_id rejected: OK')
"
```

预期：两个 `OK` 输出。

- [ ] **Step 5: 完成自检 + 询问**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 6: commit**

```bash
git add schemas/goal.py
git commit -m "feat(schemas): add 4 user_goals schemas (Create/Update/Read/ListQuery) + 2 Literal types"
```

**预估 commit 数**：1

---

### 大块 3：Service 层（Task 5-7）

### Task 5: 创建 `services/measurement_service.py`（6 函数）

**Files:**
- Create: `services/measurement_service.py`

**Interfaces:**
- Produces:
  - `create_measurement(db, current_user, payload) -> BodyMeasurement` （单条）
  - `create_measurements_batch(db, current_user, payload) -> list[BodyMeasurement]` （批量整体事务）
  - `list_measurements(db, current_user, *, date_from=None, date_to=None, limit=20, offset=0) -> list[BodyMeasurement]`
  - `get_measurement(db, current_user, measurement_id) -> BodyMeasurement` （内部权限校验）
  - `patch_measurement(db, current_user, measurement_id, patch) -> BodyMeasurement` （仅 notes + recorded_at）
  - `delete_measurement(db, current_user, measurement_id) -> None` （硬删）

依赖：Task 1（异常）+ Task 3（schema）

**关联 spec**：§5.1 完整伪代码

**关联决策**：D33 + D34 + D36 + D37

**风险点**：W2（`db.get` 显式 None check）+ W4（`exclude_unset`）+ W5（batch 整体事务）

---

- [ ] **Step 1: 阅读 spec §5.1 完整定义 + W2/W4/W5 预警**

- [ ] **Step 2: 在 services/measurement_service.py 写入 6 个函数**

按 spec §5.1 完整复制伪代码。**关键点**：
- `get_measurement` 内必须显式 `if obj is None or obj.user_id != current_user.id: raise MeasurementNotFoundError(...)`（spec §5.1 注释：故意 NotFound 防 ID 枚举）
- `patch_measurement` 用 `patch.model_dump(exclude_unset=True)`（W4）
- `create_measurements_batch` 用 `db.add_all + flush + commit`（W5）

- [ ] **Step 3: 跑 service 编译测试**

```bash
python -c "from services.measurement_service import create_measurement, create_measurements_batch, list_measurements, get_measurement, patch_measurement, delete_measurement; print('OK')"
```

预期：`OK`

- [ ] **Step 4: 完成自检 + 询问（关注 W2/W4/W5 三处易错点）**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 5: commit**

```bash
git add services/measurement_service.py
git commit -m "feat(service): add 6 body_measurements service functions (create/batch/list/get/patch/delete)"
```

**预估 commit 数**：1

---

### Task 6: 创建 `services/goal_service.py`（4 函数）

**Files:**
- Create: `services/goal_service.py`

**Interfaces:**
- Produces:
  - `create_goal(db, current_user, payload) -> UserGoal`（status 默认 "active"）
  - `list_goals(db, current_user, *, status=None, limit=20, offset=0) -> list[UserGoal]`
  - `get_goal(db, current_user, goal_id) -> UserGoal`（404 防枚举）
  - `update_goal(db, current_user, goal_id, update) -> UserGoal`（5 字段 PATCH）

依赖：Task 1（异常）+ Task 4（schema）

**关联 spec**：§5.2

**关联决策**：D35 + D37 + D36（无 DELETE）+ D38（404 防枚举）

---

- [ ] **Step 1: 阅读 spec §5.2**

- [ ] **Step 2: 写入 services/goal_service.py 4 函数**

按 spec §5.2 完整复制伪代码。**关键点**：
- `create_goal` 必须显式 `status="active"`（默认填，spec §5.2 注释）
- `update_goal` 用 `update.model_dump(exclude_unset=True)`（W4）
- 不写 `delete_goal`（Q5）

- [ ] **Step 3: 跑 service 编译测试**

```bash
python -c "from services.goal_service import create_goal, list_goals, get_goal, update_goal; print('OK')"
```

预期：`OK`

- [ ] **Step 4: 完成自检 + 询问**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 5: commit**

```bash
git add services/goal_service.py
git commit -m "feat(service): add 4 user_goals service functions (create/list/get/update, no delete by design)"
```

**预估 commit 数**：1

---

### Task 7: 把 `get_current_user` 抽到 `core/security.py`

**Files:**
- Modify: `core/security.py`（末尾追加 `get_current_user` + _bearer_scheme）
- Modify: `api/auth.py`（移除 `get_current_user` 函数定义和 `_bearer_scheme`）
- Modify: `api/auth.py`（移除 `from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer` + `from sqlalchemy.ext.asyncio import AsyncSession` 等 unused import）

**Interfaces:**
- Produces:
  - `core/security.py:get_current_user(credentials, db) -> User`（位置迁移，函数体不变）

依赖：无（纯粹位置迁移）

**关联 spec**：§7.4

**关联决策**：D39

**风险**：W6（循环 import）

---

- [ ] **Step 1: 阅读 api/auth.py 当前 get_current_user 实现**

打开 `api/auth.py` 第 116-139 行（按周四进度）。函数体需 100% 保留，**只移动位置**。

- [ ] **Step 2: 在 core/security.py 末尾追加 get_current_user**

保留完全相同的函数体（包括 `_bearer_scheme = HTTPBearer(auto_error=False)`）。需要的 import：
- `from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer`
- `from sqlalchemy.ext.asyncio import AsyncSession`
- `from core.db import get_db`
- `from core.exceptions import InvalidTokenError`
- `from models.user import User`
- 函数体中已有的 `from core.security import decode_access_token` 因已在同文件内，改成直接调用 `decode_access_token`

- [ ] **Step 3: 在 api/auth.py 删除原 get_current_user 定义**

删除 `_bearer_scheme` 变量定义 + `get_current_user` 整个函数 + 不再使用的 import。

- [ ] **Step 4: 跑应用启动 sanity**

```bash
python -c "from api.auth import router; from core.security import get_current_user; print('OK')"
```

预期：`OK`

- [ ] **Step 5: 完成自检 + 询问（D39 决策点必记录）**

按 CLAUDE.md 第六条自检：
- **□ D 决策：D39 必追加 project_progress.md**（决策记录）
- □ 报错：暂无
- □ 知识点：W6 循环 import（可做 5 分钟口述）
- □ TODO 勾选

**主动问用户**："需要我立刻记录这次的内容吗？"（**重点：D39 决策必须落盘**）

- [ ] **Step 6: commit**

```bash
git add core/security.py api/auth.py
git commit -m "refactor: move get_current_user from api/auth.py to core/security.py (D39)"
```

**预估 commit 数**：1

---

### 大块 4：路由层（Task 8-10）

### Task 8: 创建 `api/body.py`（6 路由）

**Files:**
- Create: `api/body.py`

**Interfaces:**
- Produces:
  - `POST /body-measurements` → 201 BodyMeasurementRead（单条）
  - `POST /body-measurements/batch` → 201 BodyMeasurementBatchRead（批量）
  - `GET /body-measurements` → 200 List[BodyMeasurementRead]（query: from/to/limit/offset）
  - `GET /body-measurements/{measurement_id}` → 200 BodyMeasurementRead
  - `PATCH /body-measurements/{measurement_id}` → 200 BodyMeasurementRead
  - `DELETE /body-measurements/{measurement_id}` → 204 No Content

依赖：Task 3（schema）+ Task 5（service）+ Task 7（get_current_user 已移到 core）

**关联 spec**：§3.1-§3.6 + §7.1

**路由模式**：

```python
router = APIRouter(prefix="/body-measurements", tags=["body-measurements"])

# 模式 1：ORM 对象 → DTO
obj = await service.create_measurement(db, current_user, payload)
return BodyMeasurementRead.model_validate(obj)

# 模式 2：list ORM → list DTO
return [BodyMeasurementRead.model_validate(o) for o in objs]
```

---

- [ ] **Step 1: 阅读 spec §7.1 完整路由代码**

- [ ] **Step 2: 在 api/body.py 写入 6 个路由**

按 spec §7.1 完整复制。**关键点**：
- `Depends(get_current_user)` 从 `core.security`（Task 7 迁移后）
- `Depends(get_db)` 从 `core.db`
- Query 参数用 FastAPI `Query()` 验证：`limit: int = Query(default=20, ge=1, le=100)`（D37）
- `from` 是 Python 关键字，FastAPI Query 用 `alias="from"`（参考 spec §7.1 get_measurements）

- [ ] **Step 3: 跑应用启动**

```bash
uvicorn main:app --reload --log-level warning &
sleep 3
curl -s http://127.0.0.1:8000/openapi.json | python -c "import sys, json; d=json.load(sys.stdin); paths=[p for p in d['paths'] if 'body-measurements' in p]; print('body paths:', len(paths)); [print(p) for p in sorted(paths)]"
kill %1 2>/dev/null
```

预期：6 条 path 输出（/body-measurements POST/GET, /body-measurements/batch POST, /body-measurements/{id} GET/PATCH/DELETE）

- [ ] **Step 4: 完成自检 + 询问**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 5: commit**

```bash
git add api/body.py
git commit -m "feat(api): add 6 body-measurements routes (POST/POST batch/GET/GET id/PATCH/DELETE)"
```

**预估 commit 数**：1

---

### Task 9: 创建 `api/goal.py`（4 路由）

**Files:**
- Create: `api/goal.py`

**Interfaces:**
- Produces:
  - `POST /user-goals` → 201 UserGoalRead
  - `GET /user-goals?status=active` → 200 List[UserGoalRead]
  - `GET /user-goals/{goal_id}` → 200 UserGoalRead
  - `PATCH /user-goals/{goal_id}` → 200 UserGoalRead

依赖：Task 4 + Task 6 + Task 7

**关联 spec**：§3.7-§3.10 + §7.2

**不实现**：DELETE（Q5 决策）

---

- [ ] **Step 1: 阅读 spec §7.2 完整代码**

- [ ] **Step 2: 在 api/goal.py 写入 4 路由**

按 spec §7.2 完整复制。**关键点**：
- Query status 参数用 FastAPI `Query()` + `Literal["active","completed","abandoned"] | None`
- 不写 `@router.delete("/{goal_id}")` 路由（Q5）

- [ ] **Step 3: 跑路由 sanity**

```bash
uvicorn main:app --reload --log-level warning &
sleep 3
curl -s http://127.0.0.1:8000/openapi.json | python -c "import sys, json; d=json.load(sys.stdin); paths=[p for p in d['paths'] if 'user-goals' in p]; print('goal paths:', len(paths)); [print(p) for p in sorted(paths)]"
kill %1 2>/dev/null
```

预期：4 条 path（POST/GET/GET{id}/PATCH{id}，**没有 DELETE**）

- [ ] **Step 4: 完成自检 + 询问（Q5 无 DELETE 决策点必复习）**

**主动问用户**："需要我立刻记录这次的内容吗？"（提醒：D36 决策涵盖 measurements 硬删 + goals 不删）

- [ ] **Step 5: commit**

```bash
git add api/goal.py
git commit -m "feat(api): add 4 user-goals routes (POST/GET/GET id/PATCH, no DELETE by design)"
```

**预估 commit 数**：1

---

### Task 10: 在 `main.py` 注册两个新 router

**Files:**
- Modify: `main.py`（在已有 `app.include_router(auth_router)` 之后追加 2 行）

依赖：Task 8 + Task 9

---

- [ ] **Step 1: 阅读 main.py 当前 router 注册**

- [ ] **Step 2: 在 main.py 末尾追加 2 行**

```python
from api.body import router as body_router
from api.goal import router as goal_router

# 已有 include_router(...) 之后追加
app.include_router(body_router)
app.include_router(goal_router)
```

- [ ] **Step 3: 启动应用 + 跑 /docs 看分组**

```bash
uvicorn main:app --log-level warning &
sleep 3
# 验证 /docs 页面有 body-measurements + user-goals 两个 tag
curl -s http://127.0.0.1:8000/openapi.json | python -c "
import sys, json
d = json.load(sys.stdin)
tags = set()
for path, methods in d['paths'].items():
    for method, op in methods.items():
        if 'tags' in op:
            tags.update(op['tags'])
print('tags:', sorted(tags))
print('total paths:', len(d['paths']))
"
kill %1 2>/dev/null
```

预期：tags 含 `body-measurements` 和 `user-goals`；total paths 应等于 auth(5) + body(6) + goal(4) = 15

- [ ] **Step 4: 完成自检 + 询问**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 5: commit**

```bash
git add main.py
git commit -m "feat(api): include body-measurements + user-goals routers in FastAPI app"
```

**预估 commit 数**：1

---

### 大块 5：测试（Task 11-14）

### Task 11: 创建 `tests/conftest.py`（fixture）

**Files:**
- Create: `tests/conftest.py`

**Interfaces:**
- Produces fixtures（pytest fixture）：
  - `event_loop`（asyncio 模式）
  - `engine`（async SQLAlchemy engine，连接到 MySQL test DB）
  - `db_session`（每个测试独立 session，teardown rollback）
  - `sample_user`（创建并返回测试用 User ORM）
  - `auth_headers`（register + login → 返回 `{"Authorization": "Bearer xxx"}`）

依赖：无（fixture 是测试基底）

**关联 spec**：§8.3 测试隔离

**风险点**：W7（测试环境数据库）+ W8（auth_headers fixture）

**测试 DB**：
- DATABASE_URL 走 `.env.test` 或 `conftest.py` 顶部 `os.environ` 设置
- 建议：新 schema 名 `fitforge_test`（不污染 `fitforge`）
- 表创建：`engine.begin() + await conn.run_sync(Base.metadata.create_all)`
- 表清理：fixture finalizer `await conn.run_sync(Base.metadata.drop_all)` 或每个测试 transaction rollback

---

- [ ] **Step 1: 创建 .env.test 配置文件**

在项目根目录创建 `.env.test`：
```env
DATABASE_URL=mysql+asyncmy://fitforge:lhr076200@127.0.0.1:3307/fitforge_test
SYNC_DATABASE_URL=mysql+pymysql://fitforge:lhr076200@127.0.0.1:3307/fitforge_test
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
```

`.env.test` 加入 `.gitignore`。

- [ ] **Step 2: 创建 test 数据库**

```bash
mysql -h 127.0.0.1 -P 3307 -u fitforge -plhr076200 -e "CREATE DATABASE IF NOT EXISTS fitforge_test CHARACTER SET utf8mb4;"
```

- [ ] **Step 3: 在 tests/conftest.py 写入 fixtures**

完整内容：

```python
import asyncio
import os

os.environ.setdefault("DATABASE_URL", "mysql+asyncmy://fitforge:lhr076200@127.0.0.1:3307/fitforge_test")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from core.db import Base, get_db
from main import app
from services.auth_service import register, login  # 第 6 步会用到
from models.user import User  # noqa


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(settings.DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session
        # 每个测试结束 rollback（如果还没 commit）


@pytest_asyncio.fixture
async def sample_user(db_session):
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="not-a-real-hash",  # login 不测这个 fixture
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def auth_headers(db_session):
    """注册并登录一个新用户，返回 Authorization headers"""
    from schemas.user import UserCreate, LoginRequest
    from core.security import hash_password

    user = User(
        username="alice_test",
        email="alice_test@example.com",
        password_hash=hash_password("Password123"),
    )
    db_session.add(user)
    await db_session.commit()

    login_req = LoginRequest(email="alice_test@example.com", password="Password123")
    access, refresh, expires = await login(db_session, login_req.email, login_req.password)
    return {"Authorization": f"Bearer {access}"}


@pytest_asyncio.fixture
async def client(engine):
    """httpx AsyncClient 内嵌 FastAPI app"""
    from core.db import get_db

    async def _override_get_db():
        async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 4: 跑 fixture sanity**

```bash
pytest tests/conftest.py -v --collect-only
```

预期：列出 5 个 fixture，无 import 错误。

- [ ] **Step 5: 完成自检 + 询问（W7/W8 风险点）**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 6: commit**

```bash
git add tests/conftest.py .gitignore
git commit -m "test: add conftest with db engine, session, user, auth_headers, client fixtures"
# .env.test 不入 git（已被 .gitignore 排除）
```

**预估 commit 数**：1

---

### Task 12: 写 service 单元测试（measurement + goal）

**Files:**
- Create: `tests/test_measurement_service.py`
- Create: `tests/test_goal_service.py`

**Interfaces:**
- 覆盖 10 个 service 函数（6 measurement + 4 goal）的 200/404 路径

依赖：Task 11 fixtures

**关联 spec**：§8.1

**测试用例清单（按函数）**：

| 函数 | 用例 |
|------|------|
| `create_measurement` | 单条成功 + 必填字段校验 |
| `create_measurements_batch` | 3 条全部成功 + 部分非法参数 → 整体失败 |
| `list_measurements` | 默认 + limit/offset + from/to 过滤 |
| `get_measurement` | 成功 + 不存在 404 + 跨用户 404（防枚举） |
| `patch_measurement` | 成功改 notes + 成功改 recorded_at |
| `delete_measurement` | 成功 + 不存在 404 |
| `create_goal` | 默认 status="active" + 全字段 |
| `list_goals` | status=active 过滤 + 默认全部状态 |
| `get_goal` | 成功 + 不存在 404 + 跨用户 404 |
| `update_goal` | 改 status → completed + 改 target_value |

---

- [ ] **Step 1: 写 tests/test_measurement_service.py**

```python
import pytest
from datetime import datetime, timedelta
from models.body_measurement import BodyMeasurement
from core.exceptions import MeasurementNotFoundError, FitForgeException
from schemas.measurement import BodyMeasurementCreate, BodyMeasurementBatchCreate, BodyMeasurementPatch
from services.measurement_service import (
    create_measurement, create_measurements_batch, list_measurements,
    get_measurement, patch_measurement, delete_measurement,
)


@pytest.mark.asyncio
async def test_create_measurement_ok(db_session, sample_user):
    payload = BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow())
    obj = await create_measurement(db_session, sample_user, payload)
    assert obj.id is not None
    assert obj.user_id == sample_user.id


@pytest.mark.asyncio
async def test_create_measurements_batch_all_or_nothing(db_session, sample_user):
    valid_time = datetime.utcnow()
    payload = BodyMeasurementBatchCreate(items=[
        BodyMeasurementCreate(weight=70.0, recorded_at=valid_time),
        BodyMeasurementCreate(weight=71.0, recorded_at=valid_time),
    ])
    objs = await create_measurements_batch(db_session, sample_user, payload)
    assert len(objs) == 2


@pytest.mark.asyncio
async def test_list_measurements_default(db_session, sample_user):
    now = datetime.utcnow()
    for w in [70.0, 71.0, 72.0]:
        await create_measurement(db_session, sample_user, BodyMeasurementCreate(weight=w, recorded_at=now))
    result = await list_measurements(db_session, sample_user)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_list_measurements_with_date_range(db_session, sample_user):
    base = datetime.utcnow()
    await create_measurement(db_session, sample_user, BodyMeasurementCreate(weight=70.0, recorded_at=base - timedelta(days=10)))
    await create_measurement(db_session, sample_user, BodyMeasurementCreate(weight=71.0, recorded_at=base))
    result = await list_measurements(db_session, sample_user, date_from=base - timedelta(days=5))
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_measurement_ok(db_session, sample_user):
    obj = await create_measurement(db_session, sample_user, BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow()))
    got = await get_measurement(db_session, sample_user, obj.id)
    assert got.id == obj.id


@pytest.mark.asyncio
async def test_get_measurement_not_found(db_session, sample_user):
    with pytest.raises(MeasurementNotFoundError):
        await get_measurement(db_session, sample_user, 99999)


@pytest.mark.asyncio
async def test_get_measurement_other_user_returns_404(db_session, sample_user):
    """跨用户访问返回 404 防枚举（D38）"""
    from models.user import User
    other = User(username="bob", email="bob@example.com", password_hash="x")
    db_session.add(other)
    await db_session.commit()

    obj = await create_measurement(db_session, sample_user, BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow()))
    with pytest.raises(MeasurementNotFoundError):
        await get_measurement(db_session, other, obj.id)


@pytest.mark.asyncio
async def test_patch_measurement_notes_and_recorded_at(db_session, sample_user):
    obj = await create_measurement(db_session, sample_user, BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow()))
    new_time = datetime.utcnow() + timedelta(days=1)
    patched = await patch_measurement(
        db_session, sample_user, obj.id,
        BodyMeasurementPatch(notes="updated", recorded_at=new_time)
    )
    assert patched.notes == "updated"
    # weight 不变
    assert patched.weight == 70.0


@pytest.mark.asyncio
async def test_delete_measurement_ok(db_session, sample_user):
    obj = await create_measurement(db_session, sample_user, BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow()))
    await delete_measurement(db_session, sample_user, obj.id)
    with pytest.raises(MeasurementNotFoundError):
        await get_measurement(db_session, sample_user, obj.id)
```

- [ ] **Step 2: 写 tests/test_goal_service.py**

```python
import pytest
from datetime import date, datetime
from models.user_goal import UserGoal
from core.exceptions import GoalNotFoundError
from schemas.goal import UserGoalCreate, UserGoalUpdate
from services.goal_service import create_goal, list_goals, get_goal, update_goal


@pytest.mark.asyncio
async def test_create_goal_default_status_active(db_session, sample_user):
    obj = await create_goal(db_session, sample_user, UserGoalCreate(type="cut", target_value=75.0))
    assert obj.status == "active"


@pytest.mark.asyncio
async def test_list_goals_with_status_filter(db_session, sample_user):
    g1 = await create_goal(db_session, sample_user, UserGoalCreate(type="cut"))
    g2 = await create_goal(db_session, sample_user, UserGoalCreate(type="bulk"))
    await update_goal(db_session, sample_user, g1.id, UserGoalUpdate(status="abandoned"))
    actives = await list_goals(db_session, sample_user, status="active")
    assert len(actives) == 1
    assert actives[0].id == g2.id


@pytest.mark.asyncio
async def test_get_goal_other_user_returns_404(db_session, sample_user):
    from models.user import User
    other = User(username="bob", email="bob@example.com", password_hash="x")
    db_session.add(other)
    await db_session.commit()

    g = await create_goal(db_session, sample_user, UserGoalCreate(type="cut"))
    with pytest.raises(GoalNotFoundError):
        await get_goal(db_session, other, g.id)


@pytest.mark.asyncio
async def test_update_goal_to_completed(db_session, sample_user):
    g = await create_goal(db_session, sample_user, UserGoalCreate(type="cut", target_value=75.0))
    updated = await update_goal(db_session, sample_user, g.id, UserGoalUpdate(status="completed"))
    assert updated.status == "completed"
    # target_value 不变
    assert updated.target_value == 75.0
```

- [ ] **Step 3: 跑 service 测试**

```bash
pytest tests/test_measurement_service.py tests/test_goal_service.py -v
```

预期：**所有 9 + 4 = 13 个 case 全过**。如失败，按 W2/W4/W5 排查。

- [ ] **Step 4: 完成自检 + 询问**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 5: commit**

```bash
git add tests/test_measurement_service.py tests/test_goal_service.py
git commit -m "test(service): add 13 service unit tests for measurement + goal (including D38 enumeration defense)"
```

**预估 commit 数**：1

---

### Task 13: 写 route e2e 测试（body 6 端点）

**Files:**
- Create: `tests/test_body_routes.py`

**Interfaces:**
- 6 端点 × ~3 case = ~15 case

依赖：Task 11（client + auth_headers fixture）+ Task 8（api/body 路由）

---

- [ ] **Step 1: 写 tests/test_body_routes.py**

```python
import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_body_measurement_201(client: AsyncClient, auth_headers):
    body = {"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"}
    r = await client.post("/body-measurements", json=body, headers=auth_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["weight"] == 70.0


@pytest.mark.asyncio
async def test_post_body_measurement_401_no_auth(client: AsyncClient):
    r = await client.post("/body-measurements", json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_post_body_measurement_422_invalid_weight(client: AsyncClient, auth_headers):
    r = await client.post("/body-measurements", json={"weight": 1.0, "recorded_at": "2026-08-16T08:30:00"}, headers=auth_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_batch_201(client: AsyncClient, auth_headers):
    body = {"items": [
        {"weight": 70.0, "recorded_at": "2026-08-15T08:30:00"},
        {"weight": 71.0, "recorded_at": "2026-08-16T08:30:00"},
    ]}
    r = await client.post("/body-measurements/batch", json=body, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["count"] == 2


@pytest.mark.asyncio
async def test_get_body_measurements_with_filters(client: AsyncClient, auth_headers):
    base = "2026-08-16T08:30:00"
    await client.post("/body-measurements", json={"weight": 70.0, "recorded_at": base}, headers=auth_headers)
    r = await client.get("/body-measurements?from=2026-08-15&to=2026-08-17", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_get_measurement_by_id(client: AsyncClient, auth_headers):
    created = (await client.post("/body-measurements", json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"}, headers=auth_headers)).json()
    r = await client.get(f"/body-measurements/{created['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_measurement_404(client: AsyncClient, auth_headers):
    r = await client.get("/body-measurements/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_measurement_notes(client: AsyncClient, auth_headers):
    created = (await client.post("/body-measurements", json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"}, headers=auth_headers)).json()
    r = await client.patch(f"/body-measurements/{created['id']}",
                            json={"notes": "morning"},
                            headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["notes"] == "morning"


@pytest.mark.asyncio
async def test_patch_measurement_422_extra_field(client: AsyncClient, auth_headers):
    """W3: extra="forbid" 必须拒 weight 等不允许 update 的字段"""
    created = (await client.post("/body-measurements", json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"}, headers=auth_headers)).json()
    r = await client.patch(f"/body-measurements/{created['id']}",
                            json={"weight": 999.0, "notes": "x"},
                            headers=auth_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_measurement_204(client: AsyncClient, auth_headers):
    created = (await client.post("/body-measurements", json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"}, headers=auth_headers)).json()
    r = await client.delete(f"/body-measurements/{created['id']}", headers=auth_headers)
    assert r.status_code == 204
    r2 = await client.get(f"/body-measurements/{created['id']}", headers=auth_headers)
    assert r2.status_code == 404
```

- [ ] **Step 2: 跑 body e2e 测试**

```bash
pytest tests/test_body_routes.py -v
```

预期：10 个 case 全过。

- [ ] **Step 3: 完成自检 + 询问**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 4: commit**

```bash
git add tests/test_body_routes.py
git commit -m "test(routes): add 10 e2e tests for body-measurements (POST/POST batch/GET/GET id/PATCH/DELETE + auth + 422)"
```

**预估 commit 数**：1

---

### Task 14: 写 route e2e 测试（goal 4 端点）

**Files:**
- Create: `tests/test_goal_routes.py`

依赖：Task 11 + Task 9

---

- [ ] **Step 1: 写 tests/test_goal_routes.py**

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_goal_201(client: AsyncClient, auth_headers):
    r = await client.post("/user-goals", json={"type": "cut", "target_value": 75.0}, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_post_goal_401_no_auth(client: AsyncClient):
    r = await client.post("/user-goals", json={"type": "cut"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_goals_with_status_filter(client: AsyncClient, auth_headers):
    g1 = (await client.post("/user-goals", json={"type": "cut"}, headers=auth_headers)).json()
    await client.post("/user-goals", json={"type": "bulk"}, headers=auth_headers)
    await client.patch(f"/user-goals/{g1['id']}", json={"status": "completed"}, headers=auth_headers)
    r = await client.get("/user-goals?status=active", headers=auth_headers)
    assert r.status_code == 200
    assert all(g["status"] == "active" for g in r.json())


@pytest.mark.asyncio
async def test_get_goal_by_id(client: AsyncClient, auth_headers):
    created = (await client.post("/user-goals", json={"type": "cut"}, headers=auth_headers)).json()
    r = await client.get(f"/user-goals/{created['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_patch_goal_status_to_completed(client: AsyncClient, auth_headers):
    created = (await client.post("/user-goals", json={"type": "cut", "target_value": 75.0}, headers=auth_headers)).json()
    r = await client.patch(f"/user-goals/{created['id']}", json={"status": "completed", "notes": "达成！"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    # target_value 不变
    assert r.json()["target_value"] == 75.0


@pytest.mark.asyncio
async def test_delete_goal_does_not_exist(client: AsyncClient, auth_headers):
    """Q5: 不实现 DELETE，应返回 405"""
    r = await client.delete("/user-goals/1", headers=auth_headers)
    assert r.status_code == 405


@pytest.mark.asyncio
async def test_patch_goal_422_extra_field(client: AsyncClient, auth_headers):
    """W3: extra="forbid" 必须拒 user_id"""
    created = (await client.post("/user-goals", json={"type": "cut"}, headers=auth_headers)).json()
    r = await client.patch(f"/user-goals/{created['id']}", json={"user_id": 999}, headers=auth_headers)
    assert r.status_code == 422
```

- [ ] **Step 2: 跑 goal e2e 测试**

```bash
pytest tests/test_goal_routes.py -v
```

预期：7 个 case 全过（包括 Q5 verify DELETE 返回 405）。

- [ ] **Step 3: 完成自检 + 询问（Q5 决策点）**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 4: commit**

```bash
git add tests/test_goal_routes.py
git commit -m "test(routes): add 7 e2e tests for user-goals (POST/GET/GET id/PATCH + 405 verify DELETE not implemented)"
```

**预估 commit 数**：1

---

### 大块 6：收尾（Task 15-16）

### Task 15: 服务端到端（curl smoke + 服务器部署）

**Files:**
- Create: `scripts/smoke_body_crud.sh`（smoke 测试脚本）
- Modify: 服务器 `/home/ubuntu/fitforge` 目录上传最新代码 + alembic upgrade + restart uvicorn

**Interfaces:**
- 在服务器上跑 smoke 验证完整链路：
  - register → login → POST measurement → GET list → PATCH notes → DELETE
  - register → POST goal → PATCH status=completed

依赖：Task 1-14 全部完成

**关联 spec**：无（操作类 task，不属于 spec 设计内容）

**风险**：
- 服务器 .env 密码同步（D27 教训）
- 服务器 venv 依赖完整性（D26 容器化 + D27 决策）

---

- [ ] **Step 1: 本地跑全部 pytest 确认通过**

```bash
pytest tests/ -v
```

预期：所有 measurement + goal 测试全过（约 30+ case）。

- [ ] **Step 2: 在本地起服务器，curl smoke**

```bash
uvicorn main:app --log-level warning &
sleep 3
# 1. register
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" -d '{"username":"smoke","email":"smoke@example.com","password":"Smoke123","nickname":"smoke"}' -o /dev/null -w "%{http_code}")
echo "register: $TOKEN"
# 2. login
LOGIN=$(curl -s -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d '{"email":"smoke@example.com","password":"Smoke123"}')
echo "login: $LOGIN"
ACCESS=$(echo "$LOGIN" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
# 3. POST measurement
curl -s -X POST http://127.0.0.1:8000/body-measurements \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"weight":70.5,"recorded_at":"2026-08-16T08:30:00"}' | python -m json.tool
# 4. GET list
curl -s http://127.0.0.1:8000/body-measurements -H "Authorization: Bearer $ACCESS" | python -m json.tool
# 5. POST goal
curl -s -X POST http://127.0.0.1:8000/user-goals \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"type":"cut","target_value":75.0}' | python -m json.tool
kill %1 2>/dev/null
```

预期：所有 200/201 + 正确 JSON 响应（具体响应参考 spec §3）

- [ ] **Step 3: 把脚本保存到 scripts/**

```bash
mkdir -p scripts
```

写入 `scripts/smoke_body_crud.sh`（步骤 2 的内容）

- [ ] **Step 4: 服务器部署**

按之前 /auth/login 的 5 步部署记录（详见 `tech_notes/2026-08-13-server-deploy-record.md`）：
1. 本地 `tar -czf body-crud.tar.gz --exclude=... .`
2. `scp body-crud.tar.gz ubuntu@fitforge:/tmp/`
3. SSH 服务器解包到项目目录
4. 服务器 venv 重新 `pip install -r requirements.txt`（无新依赖，但保险）
5. 服务器 alembic 不需要新迁移（schema 没改）
6. `pkill uvicorn && uvicorn main:app --host 0.0.0.0 --port 8000 &`
7. 服务器跑相同 smoke 脚本

- [ ] **Step 5: 完成自检 + 询问（服务器 smoke 关注 D26/D27 风险点）**

**主动问用户**："需要我立刻记录这次的内容吗？"

- [ ] **Step 6: 双端 commit**

```bash
git add scripts/smoke_body_crud.sh
git commit -m "test(smoke): add curl smoke tests for 11 body+goal endpoints"
```

**预估 commit 数**：1（仅 smoke 脚本；服务器部署本身不入 git）

---

### Task 16: 知识沉淀（3 个文档）

**Files:**
- Create: `tech_notes/2026-08-16-pydantic-v2-extra-forbid.md`
- Create: `tech_notes/2026-08-16-jwt-get-current-user-refactor.md`
- Create: `tech_notes/2026-08-16-batch-api-design-pattern.md`
- Modify: `project_progress.md`（追加周五日志 + D32-D39 决策）

**关联决策**：D32-D39 全部

依赖：Task 15

---

- [ ] **Step 1: 写 tech_notes/2026-08-16-pydantic-v2-extra-forbid.md**

内容大纲（**等用户授权后 Claude 写**）：

- 标题：Pydantic v2 `ConfigDict(extra="forbid")` —— PATCH 端点的安全网
- 5 个要点：
  1. 三种 extra 模式对比（allow / forbid / ignore）
  2. forbid 的两大用途：schema 准确度 + 防字段误覆盖
  3. 在 FitForge 的具体应用：`BodyMeasurementPatch` + `UserGoalUpdate`
  4. **面试话术**："我用 forbid 而非默认 allow —— 前端误传 `weight=999` 时 422 拒绝，业务层不会悄悄覆盖真实测量数据"
  5. 关联决策：D34（D35）

- [ ] **Step 2: 写 tech_notes/2026-08-16-jwt-get-current-user-refactor.md**

内容大纲：

- 标题：把 `get_current_user` 从 api/auth.py 抽到 core/security.py —— 依赖方向 vs 循环 import
- 5 个要点：
  1. **W6 风险**：路由层 import 鉴权 vs core 层提供鉴权（依赖方向）
  2. 改造前后：原 `api/auth.py` 第 116-139 行迁移到 `core/security.py` 末尾
  3. 为什么必须迁移：未来加 `api/body.py`、`api/goal.py` 等都依赖 `get_current_user`，抽到 core 避免每个路由文件都 import api/auth 出现循环
  4. **面试话术**："依赖方向应该指向 core —— core 是基础设施。路由层只做 HTTP 适配，不能让 core 反向 import 路由"
  5. 关联决策：D39

- [ ] **Step 3: 写 tech_notes/2026-08-16-batch-api-design-pattern.md**

内容大纲：

- 标题：批量 API 设计模式——单 + /batch 双端点 vs 单一端点支持多种类型
- 5 个要点：
  1. 业界两种方案对比（双端点 / 单一端点 magic）
  2. 为什么选双端点：Pydantic 不能一个端点接两种类型；schema 复用 List 即可
  3. 整体事务原则（W5）：任一失败全回滚
  4. 大小限制：max_length=50 是工程平衡（实用 vs 风险）
  5. **面试话术**："我用双端点而非 magic isinstance —— 类型清晰、schema 复用 Pydantic `list[T]`、事务边界简单。批量大小有 max 保护防超时"
  6. 关联决策：D33

- [ ] **Step 4: 修改 project_progress.md**

```bash
# 写入 第 1 周第 5 天 周六补 周五内容（spec §10 实施）
# + 追加 D32-D39 决策记录
# 不要重写已有内容，只追加
```

按已有章节格式追加（如 `### 第 1 周 第 5 天 - 周五（2026/08/15）- body_measurements + goals CRUD 补记`）。

- [ ] **Step 5: 跑全部测试 + commit**

```bash
pytest tests/ -v
git add tech_notes/2026-08-16-*.md project_progress.md
git commit -m "docs(notes): add 3 tech notes (extra=forbid, get_current_user refactor, batch API pattern) + project_progress update"
```

**预估 commit 数**：1

---

## 完整产出统计

| 项 | 数量 |
|----|------|
| 任务总数 | 16 |
| commit 数（预估） | 16 |
| 新增文件 | 8（schema × 2 + service × 2 + route × 2 + test × 3 + smoke × 1，部分合并） |
| 修改文件 | 5（exceptions + handlers + security + main + auth） |
| 测试用例数 | 30+（service 13 + body 10 + goal 7） |
| 端点数 | 11（6 measurement + 4 goal + 1 spec 标记不实现） |
| 新决策 | 8（D32-D39） |
| tech_notes 新增 | 3 篇 |

---

## 执行顺序与依赖图

```
Task 1 (exceptions)
    └→ Task 2 (handlers)
         ↓
        ┌── Task 3 (measurement schemas)
        │       ↓
        ├── Task 4 (goal schemas)
        ↓
       Task 5 (measurement service)
       Task 6 (goal service)
       Task 7 (get_current_user refactor)
        ↓
       Task 8 (body routes)
       Task 9 (goal routes)
       Task 10 (main.py include)
        ↓
       Task 11 (conftest)
        ↓
       ┌── Task 12 (service tests)
       ├── Task 13 (body e2e)
       ├── Task 14 (goal e2e)
        ↓
       Task 15 (smoke + server deploy)
        ↓
       Task 16 (tech notes + project_progress)
```

**关键依赖**：
- Task 5/6 强依赖 Task 1（异常）+ Task 3/4（schema）
- Task 8/9 强依赖 Task 7（get_current_user 必须在 core）
- Task 11 必须先于 12/13/14（fixture 提供）
- Task 15 必须先于 16（部署成功才能写"已部署"的事实）

---

## Self-Review Checklist

### 1. Spec coverage 矩阵

| spec 章节 | 对应 task |
|-----------|-----------|
| §3.1-§3.6 (6 measurement 端点) | Task 8 + Task 13（e2e） |
| §3.7-§3.10 (4 goal 端点) | Task 9 + Task 14（e2e） |
| §4.1 (6 measurement schema) | Task 3 |
| §4.2 (4 goal schema) | Task 4 |
| §5.1 (6 measurement service) | Task 5 |
| §5.2 (4 goal service) | Task 6 |
| §6.1 (3 异常) | Task 1 |
| §6.2 (3 handler) | Task 2 |
| §7.4 (get_current_user 抽 core) | Task 7 |
| §8 测试策略 | Task 11/12/13/14 |
| §10 16 任务大块 | 全 16 task |

**结论**：100% 覆盖，**无 spec 章节遗漏**。

### 2. Placeholder scan

- ✅ 无 "TBD" / "TODO" / "implement later"
- ✅ 无 "Add appropriate error handling" 这类泛化
- ✅ 每 step 含具体命令或代码

### 3. Type consistency

| 类型/函数 | 定义位置 | 使用位置 |
|----------|---------|---------|
| `MeasurementNotFoundError` | Task 1 | Task 5, 13 |
| `GoalNotFoundError` | Task 1 | Task 6, 14 |
| `UnauthorizedAccessError` | Task 1 | spec §6.1（未在本 task 直接使用，预留 403） |
| `BodyMeasurementCreate` | Task 3 | Task 5, 13 |
| `BodyMeasurementBatchCreate` | Task 3 | Task 5, 13 |
| `BodyMeasurementPatch` | Task 3 | Task 5, 13 |
| `BodyMeasurementRead` | Task 3 | Task 8, 13 |
| `UserGoalCreate`/`Update`/`Read` | Task 4 | Task 6, 9, 14 |
| `get_current_user` | Task 7（在 core） | Task 8, 9, 13, 14 |
| `create_measurement` 等 6 函数 | Task 5 | Task 8, 13 |
| `create_goal` 等 4 函数 | Task 6 | Task 9, 14 |

**结论**：无函数名/类名拼写冲突。

---

## ⚠️ 执行前提

1. 用户已批准 spec（commit `2ab935e`）
2. 用户已选择执行模式（subagent-driven / inline execution）—— 本计划不限制
3. 工作区未提交的 ~20 个修改文件（CLAUDE.md / README.md / alembic/env.py / main.py / models/user_goal.py 等）需要先确认如何处理（保留 / stash / checkout --）

---

**执行选项**（writing-plans 标准）：

1. **Subagent-Driven（推荐）**：我派遣 fresh subagent 逐 task 执行 + 每 task 后 review
2. **Inline Execution**：在本会话执行 + checkpoint

**请用户选择模式**。
