# /auth/register Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 POST /auth/register 端点，支撑 FitForge MVP 用户注册功能。

**Architecture:** 严格分层（api 路由 / services 业务 / models ORM / schemas Pydantic / core 配置/db/security）。重型 service 模式（接 Pydantic schema、返回 ORM、抛业务异常）；Depends async generator 注入 AsyncSession；Argon2id 密码哈希；email/username 唯一性双层防御（应用层查重 + DB 层 UNIQUE 约束）。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 (asyncmy) / MySQL 8.0 / Alembic / Pydantic v2 / passlib[argon2] / pydantic-settings / pytest + pytest-asyncio + httpx

**Spec 参考**：`docs/superpowers/specs/2026-07-06-auth-register-design.md`（所有 9 个文件的完整代码骨架在 spec §4.2）

---

## Global Constraints

- **Python 版本**：>= 3.10（用 `from __future__ import annotations` 和 PEP 604 `|` 语法）
- **MySQL 连接**：服务器 fitforge 库已存在（用户 fitforge / 密码 fitforge_dev_password_2026，仅开发用）
- **时间戳**：所有 DateTime 字段一律 UTC（`datetime.utcnow`）
- **依赖管理**：每个 pip install 必须同步更新 `requirements.txt`，并简述作用
- **Commit 规范**：Conventional Commits（feat/fix/docs/refactor/test/chore）
- **架构红线**：业务逻辑必须在 `services/`、路由必须在 `api/`、ORM 必须在 `models/`、配置必须在 `core/`
- **错误处理**：业务异常体系（service 抛自定义异常，路由层 `add_exception_handler` 映射）
- **ORM 不返回密码**：`UserRead` schema 不定义 `password_hash` 字段
- **错误响应**：Pydantic ValidationError → 422 / 业务异常 → 409 / 未捕获 → 500
- **配置文件**：`core/config.py` 用 `pydantic-settings.BaseSettings`，禁止硬编码
- **开发环境**：本地 Windows 写代码 + 测，最后用 Cursor Remote SSH 同步到服务器跑 alembic
- **进度追踪**：每完成一个 Task 勾选 `- [x]` + git commit + 更新 `project_progress.md`

---

## Task 1: 安装依赖 + 更新 requirements.txt

**Files:**
- Modify: `requirements.txt`

**关键依赖**（每个 pip install 后同步更新 requirements.txt + 加注释）：

```
fastapi==0.115.6           # Web 框架
uvicorn[standard]==0.32.1  # ASGI 服务器
sqlalchemy[asyncio]==2.0.36  # ORM 异步
asyncmy==0.2.10            # MySQL 异步驱动
pymysql==1.1.1             # Alembic 同步驱动（autogenerate 需要）
alembic==1.14.0            # 数据库迁移
pydantic[email]==2.10.4    # 数据校验（含 EmailStr）
pydantic-settings==2.7.0   # 配置管理
passlib[argon2]==1.7.4     # 密码哈希
argon2-cffi==23.1.0        # Argon2 C 实现
python-multipart==0.0.20   # 表单解析（未来用）
```

- [ ] **Step 1**: 在 venv 中安装依赖
```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform"
source venv/Scripts/activate  # Windows Git Bash
pip install fastapi 'uvicorn[standard]' 'sqlalchemy[asyncio]' asyncmy pymysql alembic 'pydantic[email]' pydantic-settings 'passlib[argon2]' argon2-cffi python-multipart pytest pytest-asyncio httpx
```

- [ ] **Step 2**: 同步更新 requirements.txt（手动写一遍，加注释）

- [ ] **Step 3**: 验证
```bash
pip list | grep -iE "fastapi|sqlalchemy|alembic|pydantic|passlib|argon2"
```
预期：所有包都列出

- [ ] **Step 4**: Commit
```bash
git add requirements.txt
git commit -m "chore(deps): add core dependencies for /auth/register

fastapi/sqlalchemy[asyncio]/asyncmy/alembic/pydantic-settings/passlib[argon2]
详见 D4-D19 决策，spec §1.3"
```

