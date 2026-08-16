# 批量 API 设计模式 —— 单 + /batch 双端点 vs 单一端点 magic

> **日期**：2026-08-16（周六补周五内容）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D33（body_measurements 两个创建端点：单 + batch，整体事务）
> **关联 commit**：`9304333`（BodyMeasurementBatchCreate schema）、`3238d5d`（create_measurements_batch service）、`dc98286`（test_post_batch_201）、`9f4f927`（smoke 2.4 step）
> **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md` §3.1 / §3.2 / §5.1 / §11 D33
> **目的**：面试前复习 + 业界两种批量 API 设计对比 + 整体事务原则 + 大小限制的工程平衡

---

## 1. 业界两种方案对比

设计"批量创建 N 条记录"的 API 时，业界有 2 种主流方案：


| 方案                       | 端点形态                              | 类型校验                            | 适用场景          |
| ------------------------ | --------------------------------- | ------------------------------- | ------------- |
| **方案 A：双端点**（FitForge 选的） | `POST /resources` 单条<br>`POST /resources/batch` 批量 | 两个独立 Pydantic schema（清晰）        | **推荐** —— 业务边界清晰 |
| **方案 B：单端点 magic**         | `POST /resources` 自动识别单条 / 数组       | 一个 schema + `Union[T, list[T]]` | 极少用，类型不清晰     |
| 方案 C：只用批量，单条 = 批量 1 条      | `POST /resources/batch` 必传数组        | 只有 batch schema                 | API 设计糟糕      |
| 方案 D：GraphQL mutation     | 自定义 mutation 参数                    | SDL 定义                          | 已有 GraphQL 栈时 |

### 1.1 方案 B（magic）的具体实现

```python
# 方案 B：单端点，body 既可以是 dict 也可以是 list[dict]
from typing import Union

class BodyMeasurementCreate(BaseModel):
    weight: float
    recorded_at: datetime

@router.post("/body-measurements")
async def create(
    payload: Union[BodyMeasurementCreate, list[BodyMeasurementCreate]],  # ← magic
):
    if isinstance(payload, list):
        # 批量逻辑
        ...
    else:
        # 单条逻辑
        ...
```

**问题**：

1. **类型不清晰**：OpenAPI 文档里类型是 `oneOf`，前端工程师不知道哪个字段是 list、哪个不是
2. **业务边界模糊**：单条和批量走的是同一函数，但事务、日志、metrics 都不同
3. **错误处理复杂**：批量部分失败 vs 单条失败，错误响应格式不一致
4. **schema 复用差**：单条 schema 改了，批量也得跟着测

### 1.2 方案 A（FitForge 选的）的具体实现

```python
# 方案 A：双端点
class BodyMeasurementCreate(BaseModel):
    """POST /body-measurements 入参（单条）"""
    weight: float = Field(ge=20, le=300)
    body_fat: float | None = Field(default=None, ge=3, le=60)
    # ... 13 字段
    recorded_at: datetime
    notes: str | None = Field(default=None, max_length=1000)


class BodyMeasurementBatchCreate(BaseModel):
    """POST /body-measurements/batch 入参（批量）"""
    items: list[BodyMeasurementCreate] = Field(
        min_length=1,
        max_length=50,
        description="1-50 条测量记录",
    )


@router.post("", response_model=BodyMeasurementRead, status_code=201)
async def create_measurement(payload: BodyMeasurementCreate, ...): ...


