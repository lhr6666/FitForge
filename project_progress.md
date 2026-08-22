# 智能训练管理平台 - 项目进度跟踪

> 本文件由 Claude Code 协助维护，记录每周开发进度、技术债务与里程碑。
> 更新原则：每周结束前必须更新一次；重大变更（架构调整、技术选型）即时追加。

---

## 项目基本信息

- **项目名称**：智能训练管理平台（产品名 **FitForge**）
- **开发周期**：24 周
- **开发模式**：结对开发（用户主导决策，Claude Code 协助落盘与解释）
- **目标环境**：Python 3.10+，本地开发 → Ubuntu 22.04 云服务器部署
- **启动日期**：2026/06/30
- **当前阶段**：第 1 周第 2 天（周二）⏳ 进行中

---

## 项目目录结构（已落地）

```
FitForge/  （本地目录：Intelligent_training_management_platform/）
├── .env.example              # 配置模板（不入 Git）
├── .gitignore                # 排除 .env / keys/ / .docx
├── README.md                 # 产品门面（已补全）
├── CLAUDE.md                 # 协作规则
├── main.py                   # FastAPI 入口（/ + /health）
├── requirements.txt          # 5 个核心包 + 详细注释
├── project_progress.md       # 本文件
├── api/                      # 路由层（占位）
├── core/                     # 配置 / db / security / logging
├── models/                   # user / body_measurement / user_goal
├── schemas/                  # Pydantic 请求/响应体
├── services/                 # user_service / auth_service
├── alembic/                  # 周三 alembic init
├── keys/                     # RSA 密钥（不入 Git）
├── tests/                    # 后续填
├── tech_notes/               # 技术笔记
│   └── 2026-07-01-git-essentials.md
└── error_logs/               # 报错记录（暂空）
```

> 严格遵循 CLAUDE.md「严格分层架构」红线。

---

## 技术栈规划


| 周次   | 主题                             | 关键技术                                                               | 状态     |
| ---- | ------------------------------ | ------------------------------------------------------------------ | ------ |
| 0    | 项目初始化                          | -                                                                  | ✅ 已完成  |
| 1    | Git + FastAPI + JWT + MySQL 骨架 | FastAPI / SQLAlchemy 异步 / MySQL / Argon2id / PyJWT RS256 / Alembic | 🚧 进行中 |
| 2-24 | 核心算法 + AI + 性能优化               | TBD                                                                | ⏳      |


---

## 每周开发日志

### 第 0 周（2026/06/30）- 项目初始化

**目标**：

- [x] 阅读并确认 CLAUDE.md 协作规则
- [x] 创建 tech_notes/ 与 error_logs/ 目录
- [x] 创建 project_progress.md 与 requirements.txt

**产出**：

- 项目骨架已建立，分层目录待后续按需创建

**遇到的问题**：

- 无

**下一步**：

- 等待用户下达"开始第 1 周任务"指令，进入标准 7 步闭环

---

### 第 1 周 第 1 天 - 周一（2026/07/01）- Git + 项目骨架

**目标**：

- [x] 创建 FitForge GitHub 仓库
- [x] 头脑风暴 12 项技术选型（D1-D12）
- [x] 编写 README（产品定位 + 三大创新点，humanizer-zh 处理）
- [x] 搭建极简骨架（api/core/models/schemas/services）
- [x] 编写最小 main.py（/ + /health）
- [x] 编写 .env.example / .gitignore / requirements.txt
- [x] 本地 git init + 配置 user + 首次 commit
- [x] 写 tech_notes/2026-07-01-git-essentials.md

**产出**：

- 25 个文件首次 commit（commit hash: `1232c38`）
- Conventional Commits 规范的 commit message
- 8 项重大决策 + 8 条面试话术沉淀

**遇到的问题**：

1. 父目录是 monorepo（my_coding_projects）跟踪多个项目
  - **解法**：在 FitForge 子目录内 `git init` 形成嵌套仓库
2. `云服务器相关知识与注意事项.docx` 在 untracked 列表
  - **解法**：加入 .gitignore 排除（防止误推敏感信息）

**下一步**：

- 周二：Linux + 云服务器 + SSH + 跑通 /docs

---

### 第 1 周 第 2 天 - 周二（2026/07/02）- Linux + SSH + 云服务器

**目标**：

- [x] 本地跑通 FastAPI `/docs`（昨天遗留，今日已验证）
- [x] 购买/确认云服务器（用户已有腾讯云 CVM：114.132.83.99，Ubuntu 22.04）
- [x] SSH 密钥对生成（ed25519，路径 `D:/ssh/id_ed25519`）
- [x] SSH config 配置（别名 `fitforge`）
- [x] 解决首次登录问题（腾讯云控制台绑定密钥对 + 重置密码）
- [x] SSH 成功登录服务器（`ubuntu@VM-0-15-ubuntu`）
- [x] ~~服务器装 Python 3.10 + pip + venv~~（用户口头确认已完成，未截图，按 CLAUDE.md「汇报真实」记账）
- [x] ~~服务器装 MySQL 8.0 + 初始化数据库~~（同上）
- [x] Cursor Remote SSH 配置成功（修复 Windows 私钥权限问题，见 D18）
- [x] tech_notes/2026-07-02-ssh-essentials.md
- [x] tech_notes/2026-07-02-linux-cloud-server.md
- [x] error_logs/2026-07-02-ssh-troubleshooting.md
- [x] tech_notes/2026-07-02-fastapi-docs.md（**补记**：用户发现"接口文档"内容当时口头讨论过但未落盘）
- [x] tech_notes/2026-07-02-mvp-blueprint-design.md（MVP schema 设计：3 张表完整字段 + 7 条关键决策 + alembic 迁移计划）

**产出**：

- SSH 端到端打通（本地 → 腾讯云服务器）
- 4 个文档补全：项目进度、SSH 错误日志、SSH 知识、Linux 知识
- 4 个新决策 D13-D16 落盘
- **补记**：`tech_notes/2026-07-02-fastapi-docs.md`（4 端点验证 + 3 个面试亮点：代码即文档 / openapi.json 契约 / 类型注解驱动校验）
- **MVP schema 蓝图**：`tech_notes/2026-07-02-mvp-blueprint-design.md`（头脑风暴产出）
- **Cursor Remote SSH 调试**：解决 Windows 私钥权限严格性问题（详见 `error_logs/2026-07-06-cursor-ssh-permission.md`）
- **服务器环境装完**：Python 3.10 + pip + MySQL 8.0 + fitforge 库 + fitforge 用户（用户口头确认；密码 `fitforge_dev_password_2026` 仅开发用）

**遇到的问题**：

1. SSH `Connection closed by 114.132.83.99 port 22`
  - **原因**：腾讯云 Ubuntu 默认禁用密码认证，公钥未传到服务器
  - **解法**：控制台 → 重置 ubuntu 密码 + 绑定 SSH 密钥对 + 重启实例
  - **详见**：`error_logs/2026-07-02-ssh-troubleshooting.md`
