# 把 `get_current_user` 从 `api/auth.py` 抽到 `core/security.py` —— 依赖方向 vs 循环 import

> **日期**：2026-08-16（周六补周五内容）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D39（get_current_user 抽到 core/security.py 避免循环 import）
> **关联 commit**：`c96ecbb`（refactor: move get_current_user from api/auth.py to core/security.py）、`429ac6e`（body routes 依赖新位置）、`8462a34`（goal routes 依赖新位置）
> **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md` §7.4
> **目的**：面试前复习 + Clean Architecture 依赖方向 + 解释为什么这次重构不只是"换个文件位置"

---

## 1. 重构前后位置对比

### 1.1 重构前（截止 commit `e23c120` 之前）

```python
# api/auth.py 第 116-139 行
_bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.get(User, int(user_id_str))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

**问题**：

- 路由层（api/auth.py）持有**鉴权逻辑**——这是基础设施逻辑
- 新增 `api/body.py` 或 `api/goal.py` 要鉴权时，需要 `from api.auth import get_current_user` —— 路由层 import 路由层
- 如果未来 `api/body.py` 想鉴权 → import api/auth.py；如果 `api/auth.py` 想 import `api/body.py`（如共用工具），就循环 import

### 1.2 重构后（commit `c96ecbb`）

```python
# core/security.py 末尾追加
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.exceptions import InvalidTokenError
from models.user import User
# decode_access_token 已在同文件，直接调用

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT and fetch current user. Raises 401 on invalid token."""
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.get(User, int(user_id_str))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

**关键**：函数体 100% 保留，只移动位置。

### 1.3 `api/auth.py` 清理（连带改动）

```python
# 删除原 get_current_user 函数定义 + _bearer_scheme 变量
# 删除不再使用的 imports：
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # 删除
# InvalidTokenError 不再 import（已移到 core）
# decode_access_token 不再 import（已在 core 内部）
```

**连锁清理收益**：api/auth.py 只剩路由定义（register/login/refresh/logout），与 body.py / goal.py 平行——不再是"特殊公共模块"。

---

## 2. 依赖方向原则（核心设计哲学）

### 2.1 Clean Architecture 分层

```
┌──────────────────────────────────────────┐
│  api/ (路由层)                             │  ← HTTP 适配
│  - api/auth.py / api/body.py / api/goal.py │
│  - 接收 HTTP 请求、返回 HTTP 响应               │
│  - 只做 ORM → DTO 转换 + 调用 service         │
└──────────────────────────────────────────┘
              ↓ 依赖
┌──────────────────────────────────────────┐
│  services/ (业务逻辑层)                       │  ← 业务规则
│  - services/auth_service.py                │
│  - services/measurement_service.py         │
│  - services/goal_service.py                │
│  - 接 Pydantic schema → 出 ORM → 抛业务异常     │
└──────────────────────────────────────────┘
              ↓ 依赖
┌──────────────────────────────────────────┐
│  core/ (基础设施层)                          │  ← 通用能力
│  - core/db.py (数据库 session)               │
│  - core/security.py (鉴权 + JWT 编解码)        │ ← get_current_user 在这里
│  - core/exceptions.py (业务异常基类)            │
│  - core/config.py (配置)                     │
└──────────────────────────────────────────┘
              ↓ 依赖
┌──────────────────────────────────────────┐
│  models/ (数据模型) + schemas/ (DTO)         │  ← 数据
└──────────────────────────────────────────┘
```

**依赖方向**：上 → 下，**绝对不允许反向**。

- `api/` 可以 `import core/`、`import services/`、`import models/`
- `services/` 可以 `import core/`、`import models/`、`import schemas/`
- `core/` 只能 `import models/`、`import schemas/`（**绝对不能** import api 或 services）

### 2.2 为什么 `get_current_user` 必须在 core

它做了 3 件事：

1. **解析 HTTP Header**（`HTTPAuthorizationCredentials`）—— 这是 HTTP 适配
2. **JWT 解码**（`decode_access_token`）—— 这是基础设施（密码学）
3. **查 DB 拿 user**（`db.get(User, ...)`）—— 这是数据访问

虽然它被路由层用（作为 Depends），但它**做的事情是"通用鉴权中间件"**——任何路由（不只 auth）都可能用。

**判断标准**：如果未来我写一个 CLI 脚本（不经过 HTTP），它还需要鉴权吗？需要——CLI 应该也能"假装某个用户"调业务逻辑。所以鉴权必须能在路由层外复用 → 必须在 core。

### 2.3 重构前的"乱伦"问题

```python
# api/body.py（新写的路由）
from core.db import get_db
from api.auth import get_current_user  # ← 路由层 import 路由层！奇怪的耦合
```

这导致：

- `api/auth.py` 是"特殊公共模块"，其他路由都要 import 它
- 一旦 `api/auth.py` 想 refactor（比如拆出 `api/auth_routes.py` + `api/auth_deps.py`），会牵动所有其他路由
- 单元测试要测鉴权逻辑，得 import api 层——本末倒置

> **面试话术**：「依赖方向必须单向：从业务流向基础设施。`get_current_user` 是鉴权基础设施，不是 auth 路由的私货——任何路由都可能用。我把它抽到 `core/security.py`，让 `api/body.py`、`api/goal.py` 都从 core import，符合 Clean Architecture。重构后 `api/auth.py` 跟其他路由平行（都是 APIRouter + 路由），不再是'公共仓库'。」

---

## 3. W6 风险：循环 import 的经典场景

### 3.1 循环 import 的本质

```python
# 文件 A
from b import something  # Python 加载 A，先 import b