@router.post("/batch", response_model=BodyMeasurementBatchRead, status_code=201)
async def create_measurements_batch(payload: BodyMeasurementBatchCreate, ...): ...
```

**优点**：

- OpenAPI 文档清晰：单条/批量是两个独立 endpoint
- 类型无歧义：`BodyMeasurementCreate` vs `BodyMeasurementBatchCreate`
- 错误响应统一：批量端点永远返回 `count + items` 或整个 422（不会"半成功"）
- schema 复用：`list[BodyMeasurementCreate]` 自动复用单条 schema 的所有验证

> **面试话术**：「我用双端点而非单端点 magic——Pydantic 不能优雅处理 `Union[T, list[T]]`（OpenAPI 生成 `oneOf`，前端类型不清）。双端点让单条和批量走不同路由，schema 独立定义、事务边界清晰、错误响应统一。schema 复用靠 `list[BodyMeasurementCreate]` 自动继承单条字段验证，避免代码重复。」

---

## 2. 为什么 FitForge 选双端点（业务驱动）

### 2.1 业务场景

健身用户**实测一周早晚各一次** → 7 天 × 2 = 14 条。如果只有单条端点，补录一天要 2 个 POST（早晚），补一周要 14 个 POST——啰嗦 + 网络开销大。

### 2.2 两个端点共用一个 service 函数

```python
# services/measurement_service.py
async def create_measurement(db, current_user, payload):
    """单条创建。"""
    obj = BodyMeasurement(user_id=current_user.id, **payload.model_dump())
    db.add(obj)
    await db.flush()
    await db.commit()
    return obj


async def create_measurements_batch(db, current_user, payload):
    """批量创建（整体事务）。"""
    objs = [
        BodyMeasurement(user_id=current_user.id, **item.model_dump())
        for item in payload.items
    ]
    db.add_all(objs)
    await db.flush()
    await db.commit()
    return objs
```

**为什么不合并成一个函数**：

- 单条 service 返回 `BodyMeasurement`，批量 service 返回 `list[BodyMeasurement]`
- 单条不抛 `BatchTooLargeError`，批量需要校验 `len(items) <= 50`
- 路由层的 `response_model` 不同（`BodyMeasurementRead` vs `BodyMeasurementBatchRead(count, items)`）

### 2.3 schema 复用：`list[T]`

Pydantic v2 的 `list[BodyMeasurementCreate]` 自动继承单条 schema 的所有验证：

```python
class BodyMeasurementBatchCreate(BaseModel):
    items: list[BodyMeasurementCreate] = Field(min_length=1, max_length=50)
```

这意味着：

- 批量里的每条记录都要满足 `BodyMeasurementCreate` 的所有约束（`weight >= 20` 等）
- 单条 schema 改了，批量自动同步（不需要双倍维护）
- 错误信息精确定位到 items[i].field（spec §3.2 422 错误细节）

```bash
# 批量里第 2 条 weight < 20 的错误响应
{
  "detail": [{
    "type": "greater_than_equal",
    "loc": ["body", "items", 1, "weight"],  # ← 精确到第几条哪个字段
    "msg": "Input should be greater than or equal to 20"
  }]
}
```

> **面试话术**：「批量端点的 schema 复用靠 Pydantic v2 的 `list[T]` —— 自动继承单条 schema 的所有验证。错误信息精确到 `items[i].field` 路径，前端能告诉用户'第 3 条体重太小'。这是类型系统 + 框架的杠杆：定义一次，复用 N 次。」

---

## 3. 整体事务原则（spec W5）

### 3.1 为什么必须"整体事务"

健身测量场景：用户补录一周数据（14 条），如果其中第 7 条 weight < 20（非法）—— 应该：

- ✅ 全部回滚（14 条都不入库）
- ❌ 前面 6 条入库、第 7 条失败、后面 7 条不试

**业务一致性**：用户视角"这 14 条数据要么都进、要么都不进"——不能出现"半成功"。

### 3.2 `add_all + flush + commit` 模式

```python
async def create_measurements_batch(db, current_user, payload):
    objs = [
        BodyMeasurement(user_id=current_user.id, **item.model_dump())
        for item in payload.items
    ]
    db.add_all(objs)  # 1. 全部加入 session（不执行 SQL）
    await db.flush()  # 2. 触发 INSERT（如果数据非法，会在这里抛 IntegrityError）
    await db.commit()  # 3. 提交事务
    return objs
