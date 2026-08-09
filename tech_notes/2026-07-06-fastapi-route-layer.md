# FastAPI 路由层沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：Q1-Q4（service/exception/schema/depends）、Q19（6 决策）
> **关联 commit**：`0cab349`（Task 17）、`b0002bc`（Task 18）
> **目的**：面试前复习 + FastAPI 路由层工程原则

---

## 1. APIRouter 模块化（spec §3.2）

```python
# api/auth.py
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", ...)
async def register(...): ...
```

```python
# main.py
app.include_router(auth_router)  # 挂载到主应用
```

### 1.1 4 个核心好处

| 好处 | 说明 |
|------|------|
| **模块化** | 每个文件管自己的路由组（auth.py、body.py、goal.py）|
| **prefix** | 统一 URL 前缀（`/auth/register`、`/auth/login`）|
| **tags** | OpenAPI 自动分组（Swagger UI 显示 "auth" 标签页）|
| **解耦** | main.py 只负责挂载，路由定义分散到各文件 |

### 1.2 与 Django urls.py 的对比

| Django | FastAPI |
|--------|---------|
| `urls.py` 里手写 urlpatterns | `api_xxx.py` 里 `APIRouter()` |
| `include()` 引用子模块 | `app.include_router(router)` |
| 无 tags 概念（要 drf-yasg 扩展）| `tags=["auth"]` 自动分组 |

> **面试话术**：「FastAPI 用 APIRouter 模块化路由——每个文件管自己路由组的 prefix + tags，main.py 统一 include_router。这跟 Django 的 urls.py include 类似，但 FastAPI 还自动生成 OpenAPI tags 分组，前端工程师看 Swagger UI 一目了然。」

---

## 2. Depends 注入 session（Q3）

```python
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),  # ← 关键
) -> UserRead:
    user = await auth_service.register(db, user_create)
```

### 2.1 Depends 4 步生命周期

```
1. 路由函数被调用
   ↓
2. FastAPI 检查参数 db: AsyncSession = Depends(get_db)
   ↓
3. FastAPI 调用 get_db() async generator
   ↓ yield session（路由函数开始执行）
4. 路由函数执行 await auth_service.register(db, ...)
   ↓
   yield 结束（路由函数返回）
   ↓
5. async with 自动关闭 session
```

### 2.2 为什么必须用 async generator

```python
# ❌ 普通函数：无法在 finally 里 close
async def get_db() -> AsyncSession:
    session = AsyncSessionLocal()
    return session  # 没有 finally 关闭！连接泄漏！

# ✅ async generator：yield 暂停后能执行 finally
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # 路由函数结束后才执行这里
            ...
```

### 2.3 单元测试 override Depends

```python
# 测试时可以替换 Depends
from main import app
from core.db import get_db

async def fake_get_db():
    yield test_session

app.dependency_overrides[get_db] = fake_get_db
```

> **面试话术**：「Depends(get_db) 让 session 生命周期与 HTTP 请求绑定——每个请求独立 session，路由函数执行完自动关闭。这是 FastAPI 推荐的依赖注入模式，比'中间件 + request.state.db'显式 10 倍。测试时用 dependency_overrides 替换，更可控。」

---

## 3. ORM → DTO 转换（Q4）

```python
user = await auth_service.register(db, user_create)  # ORM 对象（含 password_hash）
return UserRead.model_validate(user)  # Pydantic 实例（无 password_hash）
```

### 3.1 白名单 vs 黑名单

```python
# ❌ 黑名单：手动删字段
class UserRead(BaseModel):
    id: int
    username: str
    # 业务代码里写 .__dict__ 删 password_hash（脆弱）

# ✅ 白名单：只定义要返回的字段
class UserRead(BaseModel):
    id: int
    username: str
    nickname: str | None
    # password_hash 不定义 → 自动过滤
```

### 3.2 ORM → Pydantic 转换