# 文件 B
from a import something_else  # 加载 b 时想 import a —— 但 a 还没加载完！循环！
```

**症状**：`ImportError: cannot import name 'X' from partially initialized module 'A'`

### 3.2 为什么 `get_current_user` 在 `api/auth.py` 会引发循环

```python
# 场景 1：api/auth.py 持有 get_current_user
# api/auth.py 注册了 /auth/login /auth/me 等路由
# 路由函数里 Depends(get_current_user)
# 现在写 api/body.py
# api/body.py 想鉴权 → from api.auth import get_current_user
# 这本身不循环（auth 不 import body）

# 但是！假设未来 api/auth.py 想复用 body 的某些工具
# 比如统一错误响应格式
# api/auth.py → from api.body import error_formatter
# api/body.py → from api.auth import get_current_user
# 💥 循环 import
```

更阴险的场景：

```python
# api/auth.py 注册路由时 import 了别的路由模块
# 或者 main.py 同时加载所有路由时，模块初始化顺序出问题
```

### 3.3 抽到 core 后为什么安全

```python
# core/security.py（基础设施层）
# 它只 import 下层的东西
from core.db import get_db
from models.user import User
# 不 import 任何 api/* 或 services/*

# api/auth.py / api/body.py / api/goal.py 都从 core import
from core.security import get_current_user
# 单向依赖，不会循环
```

**规则**：`core/*` 不能 import `api/*` 或 `services/*`——这是 Clean Architecture 的硬约束。违反了就重构。

> **面试话术**：「循环 import 的本质是'依赖方向错了'。我把 `get_current_user` 抽到 core 是为了让依赖方向变成'路由 → 基础设施'的单向箭头。如果 `core/security.py` 反过来 import api 任何东西，就是 Clean Architecture 失守——那就要立刻重构，而不是'将就'。」

---

## 4. 本次重构触发的连锁改动

### 4.1 `api/auth.py` 删除 unused imports

```python
# 删除前（重构前 api/auth.py 顶部）
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # ← 现在没人用了
from sqlalchemy.ext.asyncio import AsyncSession  # ← 现在没人用了
# decode_access_token 和 InvalidTokenError 也不再 import（已移到 core）
```

**为什么必须删 unused imports**：

- 静态分析工具（flake8 / ruff）会报 `F401 imported but unused`
- 阅读代码的人看到 import 会以为有用，浪费认知
- 未来 import 路径变化时，未使用的 import 是"幽灵依赖"

### 4.2 11 个路由的 sanity 验证

| 路由文件             | 路由数 | 依赖 `get_current_user` |
| ---------------- | --- | -------------------- |
| `api/auth.py`    | 5   | /me（其他用 HTTPException） |
| `api/body.py`    | 6   | 全部                  |
| `api/goal.py`    | 4   | 全部                  |
| **总计**           | **15** | **11 个端点 Depends(get_current_user)** |

迁移后启动 uvicorn：

```bash
python -c "from api.auth import router; from core.security import get_current_user; print('OK')"
# OK
```

应用启动后：

```bash
curl -s http://127.0.0.1:8000/openapi.json | python -c "
import sys, json
d = json.load(sys.stdin)
print('total paths:', len(d['paths']))
"
# total paths: 15
```

**15 = 11 个业务路由 + 4 个 FastAPI 默认（/openapi.json / /docs / /docs/oauth2-redirect / /redoc）**

迁移未破坏任何现有功能。

### 4.3 重构 commit 的策略

```bash
git add core/security.py api/auth.py
git commit -m "refactor: move get_current_user from api/auth.py to core/security.py (D39)"
```

**为什么 1 个 commit 包含 2 个文件**：

- `core/security.py` 加新函数 + `api/auth.py` 删旧函数——是**同一个原子操作**
- 如果拆 2 个 commit，中间状态会出现"两个地方都定义 get_current_user"或"都没定义"——损坏的中间态

> **面试话术**：「重构 commit 必须是原子的——'移动'操作要 1 个 commit 包含'源删除 + 目标添加'。否则中间态是损坏代码，git bisect 找不到干净状态。这是 git 进阶用法的核心：`git mv` 不够，因为还涉及 import 路径调整；只能手写 commit message 说明原子性。」

---

## 5. 测试 / run-time sanity

### 5.1 单元测试不受影响（spec §8）

```python
# tests/test_auth.py（已有）
def test_get_current_user_no_token():
    # 不变，仍然测 401
    ...

def test_get_current_user_invalid_token():
    # 不变
    ...
```

测试只测**行为**（401 / 200），不测**位置**（core vs api）。所以迁移不影响。

### 5.2 e2e 测试不受影响（dc98286 / db4e682）

```python
# tests/test_body_routes.py / test_goal_routes.py
async def test_patch_measurement_422_extra_field(client, auth_headers):
    # auth_headers fixture 内部走 /auth/login 拿 token
    # → 注入 Bearer token 到 header
    # → 请求到 /body-measurements/{id} PATCH
    # → Depends(get_current_user) 触发（路径变了但行为不变）
    # → 业务逻辑照常跑
    ...
```

### 5.3 smoke 脚本（commit `9f4f927`）

```bash
# scripts/smoke_body_crud.sh
# 完整链路：register → login → POST measurement → GET list → PATCH → DELETE
# 验证 11 个路由都通
```

部署后 smoke 全过 → 重构无副作用。

---

## 6. 面试话术（综合 ≥ 3 句）

> 「Clean Architecture 的依赖方向是单向的：路由 → 服务 → 基础设施 → 模型。`get_current_user` 本质是鉴权基础设施，不是 auth 路由的私货——body / goal / 任何未来路由都可能用。我把它从 `api/auth.py` 抽到 `core/security.py` 就是为了让依赖方向变成'所有路由 → core'的单向箭头，避免 api 层互相 import 形成循环。这跟六边形架构（端口-适配器）的'端口在里、适配器在外'是同一个原则——基础设施是'端口'，路由是'适配器'，适配器依赖端口而非反过来。」
>
> 「循环 import 的本质是'依赖方向错了'。症状是 `ImportError: cannot import name 'X' from partially initialized module`，根因是 A import B 同时 B import A。Python 加载 A 时想加载 B，加载 B 时又想加载 A——死锁。解法不是 `import` 函数里延迟（治标），而是重新设计依赖方向（治本）：让公共部分下沉到下层（core/services），上层单向 import 下层。」
>
> 「重构 commit 必须是原子的：'移动'操作要 1 个 commit 包含'源删除 + 目标添加'。如果拆 2 个 commit，中间态会出现重复定义或都未定义——git bisect 找不到干净状态。我项目里 `c96ecbb` 一个 commit 同时改了 `core/security.py`（新增）和 `api/auth.py`（删除），保持重构原子性。这是 git 进阶用法的核心：commit message 不只描述做了什么，还要描述'为什么这一坨改动必须在一起'。」

---

## 7. 踩坑清单


| 坑                                       | 现象                       | 解法                                          |
| --------------------------------------- | ------------------------ | ------------------------------------------- |
| `get_current_user` 留在 `api/auth.py`    | 新增路由都要 `from api.auth import` —— 路由耦合 | 抽到 `core/security.py`                       |
| core 层 import api 或 services            | 循环 import + 架构失守         | 重构：把 core 用到的东西下沉到 core                  |
| 重构拆成 2 个 commit                         | 中间态损坏（重复定义或都没）          | 1 个原子 commit 包含源删 + 目标加                    |
| 重命名后没改 import                          | ImportError              | 全局 grep `get_current_user` 找引用              |
| 路由层 try/except HTTPEception            | 401 不一致                  | 用业务异常 + handler                            |
| `from core.security import decode_access_token` | core 内自引用                  | 直接调用本文件内函数，不写 `from core.security import` |

---

## 8. 关联

- **关联决策**：
  - **D39**：get_current_user 抽到 core/security.py（spec §7.4）
  - 间接影响 D32-D38：所有依赖鉴权的路由（body / goal）都用新位置的 get_current_user
- **关联 commit**：
  - `c96ecbb`：refactor: move get_current_user from api/auth.py to core/security.py (D39)
  - `429ac6e`：feat(api) add 6 body-measurements routes（依赖新位置）
  - `8462a34`：feat(api) add 4 user-goals routes（依赖新位置）
- **关联 spec**：`docs/superpowers/specs/2026-08-16-body-crud-design.md` §7.4
- **关联 plan**：`docs/superpowers/plans/2026-08-16-body-crud-plan.md` Task 7 + W6

---

**沉淀状态**：✅ 用户于 2026-08-16 批准落盘（与 Phase 5 T16 一并 commit）