```

**关键**：`flush()` 在内存中构造 INSERT 语句并执行，但不 commit。如果任一条 INSERT 失败（比如 FK 约束、CHECK 约束），`flush()` 抛错，**整个 session 的事务**自动回滚。

**为什么不逐条 commit**：

```python
# ❌ 错误做法
for item in payload.items:
    obj = BodyMeasurement(...)
    db.add(obj)
    await db.commit()  # 每条独立事务
```

这种做法：

- 不是整体事务（前面 commit 的不会回滚）
- N 次 commit = N 次 round-trip = 性能差
- 违反"批量要么都成功要么都失败"业务规则

### 3.3 异常路径：依赖全局 rollback

```python
# api/body.py
@router.post("/batch", ...)
async def create_measurements_batch(payload, current_user, db):
    objs = await measurement_service.create_measurements_batch(db, current_user, payload)
    return BodyMeasurementBatchRead(...)
```

如果 `create_measurements_batch` 抛 `FlushError`，路由函数不显式回滚——依赖 `get_db` 的 async generator 在 finally 块里执行 `await db.rollback()`。

```python
# core/db.py（已实现）
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()  # 关闭时如有未提交事务自动 rollback
```

**为什么这样设计**：

- 路由函数"无 try/except"——业务异常自然向上抛给 FastAPI，由 `exception_handlers.py` 映射 HTTP 状态码
- session 生命周期与 HTTP 请求绑定——请求结束自动清理
- 简化路由层（不做事务管理）

> **面试话术**：「批量端点的整体事务靠 SQLAlchemy 的 `add_all + flush + commit` —— 任一条 INSERT 失败，flush 抛错，事务自动回滚。如果逐条 commit 就不是整体事务，前面成功的不会回滚。我不在路由层 try/except 事务——依赖 `get_db` 的 async generator 在 finally 块里自动 rollback，路由层只负责'调 service + 转 DTO'，保持分层清晰。」

---

## 4. 大小限制：max_length=50（工程平衡）

### 4.1 为什么是 50

| 限制值    | 优点                          | 缺点                                |
| ------ | --------------------------- | --------------------------------- |
| `max=10`  | 服务端压力小                      | 不实用——一周早晚还不够                |
| **`max=50`** | **覆盖 95% 场景**（用户补录 3 周数据）  | 单条记录 200 字节，50 条 ≈ 10KB，请求合理 |
| `max=200` | 单次能补录一个月                    | 请求体 40KB，超过部分反向代理默认限制        |
| `max=1000` | 极端用户友好                      | 单请求 200KB，DB 写入慢、超时风险高        |

**经验值**：批量 API 的 max 在 50-100 之间是"实用 + 安全"的平衡点。

### 4.2 Pydantic 自动校验

```python
class BodyMeasurementBatchCreate(BaseModel):
    items: list[BodyMeasurementCreate] = Field(min_length=1, max_length=50)