---

## Task 2: 写 core/config.py

**Files:**
- Create: `core/config.py`
- Create: `.env`
- Modify: `.env.example`

**Interfaces:**
- Produces: `settings` (Settings 实例) — 所有其他模块用 `from core.config import settings`

**关键代码**（详见 spec §4.2 `core/config.py`）：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+asyncmy://fitforge:fitforge_dev_password_2026@localhost:3306/fitforge"
    SYNC_DATABASE_URL: str = "mysql+pymysql://fitforge:fitforge_dev_password_2026@localhost:3306/fitforge"
    JWT_PRIVATE_KEY_PATH: str = "./keys/private.pem"
    JWT_PUBLIC_KEY_PATH: str = "./keys/public.pem"
    JWT_ALGORITHM: str = "RS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
```

- [ ] **Step 1**: 创建 `core/__init__.py`（空文件，让 core 成为 package）

- [ ] **Step 2**: 创建 `core/config.py`，写上述代码

- [ ] **Step 3**: 创建 `.env`（同 .env.example，不入 Git）

- [ ] **Step 4**: 修改 `.env.example` 加入 DATABASE_URL 示例

- [ ] **Step 5**: 验证
```bash
python -c "from core.config import settings; print(settings.DATABASE_URL)"
```
预期：打印出数据库 URL

- [ ] **Step 6**: Commit
```bash
git add core/config.py core/__init__.py .env.example
git commit -m "feat(config): add pydantic-settings config + .env.example

D11 决策：单一 .env + pydantic-settings BaseSettings
详见 spec §4.2"
```

---

## Task 3: 写 core/db.py

**Files:**
- Create: `core/db.py`

**Interfaces:**
- Produces: `engine` (AsyncEngine), `AsyncSessionLocal` (sessionmaker), `get_db()` (async generator dependency)

**关键代码**（详见 spec §4.2 `core/db.py`）：

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from core.config import settings
from models import Base  # Task 6 后才有

engine = create_async_engine(settings.DATABASE_URL, echo=True, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

- [ ] **Step 1**: 创建 `core/db.py`

- [ ] **Step 2**: 暂时注释 `from models import Base`（Task 6 后解除）

- [ ] **Step 3**: 验证 import（用 SQLite 临时测试或等 Task 6）
```bash
python -c "from core.db import engine; print(engine)"
```

- [ ] **Step 4**: Commit
```bash
git add core/db.py
git commit -m "feat(db): add async SQLAlchemy engine + get_db dependency

Q3 决策：async generator + Depends
D4 决策：SQLAlchemy 2.0 异步
详见 spec §4.2"
```

---

## Task 4: 写 core/security.py

**Files:**
- Create: `core/security.py`

**Interfaces:**
- Produces: `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`

**关键代码**（详见 spec §4.2 `core/security.py`）：

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

- [ ] **Step 1**: 创建 `core/security.py`

- [ ] **Step 2**: 验证
```bash
python -c "
from core.security import hash_password, verify_password
h = hash_password('Test1234')
print('hash:', h[:30], '...')
print('verify ok:', verify_password('Test1234', h))
print('verify fail:', verify_password('WrongPass1', h))
"
```
预期：hash 前 30 字符 + verify ok=True + verify fail=False

- [ ] **Step 3**: Commit
```bash
git add core/security.py
git commit -m "feat(security): add Argon2id password hash + verify

D6 决策：Argon2id (passlib + argon2-cffi)
详见 spec §4.2"
```

---

## Task 5: 写 core/exceptions.py

**Files:**
- Create: `core/exceptions.py`

**Interfaces:**
- Produces: `FitForgeException` 基类 + `UsernameExistsError` / `EmailExistsError` 子类

**关键代码**（详见 spec §4.2 `core/exceptions.py`）：

```python
class FitForgeException(Exception):
    """FitForge 业务异常基类"""
    pass