2. `chmod 600` 在 Windows 上无效
  - **原因**：NTFS 不支持 Unix mode
  - **解法**：直接测试 SSH 能否工作，忽略 `ls` 显示的 mode

**下一步**：

- 周二晚：服务器装 Python + MySQL
- 周三：SQLAlchemy + Pydantic + /auth/register

**补记**（2026/07/02 当日复盘时发现）：

- "跑通 /docs + 3 个面试亮点"当时口头讨论过，但没落盘
- 已在 `tech_notes/2026-07-02-fastapi-docs.md` 补全
- **教训**：按新 CLAUDE.md「文档维护红线」应**事件触发立刻记录**，不再"口头讨论过 = 已完成"

---

### 第 1 周 第 3 天 - 周三（2026/07/06）- /auth/register 设计

**目标**：

- [x] 完成 /auth/register 端点 brainstorming（6 决策问答）
- [x] 撰写并 review 设计文档
- [x] git commit spec 文档
- [x] 调 writing-plans skill 创建实施计划（22 tasks）
- [x] 实施 plan T1-T13（大块 1+2+3：环境/DB/3 model/Alembic）— 14 commit
- [x] Docker 容器化本地 MySQL + Volume 持久化（D26 决策）
- [x] 实施 plan T14-T20（大块 4+5：Pydantic/service/路由/测试/smoke）— 7 commit
- [x] 实施 plan T21：服务器端到端（4 个 curl 测试全过：201/409/422/422）
- [x] 实施 plan T22：知识沉淀 + 收尾

**周二 2026-08-13 增量（Task 21/22 完成）**：

- **Task 21 服务器端到端**：
  - 上传代码（scp 失败 → tar 替代，详见 D 决策日志）
  - 服务器 venv + 13 个依赖
  - 修改 fitforge 用户 plugin（caching_sha2 → mysql_native_password，避开 cryptography 依赖）
  - **修改密码为 lhr076200**（D27 决策）
  - alembic upgrade head 建 3 张表
  - uvicorn 启动 + /health 200
  - 4 个端到端 curl 测试全过：201/409/422/422
- **Task 22 知识沉淀**：
  - `error_logs/2026-08-13-cryptography-caching-sha2-fix.md`（D27 关联）
  - `tech_notes/2026-08-13-server-deploy-record.md`（5 步部署 + 5 个真实踩坑 + 面试话术）

**完整产出统计（周三 + 周二增量）**：

- 21 个 commit（commit 链：f658413 → 2188dd4 → ... → 0460a14）
- 7 篇 tech_notes + 1 篇 error_log + 1 篇 deploy doc
- 19 项重大决策落盘（D1-D19）+ 2 项增量（D26-D27）
- 完整 /auth/register 端到端：本地 + 服务器**两边都跑通**

**产出**：

- `docs/superpowers/specs/2026-07-06-auth-register-design.md`（585 行，commit `391a149`）
- 6 决策：重型 service / 业务异常 / Depends / 2 schema / 中等密码 / 强制 email
- 21 个实施 TODO 组织为 6 大块
- 详见 D19 决策

**遇到的决策**：

- 6 个原子决策（Q1-Q6）都是 brainstorming 产物，详见 spec §2

**下一步**：

- 调 writing-plans skill 创建详细实施计划
- 按 6 大块逐个落盘代码

### 第 1 周 第 4 天 - 周四（2026/08/14）- /auth/login + refresh + logout

**目标**：

- [x] brainstorming 4 决策（Q1 token 机制 / Q2 logout / Q3 payload / Q4 中间件）
- [x] 写 spec v1 + 走 review
- [x] 调 writing-plans skill 创建 10-task plan
- [x] 实施 plan 10 个 task（11 commit）
- [x] 写综合 tech_notes 沉淀（461 行）
- [ ] 服务器端到端验证（下次部署时一起做）

**产出**：

- `docs/superpowers/specs/2026-08-14-auth-login-design.md`（585 行，commit `1d81d0c`）
- `docs/superpowers/plans/2026-08-14-auth-login-plan.md`（1249 行，commit `9eb5329`）
- 4 新增决策：D28（双 token + rotate）/ D29（DB 存 jti）/ D30（revoke 字段）/ D31（统一错误消息）
- 4 新端点 + 1 中间件：POST /auth/login + POST /auth/refresh + POST /auth/logout + GET /auth/me + Depends(get_current_user)
- 1 新表：refresh_tokens（6 列 + 4 索引）
- 测试：9/9 pytest + 14/14 smoke 全过
- 详见 tech_notes/2026-08-14-auth-jwt-rotation.md（commit `e4ba047`）

**完整 commit 链（周四 11 个）**：

```
da04aec  feat(security): add JWT create/decode (RS256)
d11fbf4  feat(exceptions): add InvalidCredentials + InvalidToken
bf57200  feat(models): add RefreshToken ORM
43515c7  feat(db): refresh_tokens alembic migration
6e17323  feat(schemas): add LoginRequest + RefreshRequest + TokenResponse
f97bb9b  feat(service): add login + refresh + logout (rotate)
46cc077  feat(api): add 401 handlers (WWW-Authenticate: Bearer)
e23c120  feat(api): add 4 routes + get_current_user
79bccc2  test(auth): add 5 e2e tests
1aa7c11  test(smoke): add 7 curl tests
e4ba047  docs(notes): add auth login complete tech notes
```

**遇到的真踩坑**：

- D27 疏漏：本地 Docker MySQL fitforge 密码没改（Access denied 报错过）
- datetime naive vs aware：MySQL DateTime naive vs datetime.now(UTC) aware
- access token 断言错误：rotate 后 access 内容相同（jti 才唯一）
- Edit 找不到字符串：linter 加中文注释改变了文件
- LoginRequest 弱密码预期错误：登录不校验强度（注册才校验）

**关键设计（D28）**：

> 双 token + refresh rotate —— access 30min + refresh 14day + 每次 refresh 作废旧 refresh 签发新 refresh。
> 防重放攻击：攻击者拿到旧 refresh 时，DB 已 revoked → 401。

**下一步**（按原计划，now 已修正）：

- 周五（2026-08-15）：body_measurements + user_goals CRUD → 周六补
- 周六（2026-08-16）：见下文「第 5 天 - 周六补 周五」+ 原计划 git push
- 周日：周报 + 复盘

---

### 第 1 周 第 5 天 - 周六补 周五内容（2026/08/16）- body_measurements + goals CRUD 设计

> **状态**：头脑风暴 + 任务拆解完成（spec + plan 已 commit），**编码未开始**

**目标**：

- [x] 调用 brainstorming skill → Q1-Q8 决策产出（Q1-Q3 用户拍板，Q4-Q8 推荐默认）
- [x] 写 spec v1 + 用户 review 通过
- [x] 调 writing-plans skill → 16 task 实施计划
- [x] 自审 spec + 自审 plan（Placeholder / 一致性 / 范围 / 模糊性 4 项）
- [x] spec commit（`2ab935e`，1003 行）+ plan commit（`a2785d2`，1614 行）
- [x] Task 1-16 编码落地（**未开始**）

