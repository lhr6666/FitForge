# FitForge 业务异常体系沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：Q2（业务异常体系）、D19（6 决策）
> **关联 commit**：`a9eeed3`（plan Task 5）
> **目的**：面试前复习 + 异常体系设计原则

---

## 1. 为什么业务层抛异常而不是返回错误码？

### 1.1 两种设计哲学对比

```python
# ❌ Result 模式（Rust 风格）
async def register(db, user_create) -> tuple[bool, str]:
    if username_exists:
        return (False, "username_exists")
    # ... 业务逻辑
    return (True, "")

# 调用方：必须手动检查返回值
result = await register(db, user_create)
if not result[0]:
    return JSONResponse(409, {"detail": result[1]})
# ⚠️ 忘记检查 → bug 沉默！
```

```python
# ✅ 异常模式（Python 风格）
async def register(db, user_create) -> User:
    if username_exists:
        raise UsernameExistsError("username_exists")
    # ... 业务逻辑
    return user

# 调用方：异常会自动冒泡，业务代码极简
user = await register(db, user_create)
```

### 1.2 异常模式的 3 个核心优势

| 维度 | 异常模式 | Result 模式 |
|------|----------|------------|
| **自动冒泡** | ✅ 异常默认冒泡到 exception_handler | ⚠️ 调用方必须检查 |
| **调试信息** | ✅ Python 自动 traceback（行号 + 调用栈）| ⚠️ 只有错误码字符串 |
| **不可忽略** | ✅ 未处理会冒泡到顶层 | ❌ 忘记 return 就当成功 |

> **面试话术**：「我用异常而非 Result 模式，因为 ① Python 异常原生支持 try/except，调用者代码最简洁；② 业务异常与 HTTP 解耦——service 不知道 HTTP 存在，所以业务可复用（CLI/脚本/队列都直接调 service.register()）；③ Python traceback 自带行号和调用栈，调试速度比 Result 模式的字符串错误码快 10 倍。」

---

## 2. 异常继承体系：3 层兜底

### 2.1 继承图

```
Exception（Python 内置）
   └── FitForgeException（业务异常基类）    ← 第 1 层
         ├── UsernameExistsError          ← 路由层 catch → 409
         ├── EmailExistsError             ← 路由层 catch → 409
         └── 其他业务异常（未来）            ← 路由层 catch FitForgeException → 400
```

### 2.2 路由层 3 个 catch 的语义

```python
@app.exception_handler(UsernameExistsError)  # 具体异常 → 特定码
async def h1(request, exc):
    return JSONResponse(409, ...)

@app.exception_handler(FitForgeException)  # 基类 → 400（兜底业务异常）
async def h2(request, exc):
    return JSONResponse(400, ...)

@app.exception_handler(Exception)  # Python 内置 → 500（兜底所有未捕获）
async def h3(request, exc):
    return JSONResponse(500, ...)
```

### 2.3 为什么基类是关键的"批量兜底"

| 设计选择 | 路由层 handler 数量 | 维护成本 |
|----------|--------------------|---------|
| ❌ 直接继承 Exception | 10 个异常 = 10 个 handler | 高（每加一个异常要加 handler）|
| ✅ 继承 FitForgeException 基类 | 1 个 catch 兜底所有业务异常 | 低（加新异常自动走兜底）|

> **面试话术**：「我用自定义业务异常基类 FitForgeException 继承 Exception——这样路由层只需一个 catch FitForgeException 兜底映射 400，新加的业务异常自动走这个兜底，避免每个异常单独写 handler。这是'开闭原则'的应用：扩展业务异常（加新类）不需要改路由层（不用加 handler）。」

---

## 3. 为什么不用 Python 内置 ValueError？

| 选项 | 行为 | 问题 |
|------|------|------|
| **`raise ValueError`** | Python 内置 | ⚠️ FastAPI 默认 422，但语义混淆——ValueError 是程序错误，不是业务错误 |
| **`raise HTTPException(409, ...)`** | FastAPI 原生 | ⚠️ service 依赖 FastAPI，业务不可复用（CLI/队列用不了）|
| **`raise UsernameExistsError(...)`** | ✅ 自定义业务异常 | service 不知道 HTTP，路由层 handler 映射 409 |

### 3.1 ValueError 语义错位

```python
# ValueError 是 Python 表达"参数值不对"的内置异常
# 例如 int("abc") 抛 ValueError("invalid literal for int()")
# 这是程序 bug，不是用户输入问题
raise ValueError("username exists")  # 语义错位

# 业务异常 = 用户能感知的错误（注册失败、余额不足等）
# 用专属类表达，路由层针对性处理
raise UsernameExistsError("username 'alice' already exists")  # ✅ 语义正确
```

> **面试话术**：「我不复用 Python 内置 ValueError，也不直接 raise HTTPException——前者语义错（ValueError 是程序 bug 不是业务错误），后者破坏分层（service 依赖 FastAPI 不可复用）。我自建 FitForgeException 体系，service 抛业务异常不知道 HTTP，路由层 handler 负责映射——这是'分层 + 解耦'的双重保证。」

---

## 4. 重写 `__init__` 和 `__str__` 的小细节

```python
class FitForgeException(Exception):
    def __init__(self, message: str, *args: Any) -> None:
        super().__init__(message, *args)  # 父类初始化
        self.message = message            # 存为属性方便访问

    def __str__(self) -> str:
        return self.message                # print() 时输出 message
```

