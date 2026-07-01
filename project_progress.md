# 智能训练管理平台 - 项目进度跟踪

> 本文件由 Claude Code 协助维护，记录每周开发进度、技术债务与里程碑。
> 更新原则：每周结束前必须更新一次；重大变更（架构调整、技术选型）即时追加。

---

## 项目基本信息

- **项目名称**：智能训练管理平台
- **开发周期**：24 周
- **开发模式**：结对开发（用户主导决策，Claude Code 协助落盘与解释）
- **目标环境**：Python 3.10+，本地开发 → Ubuntu 22.04 云服务器部署
- **启动日期**：2026/06/30
- **当前阶段**：第 0 周 - 项目初始化

---

## 项目目录结构（约定）

```
Intelligent_training_management_platform/
├── CLAUDE.md                 # 协作规则（最高优先级）
├── README.md                 # 项目说明（待补）
├── requirements.txt          # 依赖清单
├── project_progress.md       # 本文件：进度跟踪
├── tech_notes/               # 核心技术、原理、面试话术沉淀
├── error_logs/               # 报错与解决方案记录
├── api/                      # 路由层（待建）
├── services/                 # 业务逻辑层（待建）
├── models/                   # 数据模型层（待建）
├── core/                     # 配置、依赖注入、基础设施（待建）
└── tests/                    # 单元测试与集成测试（待建）
```

> 备注：遵循 CLAUDE.md 中"严格分层架构"红线，业务逻辑必须写在 services/，绝不混入 api/ 路由中。

---

## 技术栈规划（待逐周确认）

| 周次 | 主题 | 关键技术 | 状态 |
|------|------|----------|------|
| 0 | 项目初始化 | - | ✅ 已完成 |
| 1 | 待定 | 待定 | ⏳ 等待指令 |

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

## 待办 / 技术债务

- [ ] 补充 README.md（周一任务）
- [ ] 添加 .gitignore（Python + FastAPI + IDE，周一任务）
- [ ] 初始化 Git 仓库（周一任务）
- [x] ~~第 1 周技术选型确认~~（见下方「重大决策记录」）

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

### 待决项
（无，本周 12 项技术选型全部完成）

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