**产出**：

- `docs/superpowers/specs/2026-08-16-body-crud-design.md`（commit `2ab935e`）
- `docs/superpowers/plans/2026-08-16-body-crud-plan.md`（commit `a2785d2`）

**8 个新决策（D32-D39）**：

- D32：URL 平铺 RESTful（/body-measurements、/user-goals）
- D33：measurements 两个创建端点（单 + /batch），整体事务，max 50 条
- D34：measurements PATCH 仅允许 notes / recorded_at（体重等不可改）
- D35：goals PATCH 全 5 字段（type / target_value / status / deadline / notes）
- D36：measurements 硬删（DELETE） + goals 不实现 DELETE（走 PATCH status=abandoned）
- D37：列表 limit 上限 100、offset >= 0（业务保护）
- D38：跨用户访问返回 404（防 ID 枚举，与 GitHub 一致）
- D39：get_current_user 抽到 core/security.py（避免路由循环 import）

**11 个端点（10 实现 + 1 故意不实现）**：

- measurements 6：POST / POST /batch / GET / GET {id} / PATCH {id} / DELETE {id}
- goals 4：POST / GET（带 status 过滤）/ GET {id} / PATCH {id}
- ~~DELETE /user-goals/{id}~~ （Q5 不实现）

**Spec 8 风险坑点**：

- W1：datetime naive vs aware（D17-f）
- W2：SQLAlchemy db.get 必须显式 None check
- W3：PATCH schema 用 extra="forbid" 防字段误覆盖
- W4：PATCH 用 exclude_unset 防 None 清空字段
- W5：批量端点整体事务（依赖依赖倒置 fallback）
- W6：get_current_user 迁移位置（已落 D39）
- W7：测试环境数据库（MySQL fitforge_test schema）
- W8：测试 fixture 复用 auth_headers

**完整 16 task 计划**（详见 plan）：

- 大块 1：异常 + handler（T1-T2）
- 大块 2：Schemas（T3-T4）
- 大块 3：Service 层（T5-T7）
- 大块 4：路由层（T8-T10）
- 大块 5：测试（T11-T14）
- 大块 6：服务端到端 + 知识沉淀（T15-T16）

**预估产出**：

- 16 commit（每 task 一 commit）
- 8 个新文件 + 5 个修改文件 + 1 个 smoke 脚本
- 30+ 测试用例
- 3 篇 tech_notes（extra=forbid / get_current_user refactor / batch API 设计模式）

**遇到的决策**：

- Q1-Q3 已在 brainstorming 用户拍板
- Q4-Q8 推荐默认（待用户在 plan review / 编码前调整）

**下一步**：

- 用户确认 plan + 选择执行模式（subagent-driven 或 inline execution）→ 开始 Task 1 编码
- 编码完成后调 requesting-code-review skill 审
- 周日统一复盘：把周五补内容 + 周六部署内容拼起来写周报

---

## 第 1 周完整进度（4/7 天）


| Day | 内容                                      | commit | 状态           |
| --- | --------------------------------------- | ------ | ------------ |
| 周一  | 项目初始化                                   | 1      | ✅            |
| 周二  | 环境/服务器                                  | 2      | ✅            |
| 周三  | /auth/register                          | 22     | ✅            |
| 周四  | /auth/login + refresh + logout          | 11     | ✅            |
| 周五  | body_measurements + goals CRUD 设计 → 周六补 | 2      | 🚧 spec+plan |
| 周六  | body_measurements + goals CRUD 编码 + 测试  | 16     | ✅            |
| 周日  | 周报 + 复盘 + 部署                            | -      | ⬜            |


**总 commit 数**：54（21 + 11 + 4 其他 + 2 spec/plan + 16 Phase 1-4 编码）
**总决策数**：32（D1-D19 + D26 + D27 + D28-D31 + D32-D40）
**总 tech_notes**：9 篇
**总 error_log**：3 篇

---

## 待办 / 技术债务

- [x] ~~补充 README.md~~（周一已完成）
- [x] ~~添加 .gitignore~~（周一已完成）
- [x] ~~初始化 Git 仓库~~（周一已完成，本地 commit 1232c38，未推送）
- [x] ~~第 1 周技术选型确认~~（见下方「重大决策记录」D1-D16）
- [x] 推送首次 commit 到 GitHub（用户决定延后到周六部署前）
- [x] ~~周二：本地跑通 FastAPI /docs~~
- [x] ~~周二：确认云服务器（用户已有腾讯云 CVM）~~
- [x] ~~周二：SSH 密钥对生成 + 成功登录服务器~~
- [x] 周二晚：服务器装 Python 3.10 + MySQL 8.0
- [x] 周二晚或周三：与 Claude 一起设计 MVP 蓝图（users / body_measurements / user_goals 三表）

---

## 第 2 周后 技术债务（code review findings，2026-08-13）

- [ ] 1️⃣ 加 rate limiting（slowapi 库）— 安全风险
- [ ] 2️⃣ 加 logging（service + handler 层）— 运维友好
- [ ] 3️⃣ 合并 username/email 查重为单次 SQL — 性能优化（不是瓶颈）

## 周三 + 周二 增量 完整产出统计

- 22 个 commit（commit 链：f658413 → ... → 0460a14 → a2021e1 → code review）
- 8 篇 tech_notes + 1 篇 error_log + 1 篇 deploy doc + 1 篇 server deploy record
- 19 项重大决策落盘（D1-D19）+ 2 项增量（D26 Docker Volume + D27 密码 lhr076200）
- 完整 /auth/register 端到端：本地 + 服务器**两边都跑通**
- 7 个文件 code review 评分：9/10
- 4 个端到端测试全过：201/409/422/422

## 重大决策记录（头脑风暴输出）

> 决策一旦做出，全周不再回头讨论。所有决策必须能在面试中讲清楚"为什么"。

### D1. 蓝图缺失处理策略（2026/06/30）

- **决策**：先共建 MVP 版蓝图（仅含本周三张表）
- **理由**：避免周三 / 周五返工，符合"先设计后编码"工程规范
- **落地**：周二晚或周三开始前，与 Claude 一起设计 users / body_measurements / user_goals 三表

### D2. GitHub 账户信息（2026/06/30，2026/06/30 修正）

- **GitHub 用户名**：`lhr6666`（小写，GitHub URL 真实形式）
- **邮箱**：`1274810842@qq.com`
- **仓库 URL**：`https://github.com/lhr6666/FitForge.git`
- **本地配置**：`git config user.name "lhr6666"`，`git config user.email "1274810842@qq.com"`
- **仓库名**：`FitForge`
- **本地目录名**：`Intelligent_training_management_platform`（保留不动，避免影响 IDE 工作区）

### D3. MySQL 部署策略（2026/06/30）

- **决策**：Ubuntu 云服务器本地装 MySQL（apt install mysql-server）
- **理由**：零额外成本、调试方便、单服务场景足够
- **未来扩展**：若用户量增长，可迁移到云数据库 RDS（保留迁移接口）

