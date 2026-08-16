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
#Result 模式 的函数返回的是一个元组
if not result[0]:
# 位置 0: False (表示失败)
# 位置 1: "username_exists" (表示原因)
    return JSONResponse(409, {"detail": result[1]})
# ⚠️ 忘记检查 → bug 沉默！也就是  # 程序员忘了写 if not result[0]...程序继续往下跑，以为注册成功了 user_id = result[1].id  # 报错！或者更糟：把错误字符串当用户ID用了
```

```python
# ✅ 异常模式（Python 风格）
async def register(db, user_create) -> User:#-> User：承诺这个函数如果成功，一定会返回一个 User 对象。
    if username_exists:
        raise UsernameExistsError("username_exists")
    # ... 业务逻辑
    return user

# 异常模就是所有问题都直接发送到上层来统一解决
#由路由层统一拦截处理这个同样问题的报错进行返回
user = await register(db, user_create)#await：这是一个切点。意思是“这一行要等结果，现在你可以切走去干别的事了，等结果好了再叫我回来”。
```

### 1.2 异常模式的 3 个核心优势


| 维度       | 异常模式                            | Result 模式        |
| -------- | ------------------------------- | ---------------- |
| **自动冒泡** | ✅ 异常默认冒泡到 exception_handler     | ⚠️ 调用方必须检查       |
| **调试信息** | ✅ Python 自动 traceback（行号 + 调用栈） | ⚠️ 只有错误码字符串      |
| **不可忽略** | ✅ 未处理会冒泡到顶层                     | ❌ 忘记 return 就当成功 |


> **面试话术**：「我用异常而非 Result 模式，因为 ① Python 异常原生支持 try/except，调用者代码最简洁；② 业务异常与 HTTP 解耦——service 不知道 HTTP 存在，所以业务可复用（CLI/脚本/队列都直接调 service.register()）；③ Python traceback 自带行号和调用栈，调试速度比 Result 模式的字符串错误码快 10 倍。」

---

## 2. 异常继承体系：3 层兜底

### 2.1 继承图

```
Exception（Python 内置）
   └── FitForgeException（业务异常基类）    ← 第 1 层
         ├── UsernameExistsError          ← 路由层 catch → 409
         ├── EmailExistsError             ← 路由层 catch → 409
         └── 其他业务异常（没有设定专门的异常子类但又属于这个基类的异常） ← 路由层 catch FitForgeException → 400
```

### 2.2 路由层 3 个 catch 的语义

```python
@app.exception_handler(UsernameExistsError)  # 具体异常 → 特定码
async def h1(request, exc):
    return JSONResponse(409, ...)

@app.exception_handler(FitForgeException)  # 基类 → 400（兜底业务异常，也就是属于这个基类但又没有专门设置一个）
async def h2(request, exc):
    return JSONResponse(400, ...)

@app.exception_handler(Exception)  # Python 内置 → 500（兜底所有未捕获）
async def h3(request, exc):
    return JSONResponse(500, ...)
```

### 2.3 为什么基类是关键的"批量兜底"


| 设计选择                      | 路由层 handler 数量                                                    | 维护成本                |
| ------------------------- | ----------------------------------------------------------------- | ------------------- |
| ❌ 直接继承 Exception          | 10 个异常 = 10 个 handler（也就是有10个异常，都要记住报错之后分别返回码都要返回多少）              | 高（每加一个异常要加 handler） |
| ✅ 继承 FitForgeException 基类 | 1 个 catch 兜底所有业务异常（只要设定了某个异常是属于这个基类的，所以哪怕没有设定这个专门异常子类，通通返回400返回码） | 低（加新异常自动走兜底）        |


> **面试话术**：「我用自定义业务异常基类 FitForgeException 继承 Exception——这样路由层只需一个 catch FitForgeException 兜底映射 400，新加的业务异常自动走这个兜底，避免每个异常单独写 handler。这是'开闭原则'的应用：扩展业务异常（加新类）不需要改路由层（不用加 handler）。」

---

## 3. 为什么不用 Python 内置 ValueError？


| 选项                                   | 行为                                                        | 问题                                               |
| ------------------------------------ | --------------------------------------------------------- | ------------------------------------------------ |
| `**raise ValueError`**               | Python 内置（`ValueError` 的官方含义是：**“参数的值不符合要求（格式不对、类型不对）”**） | ⚠️ FastAPI 默认 422，但语义混淆——ValueError 是程序错误，不是业务错误 |
| `**raise HTTPException(409, ...)`**  | FastAPI 原生                                                | ⚠️ service 依赖 FastAPI，业务不可复用（CLI/队列用不了）          |
| `**raise UsernameExistsError(...)`** | ✅ 自定义业务异常                                                 | service 不知道 HTTP，路由层 handler 映射 409              |


### 3.1 ValueError 语义错位

```python
# ValueError 是 Python 表达"参数值不对"的内置异常
# 本来是用于说格式不对的，但你告诉 Python：“用户名 ‘alice’ 是一个无效的值。”
# 实际情况：‘alice’ 这个字符串本身是完全合法的！它全是字母、没有特殊符号、长度也合适。它不是格式错误的值。所以说语义错位
raise ValueError("username exists")  # 语义错位（）

