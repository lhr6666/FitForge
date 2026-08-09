# Pydantic v2 Schema 沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：Q4（2 schema 隔离 password）、Q5（中等密码强度）、Q6（email 必填）
> **关联 commit**：`8317576`（plan Task 14）
> **目的**：面试前复习 + Pydantic v1→v2 迁移指南

---

## 1. 为什么用 Pydantic

| 选项 | 行为 |
|------|------|
| 自己写 dataclass + 手动校验 | 字段多就崩 |
| **Pydantic** | 类型注解即校验 + 自动 OpenAPI + 422 自动 |
| marshmallow | 老牌但慢、Pydantic 更快 |
| msgspec | 新但生态小 |

> **面试话术**：「我用 Pydantic v2 做 schema 校验——类型注解即校验，FastAPI 自动捕获 422。这是 Python 类型系统 + Web 框架的'类型即接口'设计，业务代码只用 type hint 声明 schema，零胶水代码。」

---

## 2. v1 → v2 关键迁移（4 个改名）

| v1（已弃用）| v2（推荐）| 说明 |
|------------|----------|------|
| `validator` | `field_validator` | 重命名 |
| `class Config` | `model_config = ConfigDict(...)` | 配置改字段 |
| `orm_mode = True` | `from_attributes = True` | 重命名（更准确：支持任何 attribute 对象）|
| `@validator` | `@field_validator` + `@classmethod` | 强制 classmethod |

> **面试话术**：「Pydantic v2 重命名了 4 个核心 API：validator → field_validator、Config 类 → model_config、orm_mode → from_attributes、新增 @classmethod 强制。这是 Rust 化重写后的破坏性升级，但性能提升 5-50 倍。」

---

## 3. 4 个核心校验机制

### 3.1 Field 字段约束

```python
from pydantic import Field

class UserCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="用户名（3-50 字符，字母数字下划线）",
    )
```

**支持的约束**：
- 字符串：`min_length` / `max_length` / `pattern`
- 数值：`gt` / `lt` / `ge` / `le` / `multiple_of`
- 其他：`description`（自动生成 OpenAPI 文档）/ `default` / `examples`

### 3.2 特殊类型（EmailStr / HttpUrl / IPvAnyAddress ...）

```python
from pydantic import EmailStr

email: EmailStr  # 自动校验邮箱格式
```

- `EmailStr`：依赖 email-validator（Pydantic v2 拆出独立 extras）
- `HttpUrl`：校验 URL 格式
- `IPvAnyAddress`：校验 IP 地址
- `PositiveInt` / `NegativeFloat`：数值范围

**安装 extras**：`pip install pydantic[email]`（自动装 email-validator）。

### 3.3 field_validator 自定义校验

```python
from pydantic import field_validator

@field_validator("password")
@classmethod
def password_must_contain_letter_and_digit(cls, v: str) -> str:
    if not re.search(r"[a-zA-Z]", v):
        raise ValueError("密码必须包含字母")
    if not re.search(r"\d", v):
        raise ValueError("密码必须包含数字")
    return v
```

**3 个关键点**：
1. `@field_validator("字段名")` 绑定字段
2. `@classmethod` 必须（v2 新增）
3. 抛 `ValueError` 自动转 422

### 3.4 model_validator 跨字段校验

```python
from pydantic import model_validator

class UserCreate(BaseModel):
    password: str
    confirm_password: str

    @model_validator(mode='after')
    def check_passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("两次密码不一致")
        return self
```

**mode 选项**：
- `mode='before'`：原始输入校验
- `mode='after'`：字段校验后（默认）

---

## 4. model_config = ConfigDict 配置项

```python
from pydantic import ConfigDict

class UserRead(BaseModel):
    id: int
    model_config = ConfigDict(
        from_attributes=True,     # 允许从 ORM 对象构造
        frozen=True,              # 实例不可修改（immutable）
        extra="forbid",           # 禁止多余字段
        str_strip_whitespace=True,# 自动 strip 字符串
    )
```

**常用配置**：

| 配置 | 作用 |
|------|------|
| `from_attributes=True` | 允许 ORM/dataclass → Pydantic 转换 |
| `frozen=True` | 实例不可修改（dataclass 风格）|
| `extra="forbid"` | 禁止多余字段（严格模式）|
| `extra="ignore"` | 多余字段静默忽略（默认）|
| `str_strip_whitespace` | 自动 strip |
| `use_enum_values` | 序列化时用 enum 的 value 不是 enum 实例 |
| `populate_by_name=True` | 允许用字段别名初始化 |

---

## 5. OpenAPI 自动文档

**Pydantic → Swagger UI 自动生成**：

```python
class UserCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="用户名（3-50 字符，字母数字下划线）",
    )
```

FastAPI 自动生成 OpenAPI schema：

```json
{
  "UserCreate": {
    "properties": {
      "username": {
        "type": "string",
        "minLength": 3,
        "maxLength": 50,
        "pattern": "^[a-zA-Z0-9_]+$",
        "description": "用户名（3-50 字符，字母数字下划线）"
      }
    },
    "required": ["username"]
  }
}
```

