# FastAPI 自动接口文档机制

> 2026/07/02 周二任务产出（补记）
> 目标：把 FastAPI `/docs` 跑通时的 4 端点验证 + 3 个面试亮点系统沉淀
> 补记原因：当时口头讨论过但未落盘，2026/07/02 整理文档时发现遗漏

## 一、4 个端点验证结果

| 端点 | 验证结果 | 含义 |
|------|----------|------|
| `GET /` | `{"status":"ok","service":"fitforge","version":"0.1.0"}` | 健康检查入口 |
| `GET /health` | `{"status":"healthy"}` | K8s 风格探活 |
| `GET /docs` | HTTP 200，text/html | Swagger UI 页面 |
| `GET /openapi.json` | OpenAPI 3.1.0 JSON | API 契约自动生成 |

> 💡 Windows bash 终端编码问题：HTTP 状态码可能显示成乱码（如"HTTP ״̬�룺200"），这是**终端显示问题**，不是 HTTP 错误。HTTP 200 = 请求成功。

## 二、3 个面试亮点（核心）

### 亮点 1：代码即文档（30 秒搭起 API 文档）

**现象**：
我在 `main.py` 写了：
```python
@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "fitforge", "version": "0.1.0"}
```

打开 `http://localhost:8000/docs`，**Swagger UI 自动出现**，包含：
- 接口路径（`/`）
- HTTP 方法（GET）
- 返回类型（dict[str, str]）
- 在线测试按钮

**底层原理**：
- FastAPI 启动时**遍历所有路由函数**
- 读取 Python 类型注解（`dict[str, str]`）
- 生成 OpenAPI 3.1.0 schema
- 用 Swagger UI 渲染

**对比传统方式**：
| 步骤 | 传统 | FastAPI |
|------|------|---------|
| 1 | 写代码 | 写代码 |
| 2 | 写 Postman 集合 | （自动） |
| 3 | 写 README 接口章节 | （自动） |
| 4 | 同步前端 | 分享 /docs 链接 |

**面试话术**：
> "我选 FastAPI 不是因为它'新潮'，是因为它的 OpenAPI 自动生成能让我和前端/测试工程师对接时零摩擦——他们打开 /docs 就知道有哪些接口、参数是什么、返回结构是什么。这比传统'先写代码再写 Postman 集合再写 README'高效 10 倍。"

---

### 亮点 2：`/openapi.json` 是机器可读的 API 契约

**现象**：
访问 `/openapi.json` 返回：
```json
{
  "openapi": "3.1.0",
  "info": {"title": "FitForge", "version": "0.1.0"},
  "paths": {
    "/": {
      "get": {
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "additionalProperties": {"type": "string"}
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**这个 JSON 能干嘛？**

| 用途 | 工具 | 结果 |
|------|------|------|
| 生成前端 TS 客户端 | openapi-generator | 一行命令出 SDK |
| 导入 Postman / Insomnia | 直接导入 | 一键拿到所有接口 |
| 自动化测试 | pytest + schemathesis | 自动生成测试用例 |
| API 网关注册 | Kong / APISIX | 自动注册路由 |
| 文档站 | Redoc / Stoplight | 一键生成文档站 |

**面试话术**：
> "FastAPI 的 `/openapi.json` 是机器可读的 API 契约——前端不用等我写文档就能开始开发，他们跑 openapi-generator 直接出 TypeScript SDK。这是**契约优先开发**（Contract-First Development）的最小实践：契约从代码生成，永远不会过时。"

---

### 亮点 3：Python 类型注解 = 免费的运行时校验

**我的 main.py 写了**：
```python
async def root() -> dict[str, str]:
    return {"status": "ok"}