# 业务异常 = 用户能感知的错误（注册失败、余额不足等）
# 用专属类表达，路由层针对性处理
raise UsernameExistsError("username 'alice' already exists")  # ✅ 语义正确
```

> **面试话术**：「我不复用 Python 内置 ValueError，也不直接 raise HTTPException——前者语义错（ValueError 是程序 bug 不是业务错误），后者破坏分层（service 依赖 FastAPI 不可复用）。我自建 FitForgeException 体系，service 抛业务异常不知道 HTTP，路由层 handler 负责映射——这是'分层 + 解耦'的双重保证。」

---

## 4. 重写 `__init__` 和 `__str__` 的小细节

```python
class FitForgeException(Exception):
#它能接收的参数有两部分：必传参数 message (字符串)，可选参数 *args (其他乱七八糟的）
    def __init__(self, message: str, *args: Any) -> None:
        super().__init__(message, *args)  # 父类初始化（也就是把 message 传给父类，让它把底层的异常机制搭建好）
#假如后面函数_init_的参数变多了，我们只要最后这个self.message 赋值正确就没影响
        self.message = message            # 该类自己存为属性方便访问
#__str__ 只是个“化妆师”，它决定别人看到你是什么样（打印出来什么样）
#但它改不了你底下的“真身”（self.message 里存的数据）。
    def __str__(self) -> str:
        return self.message                # print() 时输出 message
#使用例子
class UsernameExistsError(FitForgeException):#继承FitForgeException
    pass

# 使用
async def register():
    raise UsernameExistsError("用户名 'alice' 已被占用")

# 路由层/调用方
try:
    await register()
except UsernameExistsError as exc:#相当于exc = UsernameExistsError("用户名 'alice' 已被占用")
    # 1. 拿信息：用“把手”
    detail = exc.message

    # 2. 写日志：用“化妆”
    logger.error(f"注册失败: {exc}")#exc输出的是那个“对象”，包含一切（数据+方法+堆栈信息）。也就是完整的错误字段比如：UsernameExistsError('用户名 \'alice\' 已被占用')。当你需要打印、记录、抛出时用它。

    # 3. 返回给前端
    return JSONResponse(409, {"detail": detail})#exc.message输出的是那个“数据”，只是个字符串。当你需要把错误信息取出来发给前端、或者存数据库时用它。