```python
# ORM 对象（user 类） -> Pydantic DTO
db_user = await db.execute(select(User))  # SQLAlchemy 返回 User 对象
user_read = UserRead.model_validate(db_user.scalar_one())  # Pydantic 自动转
```

`from_attributes=True` 让 Pydantic 用 `getattr(obj, "field_name")` 而不是 `obj["field_name"]`。

> **面试话术**：「service 返回 ORM 对象，路由用 UserRead.model_validate() 转 DTO——白名单过滤敏感字段。这比黑名单'handler 里手动删 password_hash'安全 10 倍：加新敏感字段也只需在 ORM 加，不在 UserRead 加就自动不返回。」

---

## 4. status_code=201（RESTful 语义）

```python
@router.post("/register", status_code=status.HTTP_201_CREATED, ...)
```

| HTTP 状态码 | 语义 | 适用 |
|------------|------|------|
| 200 OK | 成功 | GET / PUT / PATCH |
| **201 Created** | **创建成功** | **POST（创建资源）** |
| 204 No Content | 成功无 body | DELETE |
| 400 Bad Request | 请求参数错误 | 任意 |
| 409 Conflict | 资源冲突 | POST（重复）|
| 422 Unprocessable Entity | Pydantic 校验失败 | POST/PUT |
| 500 Internal Server Error | 服务器异常 | 任意 |

> **面试话术**：「POST 创建资源用 201 不是 200——这是 RESTful 标准。客户端可以靠状态码区分'创建成功（201）'和'更新成功（200）'，不用读 body 判断。我用 status_code=status.HTTP_201_CREATED 明确意图，Swagger UI 自动显示 '201' 在响应列表里。」

---

## 5. summary + description 自动 OpenAPI

```python
@router.post(
    "/register",
    summary="用户注册",
    description="Q4: 极简响应体（不含 password_hash），Q6: email 必填，Q5: 密码强度校验",
)
```

Swagger UI 自动显示这些文字给前端工程师——这是**API 自文档化**。

> **面试话术**：「FastAPI 把 docstring + summary + description 自动转 OpenAPI 文档——前端直接看 Swagger UI，不用找后端问字段。这是'API 自文档化'的体现，比手写 OpenAPI 注解省一半工作。」

---

## 6. exception_handlers 注册时机

```python
# main.py 启动时一次性注册
app = FastAPI(...)
register_exception_handlers(app)  # 4 个业务异常 → 状态码
app.include_router(auth_router)
```

### 6.1 为什么在 app 创建后立即注册

- `app.add_exception_handler()` 必须有 app 实例
- 路由层才能 catch 业务异常 → 409 等
- **不能在路由层内注册**（已经创建完了）

### 6.2 exception_handlers.py 的 4 个映射

```python
@app.exception_handler(UsernameExistsError) -> 409
@app.exception_handler(EmailExistsError) -> 409
@app.exception_handler(IntegrityError) -> 409 (DB 层兜底)
@app.exception_handler(FitForgeException) -> 400 (兜底)
```

### 6.3 3 层兜底链

```
service 抛业务异常
   ↓
路由层注册 handler 捕获
   ├ 具体子类（UsernameExistsError）→ 409
   ├ FitForgeException 基类 → 400
   └ Exception (FastAPI 默认) → 500
```

> **面试话术**：「业务异常 handler 在 main.py 启动时一次性注册到 app 上——这样路由层抛业务异常时 FastAPI 自动捕获、映射状态码。这跟 Django middleware 的概念类似，但 FastAPI 用装饰器更优雅。3 层兜底链：具体异常→409，业务基类→400，未捕获→500。」

---

## 7. 路由列表（app.routes）

```
['GET', 'HEAD'] /openapi.json              # FastAPI 自动
['GET', 'HEAD'] /docs                       # Swagger UI（自动）
['GET', 'HEAD'] /docs/oauth2-redirect      # OAuth2（自动）
['GET', 'HEAD'] /redoc                      # ReDoc（自动）
['POST'] /auth/register                     # 我们挂载的 ✅
['GET'] /                                   # 健康检查
['GET'] /health                             # K8s 健康检查
```

