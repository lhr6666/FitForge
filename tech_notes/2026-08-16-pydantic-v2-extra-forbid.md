# Pydantic v2 `ConfigDict(extra="forbid")` —— PATCH 端点的安全网

> **日期**：2026-08-16（周六补周五内容）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D34（measurements PATCH 仅 2 字段）+ D35（goals PATCH 5 字段）
> **关联 commit**：`9304333`（BodyMeasurementPatch）、`701869a`（UserGoalUpdate）、`dc98286`（W3 测试用例）、`db4e682`（user-goals 422 测试）
> **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md` §3.5 / §3.10 / §4.1
> **目的**：面试前复习 + 解释为什么 PATCH 端点必须用 `extra="forbid"`，以及与 `model_dump(exclude_unset=True)` 的协同

---

## 1. 三种 extra 模式对比（allow / ignore / forbid）

Pydantic v2 通过 `model_config = ConfigDict(extra=...)` 控制"模型未声明字段"遇到时的行为。一共有 3 种模式：


| 模式            | 未声明字段传了怎么办      | HTTP 后果       | 适用场景                |
| ------------- | --------------- | ------------- | ------------------- |
| `"allow"`     | 静默存入 `__pydantic_extra__` | 不报错（业务可见）    | 极少数需要"动态字段"的场景     |
| `"ignore"`（默认） | 静默丢弃            | 看起来成功，实际被吞   | 兼容性优先（前端老字段不会被拒）   |
| `"forbid"`    | 抛 `ValidationError` | FastAPI 自动 422 | **PATCH 端点（必须用）**   |

**Pydantic v1 vs v2 默认值差异**：

- v1 默认 `Extra.ignore`（与 v2 一致）
- v1 用 `class Config: extra = "forbid"`（类配置）
- v2 用 `model_config = ConfigDict(extra="forbid")`（字段配置）

> **面试话术**：「Pydantic 默认 `extra="ignore"`——前端多传字段被静默丢弃。这对 POST 创建可能无害，但对 PATCH 更新是灾难：业务想改 `notes`，但前端误把 `weight` 也塞进来，默认行为会'装作没看见'，最终 SQL 只更新了 notes，但日志/调试时极难排查。我用 `extra="forbid"` 让 Pydantic 在序列化阶段就 422 拒绝，'早 fail 早知道'。」

---

## 2. forbid 的两大用途

### 2.1 用途一：Schema 准确度（自我文档化）

当 `extra="forbid"` 打开后，Pydantic 把 schema 视为**白名单**：只允许列表上明确出现的字段。这个白名单本身就是"字段契约"，前端工程师看 OpenAPI 文档就能知道支持哪些字段，不用看后端代码。

```python
# ✅ 字段即契约
class BodyMeasurementPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notes: str | None = Field(default=None, max_length=1000)
    recorded_at: datetime | None = None

# 前端工程师看 Swagger UI 看到 2 个字段 —— 不可能误以为能改 weight
```

### 2.2 用途二：防字段误覆盖（业务安全）

业务上"客观测量数据不允许改"——体重/腰围/1RM 都是用户当时测的，事后改即造假。但前端工程师可能误以为 PATCH 是"万能更新"，传 `{weight: 999}` 试试看。**默认 ignore 会让 weight 假装"传了但没用"，但 SQL 实际是按 PATCH 字段白名单更新的**——日志混乱 + 用户疑惑 + 排查耗时。

```python
# ❌ 默认 ignore 行为（伪安全）
class BodyMeasurementPatch(BaseModel):
    notes: str | None = None
    recorded_at: datetime | None = None
# 用户传 {"notes": "x", "weight": 999}
# Pydantic 静默丢 weight，只取 notes
# SQL 更新只改 notes —— "我明明传了 weight 怎么没改？"

# ✅ forbid 行为（真安全）
class BodyMeasurementPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notes: str | None = None
    recorded_at: datetime | None = None
# 用户传 {"notes": "x", "weight": 999}
# Pydantic 422 + "Extra inputs are not permitted" + loc=["body", "weight"]
# 业务层根本看不到这个请求
```

> **面试话术**：「我用 `extra="forbid"` 做两层防御——schema 准确度（白名单即契约）+ 防字段误覆盖（业务上禁改的字段不会被前端误传静默吞掉）。这是'显式优于隐式'：让 422 错误替用户和工程师说'你做错了'，而不是静默装作没事。」

---

## 3. FitForge 的具体应用

### 3.1 `BodyMeasurementPatch`（D34 决策）

业务规则（spec §3.5 + Q3）：**只允许改 `notes` + `recorded_at`**，因为体重/腰围/1RM 是客观测量值，事后改即造假。

```python
# schemas/measurement.py
class BodyMeasurementPatch(BaseModel):
    """PATCH /body-measurements/{id} 入参（Q3：仅 notes + recorded_at）"""
    model_config = ConfigDict(extra="forbid")  # W3：拒额外字段
    notes: str | None = Field(default=None, max_length=1000)
    recorded_at: datetime | None = None