```

### 4.1 两个细节的好处


| 细节                        | 没有改的话                                                                                     | 重写后                                                                                          |     |
| ------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --- |
| `__init__` 存 self.message | *# 调用方（脆弱）* msg = str(exc) *# 依赖字符串格式，一旦格式变了就崩* msg = exc.args[0] *# 依赖参数位置，一旦参数顺序变了就崩* | `exc.message` 可访问，同时防止改变父类的存储结构会改变报错信息（*用户名重复*），因为自己已经单独存了一份错误信息在self.message中，只要赋值正确就不影响使用。 |     |
| `__str__` 输出 message      | `打印出来默认是：UsernameExistsError('用户名 \'alice\' 已被占用')这种`多余的类名、引号、括号，噪音很多的文字。                | 日志里就一句话：`用户名 'alice' 已被占用`看日志的人一眼就知道发生了什么，不用再去看类名、堆栈。                                       |     |


### 4.2 不重写也可以

- 不重写时，`print(异常对象)` 输出 `(ClassName, message)` 元组（Python 默认 Exception.**str** 行为）
- 重写后输出 `message` 字符串——更友好

> **面试话术**：「重写 **init** 把 message 存为 self.message——业务代码可以通过 `exc.message` 访问，不要 parse str(exc)。重写 **str** 让 print() 友好——调试日志里直接输出 '用户名 alice 已被占用' 而不是 '(UsernameExistsError, 用户名 alice 已被占用)'。两个小细节让异常可读、可调试。」

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


| 层级                  | 拦截率   | 处理                        |
| ------------------- | ----- | ------------------------- |
| **应用层（service 查重）** | 99%   | UsernameExistsError → 409 |
| **DB 层（UNIQUE 约束）** | 1% 兜底 | IntegrityError → 409      |


> **面试话术**：「DB 兜底 IntegrityError 跟业务异常是两回事——业务异常是 service 检查出的，IntegrityError 是 DB UNIQUE 约束抛出的（应对高并发竞争）。应用层 99% 拦截 + DB 层 1% 兜底，这就是'纵深防御'——单层防御总会被绕过。」

---

## 6. 面试 Q&A（5 题预演）

### Q1：为什么业务层抛异常不用返回错误码？

> "异常模式 3 个核心优势：① Python 异常原生 try/except，调用方代码最简洁；② 业务异常与 HTTP 解耦——service 不知道 HTTP 存在，业务可复用（CLI/脚本/队列都直接调 service.register()）；③ Python traceback 自带行号和调用栈，调试速度比 Result 模式的字符串错误码快 10 倍。"

### Q2：异常继承体系怎么设计？为什么用基类？

> "用 FitForgeException 基类继承 Exception，路由层一个 catch FitForgeException 兜底映射 400，新加的业务异常自动走这个兜底，避免每个异常单独写 handler。这是'开闭原则'的应用：扩展业务异常（加新类）不需要改路由层（不用加 handler）。"

### Q3：为什么不用 Python 内置 ValueError？

> "语义错位。ValueError 是 Python 表达'程序参数错'的内置异常（如 int('abc') 抛 ValueError），是程序 bug，不是用户输入问题。业务异常 = 用户能感知的错误（注册失败、余额不足等），用专属类表达，路由层针对性处理。"

### Q4：自定义异常的 **init** 怎么写？重写 **str** 有什么好处？

> "重写 **init** 把 message 存为 self.message——业务代码可以通过 exc.message 访问，不要 parse str(exc)。重写 **str** 让 print() 友好——调试日志里直接输出 message 字符串，而不是 '(ClassName, message)' 元组。两个小细节让异常可读、可调试。"

### Q5：IntegrityError 跟业务异常什么关系？

> "两层不同：业务异常是 service 检查出的（99% 拦截），IntegrityError 是 DB UNIQUE 约束抛出的（1% 兜底）。路由层都映射 409，但来源不同——service 不知道 SQLAlchemy 不抛 IntegrityError，DB 不知道业务逻辑不抛 UsernameExistsError。两层叠加是'纵深防御'。"

---

## 7. 踩坑清单


| 坑                    | 现象                      | 解法                                    |
| -------------------- | ----------------------- | ------------------------------------- |
| 业务异常不继承基类            | 路由层 catch 不到，500 错误     | 继承 FitForgeException                  |
| 业务异常继承 HTTPException | service 依赖 FastAPI，不可复用 | 自定义基类                                 |
| 异常太多不分组              | handler 数量爆炸            | 用 FitForgeException 基类 + 1 个 catch 兜底 |
| 异常 print 出来是元组       | 调试不友好                   | 重写 **str**                            |
| 业务异常 message 忘记存     | 业务代码要 parse str(exc)    | 重写 **init** 存 self.message            |
| DB UNIQUE 冲突未处理      | 1% 漏报 500               | 路由层 catch IntegrityError 兜底 409       |


---

## 8. 参考资源

- [FastAPI exception handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Python Exception 文档](https://docs.python.org/3/tutorial/errors.html)
- [SQLAlchemy IntegrityError](https://docs.sqlalchemy.org/en/20/errors.html#sqlalchemy.exc.IntegrityError)
- [开闭原则 SOLID](https://en.wikipedia.org/wiki/Open%E2%80%93closed_principle)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