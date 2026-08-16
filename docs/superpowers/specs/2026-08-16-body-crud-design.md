# body_measurements + user_goals CRUD 设计文档

> **日期**：2026-08-16（周六补周五任务）
> **作者**：LHR6666（与 Claude Code brainstorming 产出）
> **目的**：设计 11 个端点（6 measurements + 5 goals，goals 不含 DELETE），覆盖 MVP 业务闭环
> **关联决策**：D17（3 张表 schema）+ D19（重型 service / 业务异常）+ D28-D31（JWT）
> **关联 spec**：
> - `docs/superpowers/specs/2026-07-06-auth-register-design.md`（register）
> - `docs/superpowers/specs/2026-08-14-auth-login-design.md`（login + JWT 中间件）
> **状态**：⏳ 待用户 review

---

## 1. 概述

### 1.1 设计目标

FitForge MVP 业务闭环的"数据层"端点：

- **body_measurements**：身体测量数据（体重/体脂/6 围度/3 力量 1RM）的 CRUD
- **user_goals**：训练目标（cut/bulk/maintain/strength + status 状态机）的 CRUD（无 DELETE）
- **统一鉴权**：所有端点 `Depends(get_current_user)`
- **复用架构**：与 register / login 的 6 决策一致（重型 service + 业务异常 + 2 schema + Depends）

### 1.2 端点清单（11 个，简化版）

| 资源 | 端点数 | 端点 |
|------|--------|------|
| `body_measurements` | 6 | POST（单）/ POST /batch（批量）/ GET / GET {id} / PATCH {id} / DELETE {id} |
| `user_goals` | 4 | POST / GET（带 status 过滤）/ GET {id} / PATCH {id} |
| **不实现** | 0 | `DELETE /user-goals/{id}`（Q5 决策） |

### 1.3 不做什么（YAGNI 红线）

- ❌ 不做软删除（D17 NOT DO 清单）
- ❌ 不引入分页库（SQLAlchemy 原生 limit/offset）
- ❌ 不做图片上传
- ❌ 不做跨用户访问（教练场景未来扩）
- ❌ 不做并发乐观锁（measurements 不允许 update 关键字段；goals update 走"读-改-写"已够）
- ❌ 不做审计日志（D17 第 10 周后）

---

## 2. 决策汇总（Q1-Q8）

### Q1. URL 形态（已拍）

- **决策**：**平铺 RESTful**（`/body-measurements`、`/user-goals`）
- **理由**：
  - 与现有 `/auth/*` 风格统一
  - "我的"语义由 `Depends(get_current_user)` 隐式表达，URL 不冗余
  - 未来升级"教练场景"迁移到 `/users/{user_id}/...` 是渐进式重构，不破坏既有客户端
- **替代**：
  - 嵌套 `/users/me/...`（路径长 + 当前冗余）
  - 平铺 + 显式 user_id 参数（多一层校验冲突）

### Q2. body_measurements 创建粒度（已拍）

- **决策**：**两个端点都支持**：`POST /body-measurements`（单） + `POST /body-measurements/batch`（批量）
- **理由**：
  - 实测一周早晚各一次 → 补录场景 7 个 POST 太啰嗦
  - 两个端点共用同一 service，schema 一次定义 `List[BodyMeasurementCreateItem]` 复用
- **业务约束**：
  - 批量端点：**整体事务**（部分失败全部回滚）
  - 批量大小限制：`min_length=1, max_length=50`

### Q3. body_measurements update 策略（已拍）

- **决策**：**部分 update** — 只允许改 `notes` + `recorded_at`
- **理由**：
  - 体重/腰围/1RM 是客观测量值 → **事后改即造假**，业务上禁止
  - 但"我 9 点测，想改成 8 点半"或"补一句备注"是合理需求
  - SQL 层用 `Service.patch_measurement` 精确 update 这 2 个字段，避免服务层写错

### Q4. user_goals update 策略