class UsernameExistsError(FitForgeException):
    """用户名已被占用"""
    pass

class EmailExistsError(FitForgeException):
    """邮箱已被注册"""
    pass
```

- [ ] **Step 1**: 创建 `core/exceptions.py`

- [ ] **Step 2**: 验证
```bash
python -c "
from core.exceptions import UsernameExistsError, EmailExistsError, FitForgeException
e = UsernameExistsError('test')
print(isinstance(e, FitForgeException))  # True
"
```

- [ ] **Step 3**: Commit
```bash
git add core/exceptions.py
git commit -m "feat(exceptions): add FitForge business exception hierarchy

Q2 决策：业务异常体系
详见 spec §4.2"
```

---

## Task 6: 写 models/__init__.py 导出 Base

**Files:**
- Create: `models/__init__.py`

**Interfaces:**
- Produces: `Base` (DeclarativeBase) — Alembic env.py 用

**关键代码**：

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Alembic env.py 会从 models 导入所有 model
from models.user import User  # noqa: E402,F401
from models.user_goal import UserGoal  # noqa: E402,F401
from models.body_measurement import BodyMeasurement  # noqa: E402,F401
```

- [ ] **Step 1**: 创建 `models/__init__.py`（仅 Base，import 留到 Task 7-9 后追加）

- [ ] **Step 2**: 验证
```bash
python -c "from models import Base; print(Base)"
```

- [ ] **Step 3**: Commit
```bash
git add models/__init__.py
git commit -m "feat(models): add SQLAlchemy DeclarativeBase

D17 决策：3 张表的 ORM 基类
详见 spec §4.2"
```

---

## Task 7: 写 models/user.py

**Files:**
- Create: `models/user.py`

**Interfaces:**
- Produces: `User` ORM class — Alembic 会创建 users 表；services/auth_service 用

**关键代码**（详见 spec §4.2 `models/user.py`，完整版在 D17 §3.1）：

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from models import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    goals = relationship("UserGoal", back_populates="user", cascade="all, delete-orphan")
    measurements = relationship("BodyMeasurement", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"
```

- [ ] **Step 1**: 创建 `models/user.py`

- [ ] **Step 2**: 解除 `core/db.py` 里 `from models import Base` 的注释

- [ ] **Step 3**: 验证
```bash
python -c "from models.user import User; print(User.__tablename__, User.__table__.columns.keys())"
```
预期：users, ['id', 'username', 'email', 'password_hash', 'nickname', 'created_at', 'updated_at']

- [ ] **Step 4**: 更新 `models/__init__.py` 加入 `from models.user import User`

- [ ] **Step 5**: Commit
```bash
git add models/user.py models/__init__.py core/db.py
git commit -m "feat(models): add User ORM with D17 schema

D17 决策：username/email UNIQUE、CASCADE relationships
详见 spec §4.2"
```

---

## Task 8: 写 models/user_goal.py

**Files:**
- Create: `models/user_goal.py`

**Interfaces:**
- Produces: `UserGoal` ORM class

**关键代码**（详见 D17 §3.2 完整伪代码）：

```python
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Date, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from models import Base

class UserGoal(Base):
    __tablename__ = "user_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum("cut", "bulk", "maintain", "strength", name="goal_type"), nullable=False)
    target_value = Column(Float, nullable=True)
    status = Column(Enum("active", "completed", "abandoned", name="goal_status"), default="active", nullable=False, index=True)
    deadline = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="goals")

    __table_args__ = (Index("idx_user_goals_user_status", "user_id", "status"),)

    def __repr__(self):
        return f"<UserGoal {self.id} {self.type} {self.status}>"
```

- [ ] **Step 1**: 创建 `models/user_goal.py`

- [ ] **Step 2**: 更新 `models/__init__.py`

- [ ] **Step 3**: 验证
```bash
python -c "from models.user_goal import UserGoal; print(UserGoal.__tablename__)"
```

- [ ] **Step 4**: Commit
```bash
git add models/user_goal.py models/__init__.py
git commit -m "feat(models): add UserGoal ORM with ENUM + composite index