```

### 3.2 `UserGoalUpdate`（D35 决策）

业务规则（spec §3.10 + Q4）：**允许改 5 个字段**（type / target_value / status / deadline / notes），但**不允许改 user_id / id / created_at / updated_at**——因为这些字段不应该由客户端控制。

```python
# schemas/goal.py
class UserGoalUpdate(BaseModel):
    """PATCH /user-goals/{id} 入参（Q4：5 字段）"""
    model_config = ConfigDict(extra="forbid")  # W3：拒 user_id 等
    type: GOAL_TYPE | None = None
    target_value: float | None = Field(default=None, ge=0, le=1000)
    status: GOAL_STATUS | None = None
    deadline: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
```

**为什么不实现成"全字段 update"**：

- `user_id` 永远从 token 取（防止越权改他人 goal）
- `id` 是主键，由 DB 生成
- `created_at` / `updated_at` 系统自动管理

这 4 个字段不进 PATCH schema + `extra="forbid"` 兜底——双层防御。

### 3.3 错误场景示例

**场景 A**：前端误传 `weight` 想改体重。

```bash
curl -X PATCH http://127.0.0.1:8000/body-measurements/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"weight": 999.0, "notes": "上午测的"}'
```

响应：

```json
{
  "detail": [
    {
      "type": "extra_forbidden",
      "loc": ["body", "weight"],
      "msg": "Extra inputs are not permitted",
      "input": 999.0
    }
  ]
}
```
HTTP 422。业务层完全看不到这个请求。

**场景 B**：前端想改他人 goal（传 `user_id`）。

```bash
curl -X PATCH http://127.0.0.1:8000/user-goals/123 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 999, "status": "completed"}'
```

响应：422 + `loc=["body", "user_id"]`。**比 service 层校验更早 fail**——Pydantic 在反序列化阶段就拒，service 根本看不到这个 request。

---

## 4. `extra="forbid"` 与 `model_dump(exclude_unset=True)` 的协同

这是 PATCH 端点的**核心两件套**：forbid 管"传错"，exclude_unset 管"传对但没传"。

### 4.1 PATCH 的两种"不动"

| 用户行为                  | forbid 行为     | exclude_unset 行为 | 最终结果              |
| --------------------- | ------------- | ---------------- | ----------------- |
| 不传任何字段                 | 接受（无额外字段要 forbid） | dump 出空 dict       | SQL 不更新（无变化）      |
| 只传 `notes`            | 接受            | dump 出 `{notes}`    | SQL 只更新 `notes`    |
| 传 `notes + recorded_at` | 接受            | dump 出 2 个字段       | SQL 更新这 2 个字段     |
| 误传 `weight`            | **422 拒绝**   | 不触发（请求被拒了）       | 业务层看不到             |

### 4.2 service 层 `exclude_unset` 用法

```python
# services/measurement_service.py
async def patch_measurement(
    db: AsyncSession,
    current_user: User,
    measurement_id: int,
    patch: BodyMeasurementPatch,
) -> BodyMeasurement:
    obj = await get_measurement(db, current_user, measurement_id)  # 自动验权
    update_data = patch.model_dump(exclude_unset=True)  # 仅取显式传的字段
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj
```

**关键点**：

- `model_dump()` 会把所有字段都含（含默认值 `None`）—— 可能误清空已有数据
- `model_dump(exclude_unset=True)` 只取**用户显式传了的字段**——这是 PATCH 语义的正确实现
- 与 `extra="forbid"` 协同：forbid 在序列化前拒错，exclude_unset 在序列化时筛字段

### 4.3 三种 dump 方式对比


| 方式                                          | 包含默认值的字段？    | PATCH 适用？           |
| ------------------------------------------- | ------------ | ------------------- |
| `model_dump()`                              | ✅ 含（None 也是值） | ❌ 可能清空已有数据          |
| `model_dump(exclude_none=True)`             | ❌ 排除 None     | ⚠️ 不传 = 不改，但传 None = 不改（与设计冲突） |
| **`model_dump(exclude_unset=True)`**        | ❌ 只含显式传的      | ✅ **PATCH 黄金标准**    |

> **面试话术**：「PATCH 端点的'两件套'——`extra="forbid"` 防传错（422 拒绝额外字段），`exclude_unset=True` 防传漏（只更新用户显式传的字段）。前者是入口校验，后者是出口语义。两件缺一：如果没有 forbid，前端误传 weight 会被静默吞；如果没有 exclude_unset，前端不传字段会被默认 None 清空已有数据。这是 Pydantic v2 给 PATCH 端点的'完整体检'。」

---

## 5. 真实测试用例（spec §8.2）

### 5.1 `test_patch_measurement_422_extra_field`（dc98286）

```python
@pytest.mark.asyncio
async def test_patch_measurement_422_extra_field(
    client: AsyncClient, auth_headers
):
    """W3: extra="forbid" 必须拒 weight 等不允许 update 的字段"""
    created = (await client.post(
        "/body-measurements",
        json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"},
        headers=auth_headers,
    )).json()
    r = await client.patch(
        f"/body-measurements/{created['id']}",
        json={"weight": 999.0, "notes": "x"},
        headers=auth_headers,
    )
    assert r.status_code == 422
    # 进一步断言 loc 和 type
    detail = r.json()["detail"][0]
    assert detail["loc"] == ["body", "weight"]
    assert detail["type"] == "extra_forbidden"