- **决策**：**允许 update 全部字段**
- **理由**：
  - `status` 必须能切（`active` → `completed` / `abandoned`）—— 不支持 update 等于列表功能废了
  - 用户可能改 `target_value`（"原计划减 70 改减 65"）或 `deadline` 调整
  - 与 measurements 不同的语义：goal 是"意图"，可改；measurement 是"事实"，不可改
- **字段**：type / target_value / status / deadline / notes / recorded_at
- **不允许 PATCH**：user_id（永远从 token 取）/ id / created_at / updated_at

### Q5. 删除策略

- **measurements**：**硬删**（`DELETE /body-measurements/{id}`，落到 DB DELETE）
  - 理由：D17 NOT DO 软删除；客观数据可重测
- **goals**：**不实现 DELETE**，改走 `status='abandoned'` + PATCH 路径
  - 理由：goal 是历史轨迹（"我曾想减到 75kg"），硬删会损失用户成长数据
  - YAGNI：MVP 不做 delete

### Q6. 列表查询参数

| 端点 | 参数 | 默认 | 说明 |
|------|------|------|------|
| `GET /body-measurements` | `from` / `to` / `limit` / `offset` | `limit=20, offset=0` | `from`/`to` 是 ISO date，filter `recorded_at` |
| `GET /user-goals` | `status` / `limit` / `offset` | `status=None`（全部）/`limit=20, offset=0` | status 是 Literal["active","completed","abandoned"] |

- **不引入 fastapi-pagination**：SQLAlchemy 原生 limit/offset
- **验证**：service 层 assert `limit <= 100`（`offset >= 0`）；超了抛 `FitForgeException("limit 超过最大值 100")` → 400
- **排序**：默认按 `recorded_at DESC` / `created_at DESC`

### Q7. user_goals active 唯一性

- **决策**：**允许多个 active 共存**
- **理由**：
  - 健身场景"减脂 cut + 加力 strength"可并行（多目标用户大有人在）
  - 强制唯一会让用户每次只能"切目标"，体验差
  - 后续想做"主目标"再扩字段 `is_primary: bool`，不影响 schema
- **替代**：唯一 active → "切目标"逻辑，但 MVP 不需要

### Q8. 测试策略

- **service 单元**（`pytest + AsyncSession`，in-process SQLite or MySQL Test）：
  - create 单条 / create 批量（部分非法 → 整体回滚）/ list 带过滤 / update 部分字段 / 删 / 跨用户访问（防御性）
  - 异常：NotFound / Unauthorized
- **route e2e**（`pytest + httpx AsyncClient`，in-process FastAPI）：
  - 每个端点：200/201 路径 + 401（无 token）+ 404 + 422/400（参数错）
  - **不引入** respx / mock 库：直接打 in-process FastAPI
- **覆盖率目标**：service 函数 100%（目标 10 个 case/函数）+ route 端点 100%（200 + 至少 1 失败）

---

## 3. 端点详细定义

### 3.1 POST /body-measurements（单条）

**鉴权**：`Depends(get_current_user)`

**请求**（BodyMeasurementCreate）：
```json
{
  "weight": 70.5,
  "body_fat": 18.2,
  "chest": 100.0, "waist": 80.0, "hip": 95.0,
  "bicep": 35.0, "thigh": 55.0, "calf": 38.0,
  "squat_1rm": 120.0, "bench_1rm": 80.0, "deadlift_1rm": 140.0,
  "recorded_at": "2026-08-16T08:30:00",
  "notes": "早上空腹测"
}
```

**响应 201**（BodyMeasurementRead）：完整字段 + id + user_id + created_at

**错误码**：
- 422：Pydantic 字段校验失败（weight < 20、recorded_at 缺省）
- 401：未登录 / token 无效
- 500：未捕获异常

### 3.2 POST /body-measurements/batch（批量）

**鉴权**：同 3.1