D17-a/CASCADE, D17-b/composite index, D17-d/ENUM
详见 D17 §3.2"
```

---

## Task 9: 写 models/body_measurement.py

**Files:**
- Create: `models/body_measurement.py`

**Interfaces:**
- Produces: `BodyMeasurement` ORM class

**关键代码**（详见 D17 §3.3 完整伪代码）：

```python
from datetime import datetime
from sqlalchemy import Column, Integer, Float, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from models import Base

class BodyMeasurement(Base):
    __tablename__ = "body_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    weight = Column(Float, nullable=False)
    body_fat = Column(Float, nullable=True)
    chest = Column(Float, nullable=True)
    waist = Column(Float, nullable=True)
    hip = Column(Float, nullable=True)
    bicep = Column(Float, nullable=True)
    thigh = Column(Float, nullable=True)
    calf = Column(Float, nullable=True)
    squat_1rm = Column(Float, nullable=True)
    bench_1rm = Column(Float, nullable=True)
    deadlift_1rm = Column(Float, nullable=True)
    recorded_at = Column(DateTime, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="measurements")

    __table_args__ = (Index("idx_body_measurements_user_recorded", "user_id", "recorded_at"),)

    def __repr__(self):
        return f"<BodyMeasurement user={self.user_id} weight={self.weight}>"
```

- [ ] **Step 1**: 创建 `models/body_measurement.py`

- [ ] **Step 2**: 更新 `models/__init__.py`

- [ ] **Step 3**: 验证
```bash
python -c "from models.body_measurement import BodyMeasurement; print(BodyMeasurement.__tablename__)"
```

- [ ] **Step 4**: Commit
```bash
git add models/body_measurement.py models/__init__.py
git commit -m "feat(models): add BodyMeasurement ORM with 11 measurement fields

D17-c/业务时间分离（recorded_at + created_at）, D17-b/复合索引
详见 D17 §3.3"
```

---

## Task 10: Alembic init + 配置 env.py

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/` (directory)

**Interfaces:**
- Produces: alembic 可执行环境，配合 Task 11-13 生成迁移

**关键步骤**：

- [ ] **Step 1**: 初始化 alembic
```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform"
alembic init alembic
```
预期：创建 alembic/ 目录 + alembic.ini

- [ ] **Step 2**: 修改 `alembic.ini`：找到 `sqlalchemy.url` 注释掉（我们用 env.py 注入）
```ini
# sqlalchemy.url = driver://user:pass@localhost/dbname  # 注释掉
```

- [ ] **Step 3**: 修改 `alembic/env.py` 注入 metadata + 异步 URL
关键改动：
```python
from core.config import settings  # 用 SYNC_DATABASE_URL
from models import Base
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)
target_metadata = Base.metadata
```

- [ ] **Step 4**: 验证
```bash
alembic current
```
预期：输出当前 revision（空）

- [ ] **Step 5**: Commit
```bash
git add alembic.ini alembic/
git commit -m "feat(alembic): init alembic with D17 schema metadata

D9 决策：Alembic schema 版本管理
详见 spec §4.2"
```

---

## Task 11: autogenerate users 表迁移

**Files:**
- Create: `alembic/versions/<hash>_create_users_table.py`

**Interfaces:**
- Produces: users 表（id, username UNIQUE, email UNIQUE, password_hash, nickname, created_at, updated_at）

- [ ] **Step 1**: 生成迁移
```bash
alembic revision --autogenerate -m "create users table"
```

- [ ] **Step 2**: 人工 review 生成的 SQL
  - 确认 UNIQUE 约束在 username + email
  - 确认 NOT NULL 正确
  - 确认 created_at/updated_at 默认值

- [ ] **Step 3**: 执行迁移
```bash
alembic upgrade head
```