> **面试话术**：「Pydantic Field 的 description/min_length/max_length/pattern 自动生成 Swagger UI 文档——前端工程师直接看 schema 写代码，不用跟后端来回问字段。这就是'API 自文档化'，比手写 OpenAPI 注解省一半工作。」

---

## 6. 自动 422 响应

**FastAPI 自动处理 Pydantic 校验失败**：

```
Test 5 OK: bad email rejected
```

**响应格式**（自动）：

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

**自动流程**：
```
路由函数签名含 UserCreate 参数
   ↓
FastAPI 解析请求 body
   ↓
Pydantic 校验 UserCreate（自动）
   ↓
失败 → 自动 422 + ValidationError → 业务代码根本不知道校验发生过
```

> **面试话术**：「Pydantic 校验失败 → FastAPI 自动 422 响应，业务代码零胶水。这是 FastAPI 的'类型即接口'设计哲学——签名声明 `user_create: UserCreate`，框架自动校验、自动序列化、自动文档。」

---

## 7. 从 ORM 对象构造（Pydantic v2）

```python
class UserRead(BaseModel):
    id: int
    username: str
    nickname: str | None = None

    model_config = ConfigDict(from_attributes=True)

# 路由层：从 ORM 对象构造 DTO
user = await auth_service.register(db, user_create)  # ORM 对象
user_read = UserRead.model_validate(user)  # Pydantic 自动从属性读取
```

**`from_attributes=True` 的作用**：
- 允许 ORM 对象（`user.id`、`user.username`）自动转 Pydantic 实例
- v1 用 `orm_mode = True`，v2 改名 `from_attributes`（更准确：任何带属性的对象）

**`model_validate` vs `__init__`**：
- `UserRead.model_validate(user)`：从 ORM 转换（Pydantic v2 推荐）
- `UserRead(**user.__dict__)`：手动 unpack（不优雅）

---

## 8. 面试 Q&A（6 题预演）

### Q1：Pydantic v1 和 v2 区别？

> "v2 是 Rust 内核重写，性能提升 5-50 倍。破坏性变更：① validator → field_validator；② Config 类 → model_config；③ orm_mode → from_attributes；④ 新增 @classmethod 强制。代价：旧代码要改 API，但收益是性能 + 更准确的语义。"

### Q2：为什么用 Pydantic 不用 dataclass？

> "dataclass 是 Python 内置数据类，不校验类型。Pydantic 在 dataclass 基础上加运行时校验 + 自动序列化 + OpenAPI schema。dataclass + 手动校验要写 100 行，Pydantic 一行搞定。"

### Q3：EmailStr 怎么工作？

> "Pydantic EmailStr 不是自己实现——它依赖 email-validator 库做严格格式校验（DNS MX 记录、TLD 有效性等）。`pip install pydantic[email]` extras 自动装 email-validator。这是 Pydantic 模块化设计：核心功能靠第三方库扩展。"

### Q4：field_validator vs model_validator？

> "field_validator 校验单个字段（如密码含字母）。model_validator 跨字段校验（如两次密码一致）。mode='before' 是原始输入校验，mode='after' 是字段校验后（默认）。我项目里只用 field_validator，跨字段校验用业务层做（service 层）。"

### Q5：FastAPI 怎么自动 422？

> "路由函数签名声明 `user_create: UserCreate`，FastAPI 自动解析 body + Pydantic 校验。失败自动 422 + ValidationError 列表。业务代码零胶水——根本不用 try/except。这是'类型即接口'的极致体现。"

### Q6：from_attributes=True 是做什么的？

> "允许 ORM 对象（user.id、user.username）自动转 Pydantic 实例。v1 叫 orm_mode=True，v2 改名 from_attributes 因为它支持任何带属性的对象（不只 ORM）。我项目里用 UserRead.model_validate(orm_user) 把 SQLAlchemy User 转 API DTO。"

---

## 9. 踩坑清单

| 坑 | 现象 | 解法 |
|----|------|------|
| v1 v2 混用 | `validator` 不存在 | 用 v2 写法 + classmethod |
| EmailStr 报 not installed | 漏装 email-validator | `pip install pydantic[email]` |
| model_validate 失败 | UserRead 没定义字段 | 加 `from_attributes=True` |
| 校验失败不抛 422 | 路由层 try/except 拦截了 | 别 try/except ValidationError |
| 字段别名不生效 | 没设 populate_by_name | ConfigDict 加 `populate_by_name=True` |
| 多余字段报错 | 默认 extra=ignore 不会 | 设 extra="forbid" |
| frozen=True 后改字段 | 报 ValidationError | 用 model_copy(update={...}) 替代 |

---

## 10. 参考资源

- [Pydantic v2 文档](https://docs.pydantic.dev/latest/)
- [Pydantic v1→v2 迁移指南](https://docs.pydantic.dev/latest/migration/)
- [FastAPI 请求体验证](https://fastapi.tiangolo.com/tutorial/body/)
- [Pydantic 配置项](https://docs.pydantic.dev/latest/concepts/config/)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