### D4. ORM 同步/异步（2026/06/30）

- **决策**：SQLAlchemy 2.0 异步 + asyncmy
- **理由**：与 FastAPI async 生态契合、高并发优势、求职加分

### D5. JWT 库选型（2026/06/30）

- **决策**：PyJWT（弃用 python-jose）
- **理由**：python-jose 自 2022 后维护停滞；PyJWT 是 FastAPI 社区新主流

### D6. 密码哈希算法（2026/06/30）

- **决策**：Argon2id（passlib + argon2-cffi）
- **理由**：OWASP 2023+ 推荐；抗 GPU/ASIC 攻击更强（memory-hard）

### D7. JWT 签名算法（2026/06/30）

- **决策**：RS256（非对称，第一周直接上）
- **理由**：建立签发私钥 / 验证公钥的工程心智；为未来微服务拆分预留架构
- **配套**：openssl 生成 2048 位 RSA 密钥对；私钥不入 Git；预留 `kid` 头

### D8. 目录结构（2026/06/30）

- **决策**：极简骨架（首期）
  ```
  api/auth.py
  core/{config.py, db.py, security.py}
  models/{user.py, body_measurement.py, user_goal.py}
  schemas/{user.py, auth.py, body.py}
  services/{user_service.py, auth_service.py}
  main.py + .env.example + requirements.txt + alembic/
  ```
- **理由**：支撑本周 7 天任务；未来按需扩展子目录

### D9. 数据库迁移工具（2026/06/30）

- **决策**：引入 Alembic（周三首次建表就 `alembic init`）
- **理由**：周五会加表（body_measurements、user_goals），Alembic 让 schema 变更可追溯；生产部署可控；面试能讲"数据库 schema 也需要版本管理"
- **配套命令**：`alembic init alembic`、`alembic revision --autogenerate -m "create users table"`、`alembic upgrade head`

### D10. 依赖管理工具（2026/06/30）

- **决策**：uv（Rust 写的下一代包管理器）
- **理由**：速度极快（比 pip 快 10-100 倍）；兼容 pip 生态；pyproject.toml 是趋势；简历亮点
- **配套**：`uv venv` 创建虚拟环境；`uv pip install -r requirements.txt` 安装；或直接 `uv add fastapi` 管理

### D11. 配置管理（2026/06/30）

- **决策**：单一 .env + pydantic-settings（BaseSettings）
- **理由**：第一周单环境、单服务足够；未来按需拆 dev/prod
- **约定**：`.env` 不入 Git；`.env.example` 入 Git；敏感字段（DB 密码、JWT 私钥路径）走配置

### D12. 日志方案（2026/06/30）

- **决策**：logging 标准库（dictConfig 配置）
- **理由**：面试必问；零依赖；架构感强
- **落地**：`core/logging.py` 写 dictConfig，main.py 启动时加载

### D13. SSH 密钥类型：ed25519（2026/07/02）

- **决策**：从原计划的 RSA 改为 ed25519
- **理由**：ed25519 用 256 位密钥达到 RSA-2048 安全等级；签名验证快 10 倍；密钥文件小 8 倍；NIST 2019 推荐
- **落地命令**：`ssh-keygen -t ed25519 -f D:/ssh/id_ed25519 -C "fitforge@lhr6666"`

### D14. SSH 私钥路径：`D:/ssh/`（2026/07/02）

- **决策**：SSH 私钥放 `D:/ssh/`，与 RSA 私钥 `keys/` 分离
- **理由**：SSH 私钥是登录凭证（高频使用），RSA 私钥是 JWT 签发凭证（程序使用）——两类不同生命周期的密钥分开管理
- **配套**：`D:/ssh/` 加入 .gitignore 排除（其实默认就在用户目录里，已隐式排除）

### D15. SSH config 别名 `fitforge`（2026/07/02）

- **决策**：在 `~/.ssh/config` 配置别名
- **好处**：`ssh fitforge` 替代 `ssh -i D:/ssh/id_ed25519 ubuntu@114.132.83.99 -p 22`
- **配套**：`IdentitiesOnly yes` 防止 SSH agent 提供其他私钥

### D16. 腾讯云首次访问流程（2026/07/02）

- **决策**：通过控制台完成「重置 ubuntu 密码 + 绑定 SSH 密钥对 + 重启实例」三步
- **原因**：腾讯云 Ubuntu 默认禁用密码认证；首次访问公钥未传到服务器
- **教训**：云服务器首次 SSH 失败**不要反复试**——一定是密钥对没绑，去控制台查
- **不同云厂商流程对比**：腾讯云/阿里云走控制台绑定；AWS EC2 启动时直接选；GCP 走元数据

### D18. Windows SSH 私钥权限收紧策略（2026/07/06）

- **决策**：Windows 上私钥权限**永远用 `icacls`**，不用 `chmod`
- **命令**：`powershell -Command 'icacls "D:\ssh\id_ed25519" /inheritance:r /grant:r "$env:USERNAME:(R)"'`
- **原因**：① NTFS 不支持 Unix mode，`chmod` 是假动作；② Cursor Remote-SSH 严格检查 Unix mode，Git Bash OpenSSH 不严格——要按"最严"配置
- **教训**：跨 SSH 客户端时私钥权限要看"最小公倍数"——用最严的那个
- **详情**：`error_logs/2026-07-06-cursor-ssh-permission.md`

### D26. 本地 MySQL Docker 容器化 + Volume 持久化（2026/07/06）

- **决策**：
  1. 本地 MySQL 用 **Docker 容器**（不装 MySQL 安装包）
  2. 数据持久化用 **Docker named volume** `mysql_data`（不是 bind mount）
  3. 端口映射 `3307:3306`（避开 Docker Desktop 占用的 3306）
  4. **CREATE USER 时显式指定 `mysql_native_password`**（避免 caching_sha2 报错 + 不装 cryptography 包）
- **理由**：
  - 容器化：环境隔离、删容器即清环境、版本切换 1 命令
  - named volume：跨平台、Docker 自动管理、避 Windows 路径坑
  - 端口避开：Docker Desktop + WSL2 backend 预占常用端口
  - mysql_native_password：开发环境简化，pymysql 不需额外依赖
- **配套命令**（`docs/scripts/mysql-dev.sh`，未来整理）：
  ```bash
  docker run -d --name fitforge-mysql -p 3307:3306 \
    -v mysql_data:/var/lib/mysql \
    -e MYSQL_ROOT_PASSWORD=... \
    -e MYSQL_DATABASE=fitforge \
    -e MYSQL_ROOT_HOST=% \
    --restart unless-stopped mysql:8.0 \
    --character-set-server=utf8mb4 \
    --default-authentication-plugin=mysql_native_password
  ```
- **持久化验证**：stop + rm + 重跑容器 → alembic upgrade head 重建 schema 成功 → 3 张业务表 + 11 索引完整
- **下次开机流程**：Docker Desktop 自动启动容器（`--restart unless-stopped`）；schema 不丢；如需重建空库再跑 alembic upgrade head
- **文档**：`tech_notes/2026-07-06-docker-mysql-volume.md`