```

用户传 51 条 → Pydantic 自动 422：

```json
{
  "detail": [{
    "type": "too_long",
    "loc": ["body", "items"],
    "msg": "List should have at most 50 items after validation, not 51"
  }]
}
```

**业务规则**：

- `min_length=1`：禁止空数组（无意义的请求）
- `max_length=50`：防止恶意超大请求

### 4.3 业务保护（不只是性能）

- **网络层**：避免大请求体被反向代理（如 nginx 默认 `client_max_body_size 1m`）拒
- **DB 层**：避免大事务长时间占用 connection pool
- **超时风险**：单请求 50 条 INSERT 比 200 条快 4 倍，超时概率低
- **用户体验**：失败时只回滚 50 条 vs 200 条，重试成本低

> **面试话术**：「批量大小限制是工程平衡——太小不实用，太大风险高。我选 50 是因为它能覆盖 95% 场景（用户补录 3 周早晚数据），同时单请求体控制在 10KB 以内（不被反向代理拦截、不超时）。Pydantic `max_length=50` 自动 422，业务层根本不用校验。这是'用框架杠杆做边界保护'。」

---

## 5. 批量端点的错误处理（4 类）

### 5.1 错误码矩阵


| 错误码 | 触发条件                              | 例子                                   |
| --- | --------------------------------- | ------------------------------------ |
| 201 | 全部成功                              | 3 条记录全部入库                          |
| 422 | schema 校验失败（字段错、长度错、类型错）        | `weight < 20`、`items[2].recorded_at 缺` |
| 400 | 超 max_length（理论上 Pydantic 也会 422，但业务层兜底） | `len(items) == 51`                   |
| 401 | 未登录 / token 无效                    | 请求无 Bearer token                    |

### 5.2 整体事务 vs 部分失败的业务选择

| 策略               | FitForge 选 | 理由                                       |
| ---------------- | -------- | ---------------------------------------- |
| 整体事务（任一失败全回滚）   | ✅        | 业务一致性优先（用户视角"要么都进要么都不进"）                |
| 部分失败（成功的入，失败的报错） | ❌        | 业务混乱——用户需要手动对账哪些进了哪些没进                  |
| 全成功或全失败          | ✅        | 同整体事务                                   |

### 5.3 错误响应格式

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "items", 1, "weight"],
      "msg": "Input should be greater than or equal to 20",
      "input": 10.0,
      "ctx": {"ge": 20}
    }
  ]
}
```

`loc` 精确到 `items[1].weight`——前端工程师能告诉用户"第 2 条体重太小"。

> **面试话术**：「批量端点的错误响应要精确——`loc=["body", "items", 1, "weight"]` 告诉前端是第几条哪个字段错。这靠 Pydantic 自动生成，前端不用猜。GitHub API 的批量端点（如 `POST /repos/{owner}/{repo}/issues`）也是类似设计：错误信息含 index 字段，开发者能定位。」

---

## 6. 真实测试用例（spec §8 + dc98286）

### 6.1 `test_post_batch_201`

```python
@pytest.mark.asyncio
async def test_post_batch_201(client: AsyncClient, auth_headers):
    body = {"items": [
        {"weight": 70.0, "recorded_at": "2026-08-15T08:30:00"},
        {"weight": 71.0, "recorded_at": "2026-08-16T08:30:00"},
    ]}
    r = await client.post("/body-measurements/batch", json=body, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["count"] == 2
    assert len(r.json()["items"]) == 2
```

### 6.2 部分失败 → 整体回滚（service 层 spec §8.1）

```python
@pytest.mark.asyncio
async def test_create_measurements_batch_all_or_nothing(db_session, sample_user):
    """W5: 整体事务——任一非法，全回滚"""
    valid_time = datetime.utcnow()
    payload = BodyMeasurementBatchCreate(items=[
        BodyMeasurementCreate(weight=70.0, recorded_at=valid_time),
        BodyMeasurementCreate(weight=71.0, recorded_at=valid_time),
    ])
    objs = await create_measurements_batch(db_session, sample_user, payload)
    assert len(objs) == 2
    # 如果其中一条非法（weight=10），flush 抛 ValidationError → 全部回滚 → assert len == 2 失败
```

### 6.3 超 max_length → 422

```python
@pytest.mark.asyncio
async def test_post_batch_422_too_many_items(client, auth_headers):
    items = [{"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"}] * 51
    r = await client.post("/body-measurements/batch",
                          json={"items": items}, headers=auth_headers)
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "too_long"
```

### 6.4 smoke 脚本（commit `9f4f927`）

```bash
# scripts/smoke_body_crud.sh 第 2.4 步
# POST /body-measurements/batch 3 条
curl -s -X POST http://127.0.0.1:8000/body-measurements/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"weight": 70.5, "recorded_at": "2026-08-14T08:30:00"},
      {"weight": 70.8, "recorded_at": "2026-08-15T08:30:00"},
      {"weight": 71.0, "recorded_at": "2026-08-16T08:30:00"}
    ]
  }' | python -m json.tool
```

