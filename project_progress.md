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
- [ ] 实施 6 大块（按 plan T1-T22）

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

---

## 待办 / 技术债务

- [x] ~~补充 README.md~~（周一已完成）
- [x] ~~添加 .gitignore~~（周一已完成）
- [x] ~~初始化 Git 仓库~~（周一已完成，本地 commit 1232c38，未推送）
- [x] ~~第 1 周技术选型确认~~（见下方「重大决策记录」D1-D16）
- [ ] 推送首次 commit 到 GitHub（用户决定延后到周六部署前）
- [x] ~~周二：本地跑通 FastAPI /docs~~
- [x] ~~周二：确认云服务器（用户已有腾讯云 CVM）~~
- [x] ~~周二：SSH 密钥对生成 + 成功登录服务器~~
- [x] 周二晚：服务器装 Python 3.10 + MySQL 8.0
- [ ] 周二晚或周三：与 Claude 一起设计 MVP 蓝图（users / body_measurements / user_goals 三表）

---

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