### D28. JWT 双 token + refresh rotate 机制（2026/08/14）

- **决策**：access 30min + refresh 14day + 每次 refresh 作废旧 refresh + 签发新 refresh
- **理由**：
  - access 短寿命 → 泄露风险低（30min 窗口）
  - refresh 长寿命 → 用户体验好（不用频繁登录）
  - rotate 防重放 → 攻击者拿到旧 refresh 时已 revoked
- **配套**：
  - `core/security.py` 加 4 个 JWT 函数（create_access_token / create_refresh_token / decode_access_token / decode_refresh_token）
  - `models/user.py` 加 RefreshToken 模型（jti + expires_at + revoked + 复合索引）
  - `core/exceptions.py` 加 InvalidCredentialsError + InvalidTokenError
  - `api/exception_handlers.py` 加 401 handler（含 WWW-Authenticate: Bearer）
  - `api/auth.py` 加 4 路由（login/refresh/logout/me）+ get_current_user 中间件
- **面试话术**：
  > "双 token + rotate 是 OAuth 2.0 业界标准——access 短寿命控泄露风险，refresh 长寿命保 UX，rotate 防止重放。我用 DB 存 jti 实现主动撤销 + rotate，避免 Redis 黑名单的单点依赖。"
- **关联 commit**：`da04aec` → `d11fbf4` → `bf57200` → `43515c7` → `6e17323` → `f97bb9b` → `46cc077` → `e23c120` → `79bccc2` → `1aa7c11`

### D29. refresh token DB 存储 + jti 字段（2026/08/14）

- **决策**：refresh token 写 DB（jti + expires_at + revoked），不存 Redis
- **理由**：
  - 可主动撤销（logout）
  - 可 rotate（防重放）
  - 可审计（用户登录历史）
  - MVP 阶段不引入新依赖
- **配套**：
  - 新表 `refresh_tokens`：id / user_id (FK CASCADE) / jti (UNIQUE UUID4) / expires_at / revoked / created_at
  - 复合索引 `(user_id, revoked)`：按 user_id 查 active token
- **面试话术**：
  > "我把 refresh token 写 DB 而不存 Redis——MVP 阶段不引入新依赖。每个 refresh 有唯一 jti（UUID4），DB 验证 `WHERE jti=? AND revoked=false AND expires_at > now()`。微服务架构也能共享 DB（不像 session 需要 sticky 或共享缓存）。"

### D30. refresh token 用 revoked 字段（不用 Redis 黑名单）（2026/08/14）

- **决策**：`revoked` boolean 字段 + 复合索引 `(user_id, revoked)`
- **理由**：
  - 单字段查询快（`WHERE jti=? AND revoked=false`）
  - 不引入新依赖
  - MVP 够用
  - 撤销延迟：access 30min 内仍可用（业界标准 trade-off）
- **配套**：
  - service.refresh_token 作废旧 refresh + 签发新 refresh
  - service.logout 设 revoked=True
- **未来**：用户量大时迁移 Redis（毫秒级撤销）

### D31. 登录错误统一消息"邮箱或密码错误"（2026/08/14）

- **决策**：用户不存在 + 密码错返回同一消息
- **理由**：
  - 防枚举攻击（攻击者通过响应差异探测哪些 email 已注册）
  - 业界标准（GitHub / Google / 各大厂）
- **配套**：
  - service.login 抛 InvalidCredentialsError
  - detail 字段固定写"邮箱或密码错误"（**绝对不能**分别说"邮箱不存在"和"密码错误"）
- **面试话术**：
  > "我统一返回'邮箱或密码错误'——防枚举攻击。攻击者无法通过响应差异探测哪些 email 已注册。代价是真实用户报错时少一些上下文（但可以靠'忘记密码'功能找回）。这是 OAuth 2.0 / 各大厂的安全最佳实践。"

### D27. 服务器 MySQL fitforge 用户密码改为 lhr076200（2026/08/13）

- **决策**：将 fitforge 用户密码从开发默认值 `fitforge_dev_password_2026` 改为用户自定义的 `lhr076200`
- **理由**：用户明确指定自定义密码，需要全链路同步
- **修改 3 处**：
  1. 本地 `.env`：`DATABASE_URL` + `SYNC_DATABASE_URL` 已改
  2. 服务器 fitforge 用户：`sudo mysql -e "ALTER USER 'fitforge'@'localhost' IDENTIFIED WITH mysql_native_password BY 'lhr076200'; FLUSH PRIVILEGES;"`
  3. 服务器 `.env`：重新写，新密码 lhr076200 + 端口 3306
- **同步机制**：`pydantic-settings` 从 .env 读 → 业务代码无感知（Q1 重型 service 模式）
- **教训**：
  - 改密码必须 3 处同步（本地 .env、服务器 fitforge 用户、服务器 .env）
  - 用 `sudo mysql` 绕过 auth_socket 验证 OS 用户
  - 改 plugin 避免 cryptography 依赖（详见 `error_logs/2026-08-13-cryptography-caching-sha2-fix.md`）

### D17. MVP 数据库 Schema 设计（2026/07/02）

- **决策**：3 张表完整字段已敲定，整合 4 个头脑风暴答案（多目标 + 完整 11 字段 + 实用预留 + username 登录）
- **文档**：`tech_notes/2026-07-02-mvp-blueprint-design.md`
- **7 条关键设计原则**：CASCADE / 复合索引 / 业务时间分离 / ENUM / 软硬删除组合 / UTC / 全表时间戳
- **NOT DO 清单**：软删除 / UUID 主键 / 审计日志 / Trigger / 分区表
- **下一步**：周三用 Alembic 落盘这 3 张表

### D19. /auth/register 端点 6 决策（2026/07/06）

- **决策**：6 个原子决策的合并（来自 brainstorming Q1-Q6）
  - Q1: 重型 service（service 接 Pydantic schema、返回 ORM、抛业务异常；路由层只做 HTTP 适配）
  - Q2: 业务异常体系（自定义异常 + exception_handler 映射）
  - Q3: async generator + Depends（session 生命周期与请求绑定）
  - Q4: 2 个 Pydantic schema（UserCreate + UserRead）
  - Q5: 中等密码强度（min_length=8 + 字母数字混合）
  - Q6: 强制必填 email
- **理由**：业务可复用 / 分层清晰 / YAGNI / 安全第一
- **配套**：
  - `core/exceptions.py`（FitForgeException 基类 + 子类）
  - `api/exception_handlers.py`（注册 handler）
  - `core/security.py`（Argon2id cost=12）
- **文档**：`docs/superpowers/specs/2026-07-06-auth-register-design.md`（spec 已 user review 通过）
- **面试话术**：
  > "我用业务异常体系而非 Result 模式：① Python 异常原生支持 try/except，调用者代码最简洁；② 业务异常与 HTTP 异常解耦——service 不知道有 HTTP，所以业务可复用（CLI/脚本/队列都直接调）；③ FastAPI 的 `add_exception_handler` 让一处定义映射、N 个端点受益。"
