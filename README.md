# FitForge

> 一个给健身爱好者用的训练管理工具。

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-WIP-yellow)]()

## 产品定位

FitForge 是一个给健身爱好者用的训练管理工具。核心思路是按周期化训练的原理给每个人生成训练计划，再结合 AI 教练的能力，持续追踪身体数据，让计划能跟着人的状态走。

## 几个做了的事情

### 1. 周期化训练计划自动生成

读入用户的 body_measurements 和 user_goals，套用周期化训练原理（线性 / 波动 / 块状三种周期）生成阶段性的训练计划。目标是不靠"凭感觉练"。

### 2. 每次训练后动态调整

训练完录入体重、围度、最大力量这些身体数据。系统按数据的变化趋势调整后面的训练强度和动作选择。计划不是定死的，会跟着人变。

### 3. 目标和反馈串成闭环

把 user_goals、周期化算法生成的计划、body_measurements 反馈这三件事连起来，用户能直接看到自己离目标还有多远、差在哪儿。

## 技术栈

| 层 | 选型 | 备注 |
|----|------|------|
| Web 框架 | FastAPI 0.115 | 异步生态、原生 OpenAPI |
| ORM | SQLAlchemy 2.0 异步 | asyncmy 驱动 |
| 数据库 | MySQL 8.0 | 服务器本地装 |
| 迁移 | Alembic | schema 版本化 |
| 校验 | Pydantic v2 + pydantic-settings | 请求/响应体 + 配置加载 |
| 认证 | PyJWT + Argon2id | RS256 非对称签名 |
| 依赖管理 | uv | Rust 内核，速度快 |
| 日志 | logging 标准库 | dictConfig |
| 部署 | Uvicorn + Nginx（待定） | 周六上线 |

## 项目结构

```
FitForge/
├── api/              # FastAPI 路由层
├── core/             # 配置、数据库、安全、日志
├── models/           # SQLAlchemy ORM
├── schemas/          # Pydantic 请求/响应体
├── services/         # 业务逻辑（核心算法）
├── alembic/          # 数据库迁移
├── tests/            # 测试
├── keys/             # RSA 私钥/公钥（不入 Git）
├── main.py           # FastAPI 入口
├── .env.example      # 配置模板
└── requirements.txt
```

## Quick Start

### 本地开发

```bash
# 1. 克隆仓库
git clone https://github.com/lhr6666/FitForge.git
cd FitForge

# 2. 安装依赖（推荐用 uv）
pip install uv
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# 3. 复制配置并填入真实值
cp .env.example .env
# 编辑 .env，至少配置 DATABASE_URL

# 4. 启动服务
uvicorn main:app --reload

# 5. 访问 API 文档
# http://localhost:8000/docs
```

### 部署（周六补全）

```bash
# 服务器环境
apt install python3.10 mysql-server
# ... 详见 deploy.md
```

## Roadmap

24 周开发计划，当前进度见 [project_progress.md](project_progress.md)。

| 周 | 主题 | 状态 |
|----|------|------|
| 0 | 项目初始化 | ✅ |
| 1 | Git / FastAPI / JWT / MySQL 骨架 | 🚧 进行中 |
| 2-4 | Python OOP 与核心算法 | ⏳ |
| 5-8 | 周期化训练计划生成 | ⏳ |
| 9-12 | AI 教练集成 | ⏳ |
| 13-16 | 用户体系完善 | ⏳ |
| 17-20 | 性能优化与监控 | ⏳ |
| 21-24 | 上线与迭代 | ⏳ |

## 贡献

本项目由 [LHR6666](https://github.com/lhr6666) 作为求职作品开发，欢迎 Star 和 Fork。

## 许可证

MIT