**请求**（BodyMeasurementBatchCreate）：
```json
{
  "items": [
    { "weight": 70.5, "recorded_at": "2026-08-15T08:30:00" },
    { "weight": 71.0, "recorded_at": "2026-08-15T20:00:00" },
    { "weight": 70.8, "recorded_at": "2026-08-16T08:30:00" }
  ]
}
```

**响应 201**（BodyMeasurementBatchRead）：
```json
{
  "count": 3,
  "items": [<BodyMeasurementRead x3>]
}
```

**业务规则**：
- 整体事务：任一 item 校验失败 → 整个批次回滚
- 大小限制：min_length=1, max_length=50

**错误码**：同 3.1 + 400（超 max_length=50）

### 3.3 GET /body-measurements（列表）

**鉴权**：同 3.1

**Query**：
- `from` (ISO date，可选)：recorded_at >= from
- `to` (ISO date，可选)：recorded_at <= to
- `limit` (int，默认 20，1-100)
- `offset` (int，默认 0，>=0)

**响应 200**：`List[BodyMeasurementRead]`

**排序**：`recorded_at DESC`

**错误码**：401 / 422 (limit 越界)

### 3.4 GET /body-measurements/{measurement_id}

**鉴权**：同 3.1

**响应 200**：`BodyMeasurementRead`

**错误码**：
- 404：`MeasurementNotFoundError`（id 不存在）
- 404：`UnauthorizedAccessError`（id 存在但 user_id != current_user.id）—— 安全考虑，**不暴露**资源存在与否
- 401：未登录

### 3.5 PATCH /body-measurements/{measurement_id}

**鉴权**：同 3.1

**请求**（BodyMeasurementPatch）：
```json
{
  "recorded_at": "2026-08-15T08:00:00",
  "notes": "修订：其实是早上 8 点测的"
}
```

**响应 200**：`BodyMeasurementRead`

**业务规则**：
- 仅允许 `notes` + `recorded_at` 两字段（Q3）
- 其他字段传了会被 Pydantic `extra="forbid"` 拒

**错误码**：401 / 404（不存在或非本人）/ 422

### 3.6 DELETE /body-measurements/{measurement_id}

**鉴权**：同 3.1

**响应 204**：No Content

**业务规则**：硬删；幂等（重复删 404，不报错）

**错误码**：401 / 404

---

### 3.7 POST /user-goals

**鉴权**：同 3.1

**请求**（UserGoalCreate）：
```json
{
  "type": "cut",
  "target_value": 75.0,
  "deadline": "2026-12-31",
  "notes": "3 个月减到 75kg"
}
```

**响应 201**（UserGoalRead）：完整字段 + id + user_id + status="active"（默认）+ created_at

**错误码**：401 / 422

### 3.8 GET /user-goals（列表）

**Query**：
- `status` (Literal["active","completed","abandoned"]，可选)
- `limit` / `offset`（默认 20/0，limit ≤ 100）

**响应 200**：`List[UserGoalRead]`

**排序**：`created_at DESC`

**错误码**：401 / 422

### 3.9 GET /user-goals/{goal_id}

**响应 200**：`UserGoalRead`

**错误码**：401 / 404（同 3.4）

### 3.10 PATCH /user-goals/{goal_id}

**请求**（UserGoalUpdate）：
```json
{
  "status": "completed",
  "notes": "已达成！8 月 1 日达标"
}
```

**响应 200**：`UserGoalRead`

**业务规则**：仅允许这 5 个字段：type / target_value / status / deadline / notes

**错误码**：401 / 404 / 422

---

### 3.11 ~~DELETE /user-goals/{goal_id}~~

**不实现**（Q5）—— 走 `PATCH status=abandoned`

---

## 4. Pydantic Schema 定义（schemas/measurement.py + schemas/goal.py）

### 4.1 schemas/measurement.py