- **下一步**：按 spec §10 实施 TODO 执行 6 大块

### 待决项

（无，本周 19 项技术选型全部完成 — D1-D19）

---

### D32. body_measurements + user_goals URL 平铺 RESTful（2026/08/16）

- **决策**：URL 用资源平铺（`/body-measurements/*`、`/user-goals/*`），不带 `/users/me` 前缀
- **理由**：
  - 与现有 `/auth/*` 风格统一
  - "我的"语义由 `Depends(get_current_user)` 隐式表达，URL 不冗余
  - 未来支持教练场景可渐进迁移到 `/users/{user_id}/...`，不破坏既有客户端
- **关联**：spec `2026-08-16-body-crud-design.md` §1.2 + §3 端点清单

### D33. body_measurements 双创建端点：单 + /batch（2026/08/16）

- **决策**：两个端点都支持
  - `POST /body-measurements`：单条
  - `POST /body-measurements/batch`：批量，整体事务，max 50 条
- **理由**：
  - 实测一周早晚各一次 → 补录 7 个 POST 太啰嗦
  - schema 一次定义 `List[BodyMeasurementCreateItem]` 复用
  - 整体事务：任一失败整批回滚（避免脏数据）
- **替代**：
  - 单一端点 magic `isinstance` 检测（类型不清晰 + 边界复杂）
- **关联**：spec §3.1 + §3.2 + §4.1 BodyMeasurementBatchCreate（max_length=50）

### D34. measurements PATCH 仅允许 notes + recorded_at（2026/08/16）

- **决策**：`BodyMeasurementPatch` 只含 `notes` + `recorded_at` 两字段
- **理由**：
  - 体重/腰围/1RM 是客观测量值 → 事后改即造假，业务上禁止
  - 但"我 9 点测的，改 8 点半"或"补一句备注"是合理需求
- **Pydantic 强约束**：`model_config = ConfigDict(extra="forbid")`（W3）—— 前端误传 `weight=999` 时 422 拒绝
- **面试话术**：
  > "我用 `extra='forbid'` 而非默认 allow —— 前端误传 weight 时 422 拒绝，业务层不会悄悄覆盖真实测量数据。FitForge 是数据完整性平台，weight 是事实，不可改。"
- **关联**：spec §3.5 + §4.1 BodyMeasurementPatch

### D35. goals PATCH 允许全 5 字段（2026/08/16）

- **决策**：`UserGoalUpdate` 含 5 字段：`type` / `target_value` / `status` / `deadline` / `notes`
- **理由**：
  - `status` 必须能切（active → completed / abandoned）—— 不支持 update 等于列表功能废了
  - 用户可调 `target_value`（"减 70 改减 65"）
- **与 D34 不同语义**：goal 是"意图"，可改；measurement 是"事实"，不可改
- **不允许 PATCH**：`user_id` / `id` / `created_at` / `updated_at`
- **关联**：spec §3.10 + §4.2 UserGoalUpdate

### D36. measurements 硬删 + goals 不删（走 status 状态机）（2026/08/16）

- **决策**：
  - `DELETE /body-measurements/{id}`：硬删（D17 NOT DO 软删除）
  - ~~DELETE /user-goals/{id}~~：**不实现**，改走 `PATCH status="abandoned"`
- **理由**：
  - measurements 是"事实"，可重测 → 硬删合理
  - goal 是"成长轨迹"（"我曾想减到 75kg"），硬删会损失历史数据
  - 与 GitHub Issue "关掉"（不删）的设计哲学一致 —— 动作状态化
- **面试话术**：
  > "用户说 '删除一个目标' 其实很少见 —— 改走 PATCH status='abandoned' 不仅保留数据还能将来展示 '我放弃过哪些 / 为什么放弃'。YAGNI：MVP 不做 delete。"
- **关联**：spec §3.11（标注不实现）+ §5.2 不含 `delete_goal`

### D37. 列表查询参数：limit <= 100、offset >= 0、from/to（2026/08/16）

- **决策**：
  - `GET /body-measurements?from=&to=&limit=&offset=`（默认 20/0）
  - `GET /user-goals?status=&limit=&offset=`（默认 20/0）
- **理由**：
  - 不引第三方分页库（SQLAlchemy 原生 limit/offset）
  - limit 上限 100 是工程平衡（单请求防超时 + 内存压力）
- **filter 字段选择**：
  - measurements：`from` / `to` 是业务时间 `recorded_at`（D17-c 业务时间分离）
  - goals：`status` Literal 过滤
- **面试话术**：
  > "我不用 fastapi-pagination 之类的库 —— 单数据库 + 原生 SQLAlchemy limit/offset 足够。limit 上限 100 是后端保护，避免恶意请求拖死服务。"
- **关联**：spec §3.3 + §3.8

### D38. 跨用户访问返回 404（防 ID 枚举）（2026/08/16）

- **决策**：`service.get_measurement` / `service.get_goal` 检测到 `obj.user_id != current_user.id` 时统一抛 `MeasurementNotFoundError` / `GoalNotFoundError`（**不是** 403）
- **理由**：
  - 防止 ID 枚举攻击 —— 攻击者无法通过 403 vs 404 响应差异探测哪些 id 存在
  - 与 GitHub / Stack Overflow 等大厂设计一致
  - 业务语义一致：用户 A 看不到用户 B 的资源 = "找不到"
- **面试话术**：
  > "我返回 404 而非 403 —— 安全考虑。攻击者通过 403/404 差异能枚举出哪些 ID 存在。GitHub 也这么干。"
- **关联**：spec §5.1 get_measurement + §6.1 注释

### D39. get_current_user 抽到 core/security.py（2026/08/16）

- **决策**：把 `get_current_user` 从 `api/auth.py` 迁移到 `core/security.py`（位置迁移，函数体不变）
- **理由**：
  - 避免循环 import：`api/body.py` / `api/goal.py` 等多个路由需要 `Depends(get_current_user)`，如果它仍在 `api/auth.py` 就有循环风险
  - 依赖方向正确：业务（路由）依赖 core（基础设施），core 不应反向依赖路由
  - 未来 CLI / 脚本绕过 HTTP 直接调业务时也能复用鉴权
- **面试话术**：
  > "依赖方向应该指向 core —— core 是基础设施层。路由层只做 HTTP 适配。让 core 反向 import 路由会出现循环 import，业务可复用性也变差。"
- **关联**：spec §7.4 + plan Task 7

### D40. 测试数据库改用 SQLite in-memory + StaticPool（2026/08/16）

- **决策**：`tests/conftest.py` 顶部 `os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")`，engine 用 `StaticPool` 共享 connection schema
- **背景**：plan 原方案是 MySQL `fitforge_test` 单独 schema，但实施时遇到：
  1. 本地 Docker MySQL daemon down（3306/3307/3308 全 ConnectionRefused）
  2. 即使起来了，fitforge dev user **无 CREATE DATABASE 全局权限**（Access denied 1044）