- [ ] **Step 4**: 验证（用 mysql CLI 或 python）
```bash
python -c "
import pymysql
conn = pymysql.connect(host='localhost', user='fitforge', password='fitforge_dev_password_2026', database='fitforge')
cur = conn.cursor()
cur.execute('DESC users')
for row in cur.fetchall():
    print(row)
"
```
预期：7 列符合 D17 §3.1 定义

- [ ] **Step 5**: Commit
```bash
git add alembic/versions/
git commit -m "feat(db): create users table via alembic migration

详见 D17 §3.1"
```

---

## Task 12: autogenerate user_goals 表迁移

**Files:**
- Create: `alembic/versions/<hash>_create_user_goals_table.py`

**Interfaces:**
- Produces: user_goals 表（含 ENUM、复合索引、CASCADE FK）

- [ ] **Step 1**: 生成迁移
```bash
alembic revision --autogenerate -m "create user_goals table"
```

- [ ] **Step 2**: 人工 review
  - 确认 goal_type ENUM（cut/bulk/maintain/strength）
  - 确认 goal_status ENUM + default='active'
  - 确认复合索引 idx_user_goals_user_status
  - 确认 FK CASCADE

- [ ] **Step 3**: 执行迁移
```bash
alembic upgrade head
```

- [ ] **Step 4**: 验证 DESC user_goals

- [ ] **Step 5**: Commit
```bash
git add alembic/versions/
git commit -m "feat(db): create user_goals table with ENUM + composite index

详见 D17 §3.2"
```

---

## Task 13: autogenerate body_measurements 表迁移

**Files:**
- Create: `alembic/versions/<hash>_create_body_measurements_table.py`

**Interfaces:**
- Produces: body_measurements 表（含 11 测量字段、复合索引、CASCADE FK）

- [ ] **Step 1**: 生成迁移
```bash
alembic revision --autogenerate -m "create body_measurements table"
```

- [ ] **Step 2**: 人工 review
  - 确认 11 测量字段（weight NOT NULL + 10 个 nullable）
  - 确认复合索引 idx_body_measurements_user_recorded
  - 确认 recorded_at 字段

- [ ] **Step 3**: 执行迁移
```bash
alembic upgrade head
```

- [ ] **Step 4**: 验证 DESC body_measurements

- [ ] **Step 5**: Commit
```bash
git add alembic/versions/
git commit -m "feat(db): create body_measurements table with 11 fields + composite index

详见 D17 §3.3"
```

---

## Task 14: 写 schemas/user.py (UserCreate + UserRead)

**Files:**
- Modify: `schemas/user.py`（替换占位）

**Interfaces:**
- Produces: `UserCreate`（请求，password 明文）, `UserRead`（响应，无 password_hash）

**关键代码**（详见 spec §4.2 `schemas/user.py`）：

```python
import re
from pydantic import BaseModel, EmailStr, Field, field_validator

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str | None = Field(default=None, max_length=50)

    @field_validator("password")
    @classmethod
    def password_must_contain_letter_and_digit(cls, v: str) -> str:
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v


class UserRead(BaseModel):
    id: int
    username: str
    nickname: str | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 1**: 修改 `schemas/user.py`

- [ ] **Step 2**: 验证校验规则
```bash
python -c "
from schemas.user import UserCreate
from pydantic import ValidationError

# OK case
u = UserCreate(username='alice', email='alice@example.com', password='Password123')
print('ok:', u.username)

# Fail: weak password
try:
    UserCreate(username='bob', email='bob@example.com', password='12345678')
except ValidationError as e:
    print('weak pw caught:', 'letter' in str(e).lower() or '数字' in str(e))

# Fail: bad email
try:
    UserCreate(username='charlie', email='not-an-email', password='Password123')
except ValidationError as e:
    print('bad email caught')
"
```
预期：3 个验证都生效

- [ ] **Step 3**: Commit
```bash
git add schemas/user.py
git commit -m "feat(schemas): add UserCreate (Pydantic validation) + UserRead