```python
"""body_measurements Pydantic schemas."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

# ===== 入参 =====

class BodyMeasurementCreate(BaseModel):
    """POST /body-measurements 入参"""
    weight: float = Field(ge=20, le=300, description="体重 kg，必填")
    body_fat: float | None = Field(default=None, ge=3, le=60, description="体脂率 %")
    chest: float | None = Field(default=None, ge=0, le=300)
    waist: float | None = Field(default=None, ge=0, le=300)
    hip: float | None = Field(default=None, ge=0, le=300)
    bicep: float | None = Field(default=None, ge=0, le=100)
    thigh: float | None = Field(default=None, ge=0, le=100)
    calf: float | None = Field(default=None, ge=0, le=80)
    squat_1rm: float | None = Field(default=None, ge=0, le=500)
    bench_1rm: float | None = Field(default=None, ge=0, le=500)
    deadlift_1rm: float | None = Field(default=None, ge=0, le=500)
    recorded_at: datetime = Field(description="业务时间（D17-c 业务时间分离）")
    notes: str | None = Field(default=None, max_length=1000)


class BodyMeasurementBatchCreate(BaseModel):
    """POST /body-measurements/batch 入参"""
    items: list[BodyMeasurementCreate] = Field(
        min_length=1, max_length=50,
        description="1-50 条测量记录",
    )


class BodyMeasurementPatch(BaseModel):
    """PATCH /body-measurements/{id} 入参（Q3：仅 notes + recorded_at）"""
    model_config = ConfigDict(extra="forbid")  # 拒额外字段
    notes: str | None = Field(default=None, max_length=1000)
    recorded_at: datetime | None = None


class BodyMeasurementListQuery(BaseModel):
    """GET /body-measurements query 参数"""
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# ===== 出参 =====

class BodyMeasurementRead(BaseModel):
    """GET / POST 响应体"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    weight: float
    body_fat: float | None
    chest: float | None
    waist: float | None
    hip: float | None
    bicep: float | None
    thigh: float | None
    calf: float | None
    squat_1rm: float | None
    bench_1rm: float | None
    deadlift_1rm: float | None
    recorded_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime


class BodyMeasurementBatchRead(BaseModel):
    """POST /batch 响应体"""
    count: int
    items: list[BodyMeasurementRead]
```

### 4.2 schemas/goal.py

```python
"""user_goals Pydantic schemas."""

from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# ===== 入参 =====

GOAL_TYPE = Literal["cut", "bulk", "maintain", "strength"]
GOAL_STATUS = Literal["active", "completed", "abandoned"]


class UserGoalCreate(BaseModel):
    """POST /user-goals 入参"""
    type: GOAL_TYPE
    target_value: float | None = Field(default=None, ge=0, le=1000)
    deadline: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    # status 默认 "active"，service 层填


class UserGoalUpdate(BaseModel):
    """PATCH /user-goals/{id} 入参（Q4：5 字段）"""
    model_config = ConfigDict(extra="forbid")
    type: GOAL_TYPE | None = None
    target_value: float | None = Field(default=None, ge=0, le=1000)
    status: GOAL_STATUS | None = None
    deadline: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class UserGoalListQuery(BaseModel):
    """GET /user-goals query 参数"""
    status: GOAL_STATUS | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# ===== 出参 =====

class UserGoalRead(BaseModel):
    """GET / POST / PATCH 响应体"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    type: str  # PyBaseModel Literal 类型 + ORM str 列，反序列化保留为 str
    target_value: float | None
    status: str
    deadline: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

---

## 5. Service 层定义

### 5.1 services/measurement_service.py

```python
"""body_measurements 业务逻辑。

Q1 重型 service：接 Pydantic schema → 返回 ORM → 抛业务异常
路由层做 ORM → BodyMeasurementRead 转换（Q4 与 register 风格一致）
"""

from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import MeasurementNotFoundError, UnauthorizedAccessError
from models.user import User
from models.body_measurement import BodyMeasurement
from schemas.measurement import (
    BodyMeasurementCreate,
    BodyMeasurementBatchCreate,
    BodyMeasurementPatch,
)