```

**FastAPI 自动做的**：
- 校验返回类型是 `dict[str, str]`（Pydantic 校验）
- 自动生成 OpenAPI schema（`additionalProperties: {type: string}`）
- 失败时返回 422 错误（带详细错误信息）

**为什么类型注解能驱动校验？**

Python 3.5+ 的 `typing` 模块原本只是给 IDE 看，**不运行时检查**。

但 FastAPI 用 Pydantic v2 把类型注解变成了**运行时校验器**：
- `dict[str, str]` → 检查返回是 dict，且每个 value 是 str
- `list[int]` → 检查每个元素是 int
- 自定义类 `User` → 校验字段

**面试话术**：
> "我用 FastAPI 写 `dict[str, str]` 不只是给 IDE 看的——FastAPI + Pydantic 把它变成了**运行时校验器**。如果我返回 `dict[str, int]`，Pydantic 会拦截，返回 422 错误。这比手写 if-else 校验安全 10 倍，TypeScript 的类型系统也做不到运行时检查。"

---

## 三、面试追问预测

### Q1：FastAPI 和 Flask 怎么选？
- **Flask**：轻量、灵活、需要手动集成 marshmallow/swagger
- **FastAPI**：自带 OpenAPI、Pydantic 校验、async 原生、类型提示驱动
- **选 FastAPI 的核心理由**：现代项目对**类型安全 + API 文档 + 异步**需求越来越强

### Q2：什么是 OpenAPI 规范？
- **OpenAPI**：描述 REST API 的标准格式（YAML/JSON）
- 之前叫 Swagger Specification，2015 年捐给 Linux 基金会改名 OpenAPI
- 当前版本：3.1.0（2021 年）
- **作用**：API 描述的"行业标准"——Kong/Apigee/Postman 都认

### Q3：`/openapi.json` 和 `/docs` 的关系？
- `/openapi.json`：**机器读的** OpenAPI 契约
- `/docs`：**人读的** Swagger UI（前端 / 测试 / PM 看）
- `/redoc`（可选）：另一个人读的 ReDoc 风格文档

### Q4：Pydantic v2 相比 v1 有什么改进？
- **性能**：v2 用 Rust 重写，校验速度快 5-50 倍
- **API**：v2 的 `model_validate()` 替代 v1 的 `parse_obj()`
- **类型**：v2 严格支持 Python 类型注解（`dict[str, str]` 而非 v1 的 `Dict[str, str]`）

---

## 四、FitForge 后续怎么用这个能力？

### 1. 周三注册接口
```python
# /auth/register 自动出现在 /docs
@app.post("/auth/register")
async def register(user: UserCreate) -> UserResponse:
    ...
```

### 2. 周六部署后远程验证
```bash
# 服务器上跑 uvicorn，远程访问
curl http://114.132.83.99:8000/docs
# 应该看到完整的 Swagger UI
```

### 3. 写完所有接口后一键生成前端 SDK（可选）
```bash
# 拉 /openapi.json → 生成 TypeScript SDK
npx openapi-typescript-codegen \
  --input http://localhost:8000/openapi.json \
  --output ./frontend-sdk
```

### 4. 导入 Postman 给前端 / 测试
- Postman → Import → Link → `http://localhost:8000/openapi.json`
- 一键拿到所有接口的请求示例

---

## 五、FitForge 周二实操回顾

### main.py 完整代码（5 行核心）
```python
from fastapi import FastAPI

app = FastAPI(
    title="FitForge",
    description="一个给健身爱好者用的训练管理工具",
    version="0.1.0"
)

@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "fitforge", "version": "0.1.0"}

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
```

### 启动命令
```bash
uvicorn main:app --reload
# --reload 监听文件变化自动重启（开发用）
```

### 验证命令
```bash
# 4 个端点 curl 验证
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/docs
curl http://localhost:8000/openapi.json
```

---

## 六、一句话总结

> FastAPI 的核心价值不是"快"，是**类型即校验** + **代码即文档** + **契约即 JSON**——三件事合起来让前后端协作摩擦降到 0。

把这三件事讲清楚，能展开 15 分钟的面试回答。

---

**参考资源**：
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Pydantic v2 文档](https://docs.pydantic.dev/latest/)
- [OpenAPI 3.1.0 规范](https://spec.openapis.org/oas/v3.1.0)
- [OpenAPI Generator](https://openapi-generator.tech/)