Q4 决策：2 schema 隔离 password
Q5 决策：中等密码强度（letter + digit）
Q6 决策：email 必填
详见 spec §4.2"
```

---

## Task 15: 写 services/auth_service.py (register)

**Files:**
- Modify: `services/auth_service.py`（替换占位）

**Interfaces:**
- Produces: `register(db: AsyncSession, user_create: UserCreate) -> User`
- Raises: `UsernameExistsError`, `EmailExistsError`

**关键代码**（详见 spec §4.2 `services/auth_service.py`）：

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.security import hash_password
from core.exceptions import UsernameExistsError, EmailExistsError
from models.user import User
from schemas.user import UserCreate

async def register(db: AsyncSession, user_create: UserCreate) -> User:
    existing = await db.execute(select(User).where(User.username == user_create.username))
    if existing.scalar_one_or_none():
        raise UsernameExistsError(f"用户名 '{user_create.username}' 已被占用")

    existing = await db.execute(select(User).where(User.email == user_create.email))
    if existing.scalar_one_or_none():
        raise EmailExistsError(f"邮箱 '{user_create.email}' 已被注册")

    user = User(
        username=user_create.username,
        email=user_create.email,
        password_hash=hash_password(user_create.password),
        nickname=user_create.nickname,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    return user
```

- [ ] **Step 1**: 修改 `services/auth_service.py`

- [ ] **Step 2**: 验证 import
```bash
python -c "from services.auth_service import register; print(register.__doc__[:50])"
```

- [ ] **Step 3**: Commit
```bash
git add services/auth_service.py
git commit -m "feat(service): add auth_service.register with 业务异常

Q1 决策：重型 service（接 Pydantic schema、返回 ORM、抛业务异常）
详见 spec §4.2"
```

---

## Task 16: 写 api/exception_handlers.py

**Files:**
- Create: `api/exception_handlers.py`

**Interfaces:**
- Produces: `register_exception_handlers(app: FastAPI)` — 注册 4 个异常 → 状态码映射

**关键代码**（详见 spec §4.2 `api/exception_handlers.py`）：

```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from core.exceptions import UsernameExistsError, EmailExistsError, FitForgeException

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UsernameExistsError)
    async def username_exists_handler(request: Request, exc: UsernameExistsError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(EmailExistsError)
    async def email_exists_handler(request: Request, exc: EmailExistsError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "数据冲突，可能是 username 或 email 已被占用"},
        )

    @app.exception_handler(FitForgeException)
    async def fitforge_exception_handler(request: Request, exc: FitForgeException):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})
```

- [ ] **Step 1**: 创建 `api/exception_handlers.py`

- [ ] **Step 2**: 验证 import
```bash
python -c "from api.exception_handlers import register_exception_handlers; print('ok')"
```

- [ ] **Step 3**: Commit
```bash
git add api/exception_handlers.py
git commit -m "feat(api): add exception handlers mapping 业务异常 → HTTP

Q2 决策：业务异常体系
详见 spec §4.2"
```

---

## Task 17: 写 api/auth.py (POST /auth/register)

**Files:**
- Modify: `api/auth.py`（替换占位）

**Interfaces:**
- Produces: `router` (APIRouter) + `POST /auth/register` 端点
- 接受: `UserCreate` (Pydantic 自动校验) + `AsyncSession` (Depends)
- 返回: `UserRead` + 201

**关键代码**（详见 spec §4.2 `api/auth.py`）：

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from schemas.user import UserCreate, UserRead
from services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await auth_service.register(db, user_create)
    return UserRead.model_validate(user)
```

- [ ] **Step 1**: 修改 `api/auth.py`

- [ ] **Step 2**: 创建 `services/__init__.py`（空文件）

- [ ] **Step 3**: 验证 import
```bash
python -c "from api.auth import router; print(router.routes)"
```
预期：1 个 POST route

- [ ] **Step 4**: Commit
```bash
git add api/auth.py services/__init__.py
git commit -m "feat(api): add POST /auth/register endpoint