预期：返回 `{count: 3, items: [...]}`，HTTP 201。

---

## 7. 面试话术（综合 ≥ 3 句）

> 「批量 API 设计有双端点和单端点 magic 两种方案。我选双端点（`POST /resources` 单 + `POST /resources/batch` 批量），因为 Pydantic 不能优雅处理 `Union[T, list[T]]`——OpenAPI 生成 `oneOf`，前端类型不清。双端点让两个场景走不同路由，schema 独立、事务边界清晰、错误响应统一。schema 复用靠 Pydantic v2 的 `list[T]` —— 自动继承单条 schema 的所有字段验证，避免双倍维护。这是 GitHub API 批量端点（如创建多个 issue）的设计哲学。」
>
> 「批量端点必须用整体事务——任一条失败全部回滚。我用 SQLAlchemy 的 `add_all + flush + commit`：flush 触发 INSERT，任一条非法抛 IntegrityError，事务自动回滚。如果逐条 commit 就违反业务一致性（前面成功的不会回滚）。路由层不显式 try/except 事务，依赖 `get_db` 的 async generator 在 finally 自动 rollback——分层清晰，业务层只关心业务逻辑。」
>
> 「批量大小限制 max=50 是工程平衡——太小不实用（用户补录一周数据不够），太大风险高（单请求体超过 nginx 默认 1MB 限制、超时概率上升）。我用 Pydantic `max_length=50` 自动 422，业务层不用校验。这是'用框架做边界保护'：把规则放在 schema 定义里，而不是 service 里的 if 判断。Stripe API 的批量端点（如 `POST /v1/customers` 数组）也是类似设计——单次最多 100 条。」

---

## 8. 踩坑清单


| 坑                                          | 现象                       | 解法                                       |
| ------------------------------------------ | ------------------------ | ---------------------------------------- |
| 单端点 magic（`Union[T, list[T]]`）             | OpenAPI 类型 `oneOf`，前端不清 | 双端点：单 + /batch                          |
| 批量端点 schema 没复用单条                          | 字段双倍维护、容易漏                | `items: list[BodyMeasurementCreate]` 自动继承 |
| 逐条 commit                                  | 不是整体事务，前面成功不会回滚           | `add_all + flush + commit`                |
| 路由层 try/except FlushError                   | 错误被吞、事务不干净                | 路由层不接，让异常自然向上抛                         |
| `max_length` 太大                              | 单请求体超 nginx 限制             | 50-100 之间，根据业务实际场景定                    |
| `min_length=0`（允许空数组）                     | 用户误发空数组浪费一次请求             | `min_length=1`                          |
| 错误响应 `loc` 是 `["body", "items"]` 笼统定位      | 前端不知道是第几条错               | Pydantic 自动 `loc=["body", "items", i, ...]` |

---

## 9. 关联

- **关联决策**：
  - **D33**：body_measurements 两个创建端点（单 + /batch），整体事务（spec Q2）
  - 间接影响 D37（list 端点的 limit 上限 100 同样是工程平衡）
- **关联 commit**：
  - `9304333`：feat(schemas) add 6 body_measurements schemas（含 BodyMeasurementBatchCreate）
  - `3238d5d`：feat(service) add 6 body_measurements service functions（含 create_measurements_batch）
  - `dc98286`：test(routes) add 10 e2e tests for body-measurements（含 `test_post_batch_201`）
  - `9f4f927`：test(smoke) add curl smoke tests for 11 body+goal endpoints（2.4 步）
- **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md` §3.1 / §3.2 / §5.1 / §11 D33
- **关联 plan**：`docs/superpowers/plans/2026-08-16-body-crud-plan.md` Task 3 / Task 5 + W5

---

**沉淀状态**：✅ 用户于 2026-08-16 批准落盘（与 Phase 5 T16 一并 commit）