async def create_measurement(
    db: AsyncSession,
    current_user: User,
    payload: BodyMeasurementCreate,
) -> BodyMeasurement:
    """创建单条测量记录。"""
    obj = BodyMeasurement(user_id=current_user.id, **payload.model_dump())
    db.add(obj)
    await db.flush()
    await db.commit()
    return obj


async def create_measurements_batch(
    db: AsyncSession,
    current_user: User,
    payload: BodyMeasurementBatchCreate,
) -> list[BodyMeasurement]:
    """批量创建（整体事务）。"""
    objs = [
        BodyMeasurement(user_id=current_user.id, **item.model_dump())
        for item in payload.items
    ]
    db.add_all(objs)
    await db.flush()
    await db.commit()
    return objs


async def list_measurements(
    db: AsyncSession,
    current_user: User,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[BodyMeasurement]:
    """列表（按用户 + 时间区间 + limit/offset）。"""
    # Q6: limit <= 100 校验（路由层 FastAPI Query 校验，service 不重复）
    stmt = (
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == current_user.id)
        .order_by(BodyMeasurement.recorded_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if date_from is not None:
        stmt = stmt.where(BodyMeasurement.recorded_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(BodyMeasurement.recorded_at <= date_to)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_measurement(
    db: AsyncSession,
    current_user: User,
    measurement_id: int,
) -> BodyMeasurement:
    """取单条（含权限校验：仅本人可读）。"""
    obj = await db.get(BodyMeasurement, measurement_id)
    if obj is None:
        raise MeasurementNotFoundError(f"测量记录 {measurement_id} 不存在")
    if obj.user_id != current_user.id:
        # 安全：故意抛 NotFound 而非 UnauthorizedAccess，防 ID 枚举
        raise MeasurementNotFoundError(f"测量记录 {measurement_id} 不存在")
    return obj


async def patch_measurement(
    db: AsyncSession,
    current_user: User,
    measurement_id: int,
    patch: BodyMeasurementPatch,
) -> BodyMeasurement:
    """部分 update（仅 notes / recorded_at）。"""
    obj = await get_measurement(db, current_user, measurement_id)  # 自动验权
    update_data = patch.model_dump(exclude_unset=True)  # 仅取显式传的字段
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_measurement(
    db: AsyncSession,
    current_user: User,
    measurement_id: int,
) -> None:
    """硬删（含权限校验）。"""
    obj = await get_measurement(db, current_user, measurement_id)
    await db.delete(obj)
    await db.commit()
```

### 5.2 services/goal_service.py

```python
"""user_goals 业务逻辑。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import GoalNotFoundError
from models.user import User
from models.user_goal import UserGoal
from schemas.goal import UserGoalCreate, UserGoalUpdate


async def create_goal(
    db: AsyncSession,
    current_user: User,
    payload: UserGoalCreate,
) -> UserGoal:
    """创建目标（status 默认 active）。"""
    obj = UserGoal(
        user_id=current_user.id,
        status="active",  # 默认值（Q5: 不允许创建时指定 status）
        **payload.model_dump(),
    )
    db.add(obj)
    await db.flush()
    await db.commit()
    return obj


async def list_goals(
    db: AsyncSession,
    current_user: User,
    *,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[UserGoal]:
    """列表（status 过滤 + 分页）。"""
    stmt = (
        select(UserGoal)
        .where(UserGoal.user_id == current_user.id)
        .order_by(UserGoal.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(UserGoal.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_goal(
    db: AsyncSession,
    current_user: User,
    goal_id: int,
) -> UserGoal:
    """取单条（含权限）。"""
    obj = await db.get(UserGoal, goal_id)
    if obj is None or obj.user_id != current_user.id:
        raise GoalNotFoundError(f"目标 {goal_id} 不存在")
    return obj


async def update_goal(
    db: AsyncSession,
    current_user: User,
    goal_id: int,
    update: UserGoalUpdate,
) -> UserGoal:
    """update 5 字段（Q4）。"""
    obj = await get_goal(db, current_user, goal_id)
    update_data = update.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj
```

---

## 6. 异常体系补强

### 6.1 core/exceptions.py 新增 3 个子类

```python
class MeasurementNotFoundError(FitForgeException):
    """测量记录不存在或非当前用户所有（HTTP 404）。"""
    pass


class GoalNotFoundError(FitForgeException):
    """训练目标不存在或非当前用户所有（HTTP 404）。"""
    pass


class UnauthorizedAccessError(FitForgeException):
    """未授权访问他人资源（HTTP 403）。"""
    pass
```

**设计选择**：跨用户访问返回 404 而非 403，原因：
- 防资源枚举攻击（攻击者通过响应差异探测哪些 id 存在）
- 与 GitHub / Stack Overflow 等大厂设计一致

### 6.2 api/exception_handlers.py 新增 2 个 handler

```python
@app.exception_handler(MeasurementNotFoundError)
async def measurement_not_found_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(GoalNotFoundError)
async def goal_not_found_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(UnauthorizedAccessError)
async def unauthorized_access_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )
```

---

## 7. 路由层定义

### 7.1 api/body.py

```python
"""body_measurements 路由层。"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.security import get_current_user  # 重命名自 api/auth.py
from models.user import User
from schemas.measurement import (
    BodyMeasurementBatchCreate,
    BodyMeasurementBatchRead,
    BodyMeasurementCreate,
    BodyMeasurementListQuery,
    BodyMeasurementPatch,
    BodyMeasurementRead,
)
from services import measurement_service


router = APIRouter(prefix="/body-measurements", tags=["body-measurements"])


@router.post("", response_model=BodyMeasurementRead, status_code=status.HTTP_201_CREATED)
async def create_measurement(
    payload: BodyMeasurementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementRead:
    obj = await measurement_service.create_measurement(db, current_user, payload)
    return BodyMeasurementRead.model_validate(obj)


@router.post("/batch", response_model=BodyMeasurementBatchRead, status_code=status.HTTP_201_CREATED)
async def create_measurements_batch(
    payload: BodyMeasurementBatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementBatchRead:
    objs = await measurement_service.create_measurements_batch(db, current_user, payload)
    return BodyMeasurementBatchRead(
        count=len(objs),
        items=[BodyMeasurementRead.model_validate(o) for o in objs],
    )


@router.get("", response_model=list[BodyMeasurementRead])
async def list_measurements(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BodyMeasurementRead]:
    objs = await measurement_service.list_measurements(
        db, current_user, date_from=from_, date_to=to, limit=limit, offset=offset,
    )
    return [BodyMeasurementRead.model_validate(o) for o in objs]


@router.get("/{measurement_id}", response_model=BodyMeasurementRead)
async def get_measurement(
    measurement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementRead:
    obj = await measurement_service.get_measurement(db, current_user, measurement_id)
    return BodyMeasurementRead.model_validate(obj)


@router.patch("/{measurement_id}", response_model=BodyMeasurementRead)
async def patch_measurement(
    measurement_id: int,
    patch: BodyMeasurementPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementRead:
    obj = await measurement_service.patch_measurement(db, current_user, measurement_id, patch)
    return BodyMeasurementRead.model_validate(obj)


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement(
    measurement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await measurement_service.delete_measurement(db, current_user, measurement_id)
```

### 7.2 api/goal.py

```python
"""user_goals 路由层。"""

from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.security import get_current_user
from models.user import User
from schemas.goal import UserGoalCreate, UserGoalRead, UserGoalUpdate
from services import goal_service


router = APIRouter(prefix="/user-goals", tags=["user-goals"])


@router.post("", response_model=UserGoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: UserGoalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserGoalRead:
    obj = await goal_service.create_goal(db, current_user, payload)
    return UserGoalRead.model_validate(obj)


@router.get("", response_model=list[UserGoalRead])
async def list_goals(
    status: Literal["active", "completed", "abandoned"] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserGoalRead]:
    objs = await goal_service.list_goals(
        db, current_user, status=status, limit=limit, offset=offset,
    )
    return [UserGoalRead.model_validate(o) for o in objs]


@router.get("/{goal_id}", response_model=UserGoalRead)
async def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserGoalRead:
    obj = await goal_service.get_goal(db, current_user, goal_id)
    return UserGoalRead.model_validate(obj)


@router.patch("/{goal_id}", response_model=UserGoalRead)
async def update_goal(
    goal_id: int,
    update: UserGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserGoalRead:
    obj = await goal_service.update_goal(db, current_user, goal_id, update)
    return UserGoalRead.model_validate(obj)
```

### 7.3 main.py 修改

```python
# 在现有 include_router 之后增加
from api.body import router as body_router
from api.goal import router as goal_router

app.include_router(body_router)
app.include_router(goal_router)
```

### 7.4 api/auth.py 重构（命名迁移）

`get_current_user` 当前定义在 `api/auth.py`。需要：
- **选项 A**：抽到 `core/security.py`（推荐，避免路由层循环 import）
- **选项 B**：保持 `api/auth.py`，import 路径 `from api.auth import get_current_user`

建议选项 A（迁移到 `core/security.py`），与 `core/exceptions.py` 同级。**注意**：当前 `api/auth.py` 已经实现 `get_current_user`，本次只迁移位置，**不动逻辑**。

---

## 8. 测试策略

### 8.1 服务单元（pytest + AsyncSession + testcontainers MySQL）

`tests/test_measurement_service.py`：
- 创建单条：成功 + 字段全
- 批量创建：3 条全部入库 + 部分非法回滚
- 列表：默认 + limit/offset + from/to 过滤
- 获取单条：成功 + 不存在 404 + 跨用户 404
- patch：成功 + 仅允许字段
- delete：成功 + 不存在 404

`tests/test_goal_service.py`：
- 创建：默认 status=active + 全字段
- 列表：status=active 过滤
- 获取：成功 + 不存在 404 + 跨用户 404
- update：成功 + 部分字段

### 8.2 路由 e2e（pytest + httpx AsyncClient）

`tests/test_body_routes.py`：
- POST `/body-measurements`：201 + 401 + 422
- POST `/body-measurements/batch`：201 批量 + 400 超 max
- GET `/body-measurements`：200 + 401
- GET `/{id}`：200 + 401 + 404
- PATCH `/{id}`：200 + 401 + 404 + 422 extra 字段
- DELETE `/{id}`：204 + 401 + 404

`tests/test_goal_routes.py`：同结构

### 8.3 测试隔离

- 每个测试用独立 user，避免 cross-contamination
- 用 `pytest-asyncio` 异步执行
- 数据库：`tests/conftest.py` 创建 test session，setUp/tearDown 创清表

---

## 9. 文件落盘清单

| 路径 | 新增 / 修改 | 内容 |
|------|------------|------|
| `schemas/measurement.py` | 新 | 5 schema |
| `schemas/goal.py` | 新 | 4 schema |
| `core/exceptions.py` | 改 | +3 子类 |
| `core/security.py` | 改 | 把 `get_current_user` 从 `api/auth.py` 移过来（或保留，下方 §7.4 标注） |
| `api/exception_handlers.py` | 改 | +3 handler |
| `services/measurement_service.py` | 新 | 6 函数 |
| `services/goal_service.py` | 新 | 4 函数 |
| `api/body.py` | 新 | 6 路由 |
| `api/goal.py` | 新 | 4 路由 |
| `api/auth.py` | 改 | （可选）移除 `get_current_user` 定义 |
| `main.py` | 改 | include 2 新 router |
| `tests/conftest.py` | 新 | 测试 fixture |
| `tests/test_measurement_service.py` | 新 | unit |
| `tests/test_goal_service.py` | 新 | unit |
| `tests/test_body_routes.py` | 新 | e2e |
| `tests/test_goal_routes.py` | 新 | e2e |

**总计**：8 新文件 + 5 修改文件 = 13 个文件

---

## 10. 实施 TODO 大块（按 plan skill 拆分）

| 大块 | 内容 | 任务数（预估） |
|------|------|---------------|
| 1. 异常 + handler | core/exceptions.py +3 类、api/exception_handlers.py +3 handler | 2 |
| 2. Schemas | schemas/measurement.py + schemas/goal.py | 2 |
| 3. Service 层 | services/measurement_service.py（6 函数） + services/goal_service.py（4 函数） | 3 |
| 4. 路由层 | api/body.py（6 路由）+ api/goal.py（4 路由）+ main.py include | 3 |
| 5. 测试 | conftest.py + 4 测试文件 | 4 |
| 6. 收尾 | server 端到端（curl 验证）+ 知识沉淀 | 2 |

总计 **16 任务**

---

## 11. 决策编号

- **D32**：URL 平铺 RESTful（/body-measurements、/user-goals）
- **D33**：body_measurements 两个创建端点（单 + batch），整体事务
- **D34**：measurements PATCH 仅允许 notes/recorded_at
- **D35**：goals PATCH 允许全 5 字段（不含 user_id/id/time）
- **D36**：measurements 硬删 + goals 不实现 DELETE（走 status=abandoned）
- **D37**：列表 limit 上限 100、offset ≥ 0（业务保护）
- **D38**：跨用户访问返回 404 防枚举（与 GitHub 一致）
- **D39**：get_current_user 抽到 core/security.py（避免路由层循环 import）

---

## 12. 面试话术

### Q：怎么设计"创建多条测量"的接口？

> "我提供两个端点：`POST /body-measurements` 单条 + `POST /body-measurements/batch` 批量数组。**整体事务**保证——一条失败全部回滚，避免脏数据。批量上限 50 条是工程保护：太小不够实用，太大一个请求超时风险高。Service 复用同一个 ORM 添加路径，schema 一次定义 `List[BodyMeasurementCreateItem]` 复用。"

### Q：身体测量数据允许 update 吗？

> "**部分 update** —— 只允许改 notes + recorded_at。体重/腰围/1RM 都是客观测量值，事后改即造假，业务上禁止。但'我 9 点测的，想改 8 点半'或'补一句备注'是合理需求。Pydantic `extra='forbid'` 拒绝额外字段，避免前端误传 weight 这种关键字段被悄悄覆盖。"

### Q：为什么 user_goals 没有 DELETE？

> "**走 status 状态机** —— '放弃'是个有意义的状态，不是个动作。goal 是用户的成长轨迹（'我曾想减到 75kg'），硬删会损失这些数据。MVP 只允许 `PATCH status='abandoned'`，未来想看'我放弃过哪些目标 / 为什么放弃'，靠数据库历史就行。这跟 GitHub Issue 关掉（不删）的设计哲学一致——动作状态化。"

### Q：跨用户访问返回什么状态码？

> "**404 Not Found**，不是 403。原因是防资源 ID 枚举攻击——攻击者通过 403 vs 404 响应差异探测哪些 id 存在。GitHub / Stack Overflow 等大厂都用 404 兜底。我们业务上'用户 A 看不到用户 B 的资源'——拿不到说明就该说'找不到'，安全利益一致。"

### Q：为什么把 get_current_user 从 auth.py 抽到 core/security.py？

> "**避免循环 import** + **体现依赖方向**：业务模块（api/body、api/goal）需要鉴权，依赖 core（基础设施）是不允许反过来。这样未来想写 CLI 脚本绕过 HTTP 直接调业务逻辑时，鉴权也可以复用。**核心原则**：路由层只是 HTTP 适配，所有可复用逻辑都该在更低层。"

---

## 13. 审批

- [ ] ✅ 用户于 2026-08-16 头脑风暴中通过 Q1-Q8
- [ ] ⏳ 用户对 spec review 通过
- [ ] ⏳ 用户授权调用 writing-plans skill 生成实施 plan

---

**关联实施**：本文档通过 spec 自审后，将调 `writing-plans` 生成 16 task 的详细实施 plan。