### 4.1 两个细节的好处

| 细节 | 默认行为 | 重写后 | 价值 |
|------|----------|--------|------|
| `__init__` 存 self.message | 父类只在 args 里存 | `exc.message` 可访问 | 业务代码不用 `parse str(exc)` |
| `__str__` 输出 message | `(ClassName, message)` 元组 | 字符串 `message` | 调试日志更友好 |

### 4.2 不重写也可以

- 不重写时，`print(异常对象)` 输出 `(ClassName, message)` 元组（Python 默认 Exception.__str__ 行为）
- 重写后输出 `message` 字符串——更友好

> **面试话术**：「重写 __init__ 把 message 存为 self.message——业务代码可以通过 `exc.message` 访问，不要 parse str(exc)。重写 __str__ 让 print() 友好——调试日志里直接输出 '用户名 alice 已被占用' 而不是 '(UsernameExistsError, 用户名 alice 已被占用)'。两个小细节让异常可读、可调试。」

---

## 5. IntegrityError（DB 层兜底）—— 它不属于业务异常

```python
from sqlalchemy.exc import IntegrityError

@app.exception_handler(IntegrityError)  # SQLAlchemy 自己的异常
async def integrity_error_handler(request, exc):
    return JSONResponse(409, {"detail": "数据冲突..."})
```

### 5.1 为什么把 IntegrityError 单独处理

- IntegrityError 是 SQLAlchemy 的——业务层不该 import SQLAlchemy
- 业务异常是 service 抛的，IntegrityError 是 DB 自动抛的
- **正确做法**：路由层单独 catch IntegrityError 兜底 409（处理"并发注册同 username"）

### 5.2 双层防御

| 层级 | 拦截率 | 处理 |
|------|--------|------|
| **应用层（service 查重）** | 99% | UsernameExistsError → 409 |
| **DB 层（UNIQUE 约束）** | 1% 兜底 | IntegrityError → 409 |

> **面试话术**：「DB 兜底 IntegrityError 跟业务异常是两回事——业务异常是 service 检查出的，IntegrityError 是 DB UNIQUE 约束抛出的（应对高并发竞争）。应用层 99% 拦截 + DB 层 1% 兜底，这就是'纵深防御'——单层防御总会被绕过。」

---

## 6. 面试 Q&A（5 题预演）

### Q1：为什么业务层抛异常不用返回错误码？

> "异常模式 3 个核心优势：① Python 异常原生 try/except，调用方代码最简洁；② 业务异常与 HTTP 解耦——service 不知道 HTTP 存在，业务可复用（CLI/脚本/队列都直接调 service.register()）；③ Python traceback 自带行号和调用栈，调试速度比 Result 模式的字符串错误码快 10 倍。"

### Q2：异常继承体系怎么设计？为什么用基类？

> "用 FitForgeException 基类继承 Exception，路由层一个 catch FitForgeException 兜底映射 400，新加的业务异常自动走这个兜底，避免每个异常单独写 handler。这是'开闭原则'的应用：扩展业务异常（加新类）不需要改路由层（不用加 handler）。"

### Q3：为什么不用 Python 内置 ValueError？

> "语义错位。ValueError 是 Python 表达'程序参数错'的内置异常（如 int('abc') 抛 ValueError），是程序 bug，不是用户输入问题。业务异常 = 用户能感知的错误（注册失败、余额不足等），用专属类表达，路由层针对性处理。"

### Q4：自定义异常的 __init__ 怎么写？重写 __str__ 有什么好处？

> "重写 __init__ 把 message 存为 self.message——业务代码可以通过 exc.message 访问，不要 parse str(exc)。重写 __str__ 让 print() 友好——调试日志里直接输出 message 字符串，而不是 '(ClassName, message)' 元组。两个小细节让异常可读、可调试。"

### Q5：IntegrityError 跟业务异常什么关系？

> "两层不同：业务异常是 service 检查出的（99% 拦截），IntegrityError 是 DB UNIQUE 约束抛出的（1% 兜底）。路由层都映射 409，但来源不同——service 不知道 SQLAlchemy 不抛 IntegrityError，DB 不知道业务逻辑不抛 UsernameExistsError。两层叠加是'纵深防御'。"

---

## 7. 踩坑清单

| 坑 | 现象 | 解法 |
|----|------|------|
| 业务异常不继承基类 | 路由层 catch 不到，500 错误 | 继承 FitForgeException |
| 业务异常继承 HTTPException | service 依赖 FastAPI，不可复用 | 自定义基类 |
| 异常太多不分组 | handler 数量爆炸 | 用 FitForgeException 基类 + 1 个 catch 兜底 |
| 异常 print 出来是元组 | 调试不友好 | 重写 __str__ |
| 业务异常 message 忘记存 | 业务代码要 parse str(exc) | 重写 __init__ 存 self.message |
| DB UNIQUE 冲突未处理 | 1% 漏报 500 | 路由层 catch IntegrityError 兜底 409 |

---

## 8. 参考资源

- [FastAPI exception handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Python Exception 文档](https://docs.python.org/3/tutorial/errors.html)
- [SQLAlchemy IntegrityError](https://docs.sqlalchemy.org/en/20/errors.html#sqlalchemy.exc.IntegrityError)
- [开闭原则 SOLID](https://en.wikipedia.org/wiki/Open%E2%80%93closed_principle)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