- **理由**：
  - 测试金字塔核心是验证业务逻辑，DB 引擎选型对业务测试影响小
  - SQLite `:memory:` + `StaticPool` 提供**完美测试隔离**：每次测试 function 独立 session 共享 schema，teardown 清空
  - 最小权限原则：不为测试扩大 dev user 权限
- **配套**：
  - `tests/conftest.py` conftest 顶部固定 SQLite URL
  - `engine` fixture 用 `poolclass=StaticPool` 强制单 connection
  - `requirements.txt` **不改**（用户 M 标记文件），aiosqlite 作为测试专属依赖，仅本地 pip install
  - `clean_test_data` autouse fixture 每个测试前后清空所有测试数据
- **未来回归**：MySQL 全链路一致性可走 GitHub Actions CI + docker-compose 起专用 mysql-test 容器，**不污染**本地开发
- **面试话术**：
  > "测试金字塔是验证业务逻辑，不是验证 DB 引擎兼容性。SQLite `:memory:` + StaticPool 提供'每测试独立 schema'的完美隔离，而 MySQL 共享 schema 有 conftest 漏 fixture 污染全数据库的风险。**测试要的不是'与生产完全一样的环境'，而是'业务规则在每个边界 case 下表现一致'**。"
- **关联**：plan §W7 修订 + Phase 4 subagent 实施 + 子 agent 第一次 D41 幻觉（subagent 内部命名 D41 与正式 D40 不一致，已在 commit 后用 Edit + 后续 commit fix）
- **教训**：subagent 决策号**必须**对齐 spec §11 决策表，不允许子 agent 自创编号

---

## 面试话术积累区

> 随着开发推进，把每个技术决策的"为什么"沉淀在这里，面试前可直接复习。

### ⚠️ 本周暂存区（周日统一整理）

**1. SQLAlchemy 2.0 异步选型**（头脑风暴 §1）

> "FitForge 选用 SQLAlchemy 2.0 异步 + asyncmy，因为 FastAPI 异步生态天生契合，高并发场景下不会因为 ORM 阻塞事件循环。这是为未来水平扩展做准备——单服务阶段同步也够，但异步的代码风格是行业新趋势。"

**2. PyJWT vs python-jose 选型**（头脑风暴 §2）

> "我选用 PyJWT 而非教程常见的 python-jose，因为后者自 2022 年后维护停滞。选型不是看哪个'流行'，是看哪个'健康'。"

**3. argon2id vs bcrypt 选型**（头脑风暴 §3）

> "密码哈希选 Argon2id，是 OWASP 2023+ 推荐的 PHC 算法，相比 bcrypt 抗 GPU/ASIC 攻击更强——因为它是内存硬性（memory-hard）的，硬件加速成本高。"

**4. RS256 直接落地（跳过 HS256）**（头脑风暴 §4）

> "我第一周直接采用 RS256 而非更简单的 HS256，因为：① 我想从一开始就建立'签发私钥 / 验证公钥'的工程心智，避免后期重构；② 为未来拆 auth-service 微服务预留架构；③ 简历上'项目从 Day 1 就按工业级安全标准设计'是亮点。代码中通过 `kid` 头预留密钥版本，未来可以无痛升级到 JWKS endpoint。"

**5. 第一周 RSA 密钥管理动作清单**（头脑风暴 §4 续）

- `openssl genrsa -out keys/private.pem 2048` 生成私钥
- `openssl rsa -in keys/private.pem -pubout -out keys/public.pem` 导出公钥
- `keys/private.pem` 加入 `.gitignore`（.env 中只存路径）
- PyJWT：`jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "v1"})`

**6. Alembic 数据库 schema 版本化**（头脑风暴 §6）

> "数据库表结构也需要版本管理——这是我从 Git 推出来的类比。Alembic 让 schema 变更可追溯、生产部署可控、周五加表不会变成'我忘了在本地加那个字段'的事故。"

**7. uv 包管理器选型**（头脑风暴 §7）

> "我选用 uv 而非传统 pip，因为：① Rust 内核速度极快（pip install 30s vs uv 1s），CI 节省的时间累积可观；② 兼容现有 pip 生态，无需重写 requirements.txt；③ 这是 Python 包管理的未来趋势，写在简历上是亮点。"

**8. logging 标准库 vs loguru**（头脑风暴 §8）

> "日志我选 Python 标准库 logging 而非更便捷的 loguru，原因有三：① logging 是面试必问（'讲讲 logger/handler/formatter 的关系'），用标准库能展开 10 分钟；② 项目从 Day 1 就该建立'架构感'，而非追求配置行数最少；③ loguru 的能力未来需要时一行 import 即可切换，但 logging 的底层理解一旦建立终身受益。"

**9. SSH 密钥对机制**（周二实操）

> "SSH 登录用的是非对称加密——本地存私钥（永远不外传），服务器存公钥（可公开）。登录时本地用私钥签名，服务器用公钥验证。这比密码登录安全 100 倍：密码可能被暴力破解，私钥签名是数学难题（ed25519 是椭圆曲线离散对数）。"

**10. ed25519 vs RSA 选型**（周二实操）

> "我选 ed25519 而非 RSA-2048：① 256 位 vs 2048 位——密钥小 8 倍；② 签名验证快 10 倍——GitHub 大规模部署时 CPU 节省显著；③ NIST 2019 推荐 ed25519 替代 RSA；④ ed25519 标准化晚（2011），审计更新，潜在弱点更少。RSA 唯一优势是兼容性广——但我现在用的客户端（Git Bash）都支持 ed25519，没必要。"

**11. SSH config 别名管理**（周二实操）

> "我用 `~/.ssh/config` 别名管理多服务器：`ssh fitforge` 比 `ssh -i D:/ssh/id_ed25519 ubuntu@114.132.83.99 -p 22` 简洁 10 倍。配上 `IdentitiesOnly yes` 防止 SSH agent 自动选错私钥——这种'小配置大效率'的工程习惯，面试能展开 5 分钟。"

**12. 云服务器首次访问的特殊流程**（周二实操）

> "我处理过腾讯云 CVM 首次 SSH 失败的'经典坑'——服务器 Connection closed 不是密码错，而是**默认禁密码 + 公钥未上传**。解法在腾讯云控制台：重置密码 + 绑定密钥对 + 重启实例。这个流程 100% 网上教程不写，但每个用云服务器的人都会遇到。AWS / GCP / 阿里云 / 腾讯云各家流程不同，但'云厂商控制台绑定密钥对'是通用范式。"

---

## 🚨 2026/08/18 周一开工 - 事实澄清补记（事件驱动，立即落盘）

> **触发事件**：早上读 `project_progress.md` 时汇报"16 个 task 编码未开始"，用户质疑后实地 git 查证发现完全失实。

### 严重失实更正