```

### 5.2 `test_patch_goal_422_extra_field`（db4e682）

```python
@pytest.mark.asyncio
async def test_patch_goal_422_extra_field(
    client: AsyncClient, auth_headers
):
    """W3: extra="forbid" 必须拒 user_id"""
    created = (await client.post(
        "/user-goals",
        json={"type": "cut"},
        headers=auth_headers,
    )).json()
    r = await client.patch(
        f"/user-goals/{created['id']}",
        json={"user_id": 999},
        headers=auth_headers,
    )
    assert r.status_code == 422
```

### 5.3 完整测试矩阵


| 测试用例                                  | 期望状态码 | 触发原因                  |
| ------------------------------------- | ----- | --------------------- |
| `test_patch_measurement_notes`        | 200   | 只传 `notes`（合法 PATCH）    |
| `test_patch_measurement_422_extra_field` | 422   | 传 `weight`（forbid 拒绝）   |
| `test_patch_goal_status_to_completed` | 200   | 只传 `status`（合法 PATCH）    |
| `test_patch_goal_422_extra_field`     | 422   | 传 `user_id`（forbid 拒绝）   |
| `test_patch_measurement_401_no_auth`  | 401   | 无 token（鉴权前置）          |

---

## 6. 面试话术（综合 ≥ 3 句）

> 「PATCH 端点必须用 `extra="forbid"`，否则前端误传字段会被 Pydantic 默认 ignore 静默吞掉，业务层装作'成功'但实际什么都没改。我项目里 BodyMeasurementPatch（spec §4.1）和 UserGoalUpdate（spec §4.2）都用 forbid：业务上'客观测量数据不能改'或'用户主键不能改'的字段，统统由 forbid 在入口就拒绝，422 返回错误细节让前端立刻知道错在哪。」
>
> 「forbid + `exclude_unset=True` 是 PATCH 的黄金组合——前者防传错，后者防传漏。如果只有 forbid 没有 exclude_unset，用户不传的字段会被默认值（None）覆盖；如果只有 exclude_unset 没有 forbid，用户传的非法字段会被静默吞。两个一起用：传错 → 422，传对但没传 → 不动。」
>
> 「业界最佳实践：所有 PATCH 端点都加 forbid；POST 端点可加可不加（取决于业务是否需要严格 schema）。GitHub API 的 PATCH 端点（如 update issue）就是用类似机制——传错字段直接 422 而不是静默接受。」

---

## 7. 踩坑清单


| 坑                                       | 现象                       | 解法                                                 |
| --------------------------------------- | ------------------------ | -------------------------------------------------- |
| PATCH 端点没用 forbid                      | 前端误传字段被静默吞 + SQL 看起来"成功"  | 所有 PATCH schema 加 `extra="forbid"`                  |
| 用 `model_dump()` 不带 exclude_unset       | 用户不传的字段被 None 覆盖           | 改用 `model_dump(exclude_unset=True)`                 |
| PUT 端点误用 forbid                        | 前端必传全部字段也会被拒              | PUT（整体替换）不该用 forbid；PATCH（部分更新）必须用 forbid         |
| 在路由层 try/except ValidationError        | 422 不返回，错误被吞              | 别拦截 ValidationError，让 FastAPI 自动处理                |
| 错误响应 `loc` 是 `["body", "weight"]`     | 前端工程师看不懂                 | 在 OpenAPI 文档说明 + 前端做错误展示                          |

---

## 8. 关联

- **关联决策**：
  - **D34**：measurements PATCH 仅允许 `notes` + `recorded_at`（spec Q3）
  - **D35**：goals PATCH 允许 5 字段（type / target_value / status / deadline / notes），不含 user_id/id/time（spec Q4）
- **关联 commit**：
  - `9304333`：feat(schemas) add 6 body_measurements schemas（含 BodyMeasurementPatch）
  - `701869a`：feat(schemas) add 4 user_goals schemas（含 UserGoalUpdate）
  - `dc98286`：test(routes) add 10 e2e tests for body-measurements（含 `test_patch_measurement_422_extra_field`）
  - `db4e682`：test(routes) add 7 e2e tests for user-goals（含 `test_patch_goal_422_extra_field`）
- **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md` §3.5 / §3.10 / §4.1 / §4.2 / W3
- **关联 plan**：`docs/superpowers/plans/2026-08-16-body-crud-plan.md` Task 3 / Task 4 + W3

---

**沉淀状态**：✅ 用户于 2026-08-16 批准落盘（与 Phase 5 T16 一并 commit）