7 个路由 = **4 个 FastAPI 默认 + 3 个我们**。

---

## 8. app.include_router vs @app.post 直接挂载

```python
# 方案 A：APIRouter 模块化（推荐）
router = APIRouter(prefix="/auth", tags=["auth"])
@router.post("/register", ...)
# main.py: app.include_router(router)

# 方案 B：直接在 app 上定义（不推荐）
@app.post("/auth/register", ...)
```

**为什么 A 更好**：
- A：路由定义分散到各文件，main.py 干净
- B：所有路由挤在 main.py，单文件难维护

> **面试话术**：「APIRouter 是 FastAPI 模块化的核心——路由定义分散到各文件（auth.py、body.py、goal.py），main.py 只负责挂载。我项目里 30+ 路由也只占 main.py 20 行代码。」

---

## 9. 面试 Q&A（6 题预演）

### Q1：FastAPI vs Flask 路由区别？

> "Flask 用装饰器 `@app.route('/path')` 直接挂载到 app，FastAPI 推荐用 APIRouter 模块化。FastAPI 自动生成 OpenAPI 文档，Flask 要装 flask-restx 才有类似功能。FastAPI 内置 async 支持，Flask 2.0 才有但生态不成熟。」

### Q2：APIRouter 怎么用？

> "创建 `router = APIRouter(prefix='/auth', tags=['auth'])`，在 router 上定义路由，主应用 `app.include_router(router)` 挂载。prefix 给所有路由加统一前缀，tags 让 Swagger UI 自动分组。」

### Q3：Depends(get_db) 怎么工作？

> "FastAPI 调 get_db() async generator，yield session 给路由函数。路由函数执行完，generator 的 finally 关 session。整个生命周期与 HTTP 请求绑定——天然隔离并发。测试时用 dependency_overrides 替换，更可控。」

### Q4：ORM → DTO 转换怎么做？

> "service 返回 ORM 对象（含 password_hash），路由用 UserRead.model_validate() 转 DTO（无 password_hash）。这是'白名单'设计：UserRead 只定义要返回的字段，敏感字段自动不返回。比黑名单'手动删字段'安全 10 倍。」

### Q5：status_code=201 是什么意思？

> "RESTful 标准——POST 创建资源用 201 Created，不是 200 OK。客户端可以靠状态码区分创建成功（201）和更新成功（200），不用读 body 判断。FastAPI 用 status_code=status.HTTP_201_CREATED 明确意图，Swagger UI 自动显示 '201' 在响应列表里。」

### Q6：异常 handler 怎么注册？

> "在 main.py 创建 app 后立即 `register_exception_handlers(app)` 注册。业务异常（如 UsernameExistsError）抛到 FastAPI 时自动捕获，映射到 HTTP 状态码（如 409）。3 层兜底：具体子类→409，业务基类→400，未捕获→500。」

---

## 10. 踩坑清单

| 坑 | 现象 | 解法 |
|----|------|------|
| 路由没出现 | 忘了 `app.include_router(router)` | main.py 挂载 |
| prefix 写错 | `/auth/register` 实际是 `/api/auth/register` | 检查 APIRouter(prefix=...) |
| tags 没分组 | Swagger UI 所有路由混在一起 | 加 tags=["auth"] |
| 422 vs 400 混淆 | 校验失败统一返回 400 | Pydantic 422（默认），业务异常 400 |
| Depends 不生效 | get_db 没异步 generator | 用 `async def` + `yield` |
| 测试不通过 | 真 DB 干扰测试 | 用 dependency_overrides 替换 |
| exception_handler 不触发 | 异常类型不匹配 | 确认 handler 注册的是 exception 类，不是 instance |

---

## 11. 参考资源

- [FastAPI 路由文档](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [FastAPI Depends 依赖注入](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI 异常处理](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [FastAPI response_model](https://fastapi.tiangolo.com/tutorial/response-model/)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