Q3 决策：Depends async generator 注入 session
详见 spec §4.2"
```

---

## Task 18: 修改 main.py 挂载路由 + 注册异常处理

**Files:**
- Modify: `main.py`

**关键代码**（完整版在 spec §4.2 `main.py`）：

```python
from fastapi import FastAPI
from api.auth import router as auth_router
from api.exception_handlers import register_exception_handlers

app = FastAPI(title="FitForge API", version="0.1.0")

register_exception_handlers(app)
app.include_router(auth_router)

@app.get("/")
async def root():
    return {"message": "FitForge API", "version": "0.1.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 1**: 修改 `main.py`

- [ ] **Step 2**: 启动服务（后台）
```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform"
uvicorn main:app --reload --port 8000 &
sleep 3
```

- [ ] **Step 3**: 验证 /docs
```bash
curl http://localhost:8000/docs | head -20
```
预期：HTML 文档页面

- [ ] **Step 4**: Commit
```bash
git add main.py
git commit -m "feat(main): mount auth router + register exception handlers

详见 spec §4.2"
```

---

## Task 19: 写 tests/test_auth.py 端到端测试

**Files:**
- Create: `tests/test_auth.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`（配置 pytest-asyncio）

**关键代码**（详见 spec §7 测试用例）：

```python
# tests/conftest.py
import pytest_asyncio
from httpx import AsyncClient
from main import app

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c

# tests/test_auth.py
import pytest

@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post("/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "Password123",
        "nickname": "Alice",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "alice"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data

@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    payload = {"username": "bob", "email": "bob@example.com", "password": "Password123"}
    await client.post("/auth/register", json=payload)
    payload2 = {"username": "bob", "email": "bob2@example.com", "password": "Password123"}
    resp = await client.post("/auth/register", json=payload2)
    assert resp.status_code == 409

@pytest.mark.asyncio
async def test_register_weak_password(client):
    resp = await client.post("/auth/register", json={
        "username": "charlie", "email": "charlie@example.com", "password": "12345678"
    })
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_register_missing_email(client):
    resp = await client.post("/auth/register", json={
        "username": "dave", "password": "Password123"
    })
    assert resp.status_code == 422
```

- [ ] **Step 1**: 创建 `tests/conftest.py`

- [ ] **Step 2**: 创建 `tests/__init__.py`

- [ ] **Step 3**: 创建 `tests/test_auth.py`

- [ ] **Step 4**: 跑测试
```bash
pytest tests/test_auth.py -v
```
预期：4 个测试都过（注意：需要在测试前清空 users 表避免重复）

- [ ] **Step 5**: Commit
```bash
git add tests/
git commit -m "test(auth): add 4 end-to-end tests for /auth/register

覆盖：成功 / username 重复 / 弱密码 / email 缺失
详见 spec §7"
```

---

## Task 20: 端到端 smoke test (curl)

**Files:** 无

- [ ] **Step 1**: 启动服务（后台）
```bash
uvicorn main:app --port 8000 &
sleep 2
```

- [ ] **Step 2**: curl 成功注册
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"Password123","nickname":"Alice"}'
```
预期：`201` + `{"id":1,"username":"alice","nickname":"Alice"}`

- [ ] **Step 3**: curl 重复 username
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice2@example.com","password":"Password123"}'
```
预期：`409` + `{"detail":"用户名 'alice' 已被占用"}`

- [ ] **Step 4**: curl 弱密码
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"weak","email":"weak@example.com","password":"12345678"}'
```
预期：`422`

- [ ] **Step 5**: 关闭后台 uvicorn
```bash
kill %1 2>/dev/null
```

- [ ] **Step 6**: 在 README 或 docs 加 curl 示例（可选）

---

## Task 21: 同步到服务器 + 服务器跑 alembic + 端到端验证

**Files:** 无

- [ ] **Step 1**: 同步代码到服务器（用 git 或 scp）
```bash
# 用 git（如果已 push）或 scp
# 简化方案：用 Cursor Remote SSH 编辑器同步整个项目
```

- [ ] **Step 2**: SSH 到服务器
```bash
ssh fitforge  # 用 SSH 别名
```

- [ ] **Step 3**: 服务器安装新依赖
```bash
cd ~/fitforge  # 服务器项目目录
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 4**: 配置服务器 .env
```bash
cp .env.example .env
# 编辑 .env，把 DATABASE_URL 改为服务器 MySQL
```