1. **"16 个 task 未开始"是错的**——git log 显示从 `a2785d2`（plan 写完）到 `ec663f5`（test sync）之间有 **24 个业务 commit**，16 个 task 编码**全部完成**（含 D39 refactor + D40 测试 SQLite 决策 + 部署 checklist + 4 个 deploy issues error_log）。
2. **"32 个文件 commit"是指周日晚抢救性 sync**——`6572e7b` (6 files) + `d7c0fa9` (14 files) + `12b1d02` (7 files) + `ec663f5` (1 file) = 28 文件 + 散 commit 凑到 30+。
3. **工作树当前 `clean`**（`git status` 验证），main 分支最新 commit `12b1d02`。

### 服务器现状（用户自查）

- **服务器状态**：用户已自查，**实例存活、处于"已关机"状态**（非"实例过期/释放"）
- **SSH 连接**：**未连上**——早上 `ssh fitforge` 报 `Connection timed out`（端口 22 超时，与"关机"状态吻合）
- **之前"部署成功"字样存疑**：
  - `0460a14 feat(deploy): add server deploy script`（脚本本身 commit 了，不等于真部署）
  - `f4f64df docs(error-log): record 4 deploy issues`（4 个部署问题已记录，需重读详情）
  - `error_logs/2026-08-16-server-deploy-4-issues.md`（待详查）

### 教训（必填）

- **下次开工必须先 `git log --stat` 实地查证**，不能只读 `project_progress.md`——文档可能是过期/乐观版本
- **失实汇报**比"不知道"更危险——差点误导用户以为"还没开始"就跳进"开始"的指令
- 用户质疑**永远当回事**——"我好像都没连服务器就部署成功了？"这句是关键，文档里"成功"字样需逐一核验

### 下一步（待用户拍板，未开始）

- [x] 重读 `error_logs/2026-08-16-server-deploy-4-issues.md` 弄清之前 4 个部署问题
- [x] 服务器开机后测试 SSH 连接（`ssh fitforge`）→ 用户自查服务器存活
- [x] 核实之前"部署"实际状态 → 08-16 部署完整（smoke 13 步全过）
- [x] git push 到 GitHub（`lhr6666/FitForge`）→ **首次 push 完成**（commit `91bfeac`）
- [x] 第 1 周周报 + 复盘（见下方「第 1 周周报」section）

---

## 第 1 周周报（2026/06/30 - 2026/08/16 + 周一补记 2026/08/18）

> **写作原则**：汇编已有记录，不重写原文。精简版聚焦"指标 + 教训 + 规划"。
> **覆盖周期**：第 0 周（06/30）初始化 + 第 1 周（07/01 - 08/16）开发 + 周一（08/18）收尾
> **作者**：LHR6666 + Claude Code

### 1.1 关键指标


| 维度       | 数值                                    |
| -------- | ------------------------------------- |
| 总 commit | 60+（含今日 4 个 + 抢救性 sync 4 个）           |
| 重大决策     | D1-D40（40 项）                          |
| 文档沉淀     | 12 tech_notes + 7 error_logs（含今日 3 篇） |
| 业务端点     | 13（5 auth + 6 body + 4 goals - 2 删除）  |
| 测试覆盖     | pytest 39+ + smoke 13 步全过             |
| 服务器部署    | 08-16 完整部署（业务功能 100%）                 |
| 远程备份     | 08-18 首次 git push（commit `91bfeac`）   |


### 1.2 7 天节奏（按时间序）

- **周一**（07/01）：项目初始化 + Git（1 commit）
- **周二**（07/02）：Linux/SSH/腾讯云 CVM（2 commit）
- **周三**（07/06）：/auth/register 端到端（22 commit）
- **周四**（08/14）：/auth/login + JWT rotation（11 commit）
- **周五补**（08/16）：body CRUD 编码 + 服务器部署（24 commit）
- **周日补**（08/18）：PyJWT 修复 + 重复部署纠正 + 首次 push（4 commit）

### 1.3 6 大里程碑

1. **Git + 项目骨架**（周一）— Conventional Commits 规范落地
2. **SSH + 云服务器端到端**（周二）— ed25519 + 腾讯云首次访问踩坑
3. **/auth/register 端到端**（周三）— Argon2id + PyJWT RS256
4. **JWT 双 token + rotate**（周四）— 防重放 + DB 存 jti
5. **body CRUD + 完整部署**（周五补）— 4 失误修复 + smoke 全过
6. **远程备份建立**（周一补）— 首次 push 到 GitHub

### 1.4 5 大教训（写入简历）


| #   | 教训                        | 工程价值            | 来源                                                |
| --- | ------------------------- | --------------- | ------------------------------------------------- |
| 1   | 依赖脱漏是隐形技术债                | venv 残留掩盖 → 部署崩 | `error_logs/2026-08-18-pyjwt-requirements-fix.md` |
| 2   | alembic 必须 always upgrade | schema 是状态不是代码  | `error_logs/2026-08-16-server-deploy-4-issues.md` |
| 3   | 实地查证 > 文档脑补               | 2 次失实同源错误       | `error_logs/2026-08-18-redeploy-antipattern.md`   |
| 4   | 用户质疑永远当回事                 | 早期信号被忽略代价大      | 早上"16 task" + "重复部署"                              |
| 5   | exclude 列表必须显式备份          | .env 备份复制是部署必备  | 08-16 失误 1                                        |


### 1.5 服务器 + 远程现状

- **GitHub**：首次 push 完成（HEAD = `91bfeac`）
- **服务器**：腾讯云 CVM 114.132.83.99 处于**关机状态**（按量付费节省），代码 = 08-16 部署完整版
- **本地 vs 服务器**：本地 `91bfeac`（含 3 个 dev-side commit），服务器是 08-16 部署版本
- **结论**：服务器功能完整，**无需重新部署**（08-18 已澄清）

### 1.6 第 2 周规划（待 user 拍板）

- 用户 08-18 决策：**先把第 1 周收尾干净再谈第 2 周**
- 候选方向：
  - A. 继续核心功能（CRUD 后续 / 教练 / 食物）
  - B. 补技术债（rate limiting / logging / SQL 优化 / PyJWT grep 检查机制）
  - C. 调 brainstorming 重新定方向

### 1.7 技术债清单（code review 留项 + 本周发现）

- [ ] rate limiting（slowapi 库）— 安全风险
- [ ] logging（service + handler 层）— 运维友好
- [ ] 合并 username/email 查重为单次 SQL — 性能优化
- [ ] **PyJWT grep 检查机制**（建立本地+服务器 requirements.txt 完整性自动校验）

### 1.8 面试话术复习入口

详见「面试话术积累区」12 条 + 本周新增：

- 重复部署反模式教训（`error_logs/2026-08-18-redeploy-antipattern.md`）
- PyJWT 依赖脱漏教训（`error_logs/2026-08-18-pyjwt-requirements-fix.md`）
- 5 大教训汇总（见 1.4 节）

---

## ✅ 第 1 周收尾 checklist（已完成）

- [x] 业务代码 + 测试 + 部署 完整
- [x] 文档沉淀（12 tech_notes + 7 error_logs）
- [x] Git 远程备份（首次 push 到 `lhr6666/FitForge`）
- [x] PyJWT requirements.txt 修复（commit `1622384`）
- [x] 周报 + 复盘（本文档）