- [ ] **Step 5**: 服务器 alembic upgrade
```bash
alembic upgrade head
```

- [ ] **Step 6**: 服务器启动 + curl
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"serveruser","email":"server@example.com","password":"ServerPass1"}'
```
预期：`201`

- [ ] **Step 7**: 服务器 mysql 验证
```bash
mysql -u fitforge -pfitforge_dev_password_2026 fitforge -e "SELECT id, username, email, nickname FROM users WHERE username='serveruser';"
```
预期：1 行

- [ ] **Step 8**: 关闭服务器 uvicorn
```bash
kill %1 2>/dev/null
exit  # 退出 SSH
```

---

## Task 22: 知识沉淀 + 更新进度

**Files:**
- Create: `tech_notes/2026-07-06-fastapi-register-flow.md`
- Create: `tech_notes/2026-07-06-async-sqlalchemy-pattern.md`
- Modify: `project_progress.md`

- [ ] **Step 1**: 写 `tech_notes/2026-07-06-fastapi-register-flow.md`
  - 内容：POST /auth/register 完整数据流 + 6 决策回顾 + 面试话术

- [ ] **Step 2**: 写 `tech_notes/2026-07-06-async-sqlalchemy-pattern.md`
  - 内容：async engine + Depends get_db + async_sessionmaker 三件套 + 面试话术

- [ ] **Step 3**: 更新 `project_progress.md` 勾选周三所有 TODO 为 `[x]`

- [ ] **Step 4**: Commit
```bash
git add tech_notes/2026-07-06-*.md project_progress.md
git commit -m "docs(notes): add 2 tech notes + update project_progress

详见 D19、spec §11"
```

---

## 总进度追踪

| Task | 状态 | 验收 |
|------|------|------|
| T1 安装依赖 | ⬜ | pip list 全装好 |
| T2 config.py | ⬜ | `from core.config import settings` 不报错 |
| T3 db.py | ⬜ | engine 创建成功 |
| T4 security.py | ⬜ | hash + verify 测试通过 |
| T5 exceptions.py | ⬜ | 异常继承正确 |
| T6 models/__init__ | ⬜ | Base 导出 |
| T7 models/user.py | ⬜ | User 类加载 |
| T8 models/user_goal.py | ⬜ | UserGoal 类加载 |
| T9 models/body_measurement.py | ⬜ | BodyMeasurement 类加载 |
| T10 alembic init | ⬜ | alembic current 不报错 |
| T11 users 表迁移 | ⬜ | DESC users 符合 D17 |
| T12 user_goals 表迁移 | ⬜ | DESC user_goals 符合 D17 |
| T13 body_measurements 表迁移 | ⬜ | DESC body_measurements 符合 D17 |
| T14 schemas/user.py | ⬜ | 4 个校验规则生效 |
| T15 services/auth_service.py | ⬜ | register 函数 import OK |
| T16 api/exception_handlers.py | ⬜ | 4 个 handler 注册成功 |
| T17 api/auth.py | ⬜ | POST /auth/register 路由存在 |
| T18 main.py 修改 | ⬜ | /docs 显示 |
| T19 tests/test_auth.py | ⬜ | pytest 4 个测试全过 |
| T20 curl smoke test | ⬜ | 3 个 curl 都返回预期状态码 |
| T21 服务器端到端 | ⬜ | 服务器注册成功 + DB 有记录 |
| T22 知识沉淀 | ⬜ | 2 个 tech_notes + 进度更新 |

---

## Execution Handoff

按 writing-plans 流程，plan 完成后给出 2 个执行选项：