# FitForge MVP 数据库 Schema 设计

> **日期**：2026-07-02（周二）
> **作者**：LHR6666（与 Claude Code 头脑风暴产出）
> **目的**：为周三 SQLAlchemy ORM 编写提供 schema 蓝图
> **关联决策**：D1（先共建 MVP 版蓝图）、D17（见末尾）

---

## 1. 概述

### 1.1 设计目标

MVP 阶段为 FitForge 设计 3 张核心表，覆盖：
- **用户体系**：账号、认证
- **目标管理**：用户训练目标的历史记录与状态管理
- **身体数据**：测量记录，支撑"周期化算法"读取

### 1.2 设计原则（YAGNI）

- ❌ 不做软删除（MVP 硬删除，未来需要再加 `deleted_at`）
- ❌ 不做 UUID 主键（MVP 用 INT 自增）
- ❌ 不做审计日志（MVP 阶段不需要，第 10 周以后）
- ❌ 不做 Trigger / 存储过程（DB 只存数据）
- ❌ 不做分区表（MVP 1 万条数据不需要）

### 1.3 范围说明

**MVP 支持**：
- 用户注册 / 登录（username + 密码）
- 用户目标增删改（一次可以有多个，状态管理）
- 身体数据录入 / 查询（一次录入多条）
- 一对多关系（一个用户对多个目标/测量）

**MVP 不支持**：
- 关注 / 好友关系
- 训练计划表（用户说"计划是周期化算法实时算出来的，不存表"）
- 图片上传
- 第三方认证（OAuth）

---

## 2. ER 关系图

```
┌─────────────────────┐
│       users         │
│  id (PK)            │
│  username (UQ)      │
│  email (UQ)         │
│  password_hash      │
│  nickname           │
│  created_at         │
│  updated_at         │
└──────────┬──────────┘
           │
           │ 1:N（ON DELETE CASCADE）
           │
    ┌──────┴─────────────────────────┐
    │                                │
    ▼                                ▼
┌───────────────────────┐  ┌────────────────────────┐
│    user_goals         │  │   body_measurements    │
│  id (PK)              │  │  id (PK)               │
│  user_id (FK, IDX)    │  │  user_id (FK, IDX)     │
│  type (ENUM)          │  │  weight (NOT NULL)     │
│  target_value (NULL)  │  │  body_fat (NULL)       │
│  status (IDX)         │  │  chest/waist/hip ...   │
│  deadline (NULL)      │  │  bicep/thigh/calf ...  │
│  notes (NULL)         │  │  squat_1rm ...         │
│  created_at, updated  │  │  recorded_at (IDX)     │
│                       │  │  notes (NULL)          │
│  IDX: (user_id,       │  │  created_at, updated   │
│       status)         │  │  IDX: (user_id,        │
│                       │  │       recorded_at)     │
└───────────────────────┘  └────────────────────────┘
```

---

## 3. 三张表完整字段定义

### 3.1 `users` 表

| 字段 | 类型 | 约束 | 索引 | 说明 |
|------|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | ✅ PK | 主键 |
| `username` | VARCHAR(50) | UNIQUE, NOT NULL | ✅ UQ | 登录标识 |
| `email` | VARCHAR(255) | UNIQUE, NULL | ✅ UQ | 找回密码用 |
| `password_hash` | VARCHAR(255) | NOT NULL | - | Argon2id 哈希 |
| `nickname` | VARCHAR(50) | NULL | - | 显示名（可与 username 不同） |
| `created_at` | DATETIME | NOT NULL | - | UTC |
| `updated_at` | DATETIME | NOT NULL | - | UTC, on update |

**SQLAlchemy ORM 伪代码**：
```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow,
        onupdate=datetime.utcnow, nullable=False
    )

    # 关系
    goals = relationship(
        "UserGoal", back_populates="user",
        cascade="all, delete-orphan"
    )
    measurements = relationship(
        "BodyMeasurement", back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.username}>"
```

---

### 3.2 `user_goals` 表

| 字段 | 类型 | 约束 | 索引 | 说明 |
|------|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | ✅ PK | 主键 |
| `user_id` | INT | FK→users.id, NOT NULL, ON DELETE CASCADE | ✅ IDX | 外键 |
| `type` | ENUM('cut','bulk','maintain','strength') | NOT NULL | - | 目标类型 |
| `target_value` | FLOAT | NULL | - | 如 75.0（kg） |
| `status` | ENUM('active','completed','abandoned') | default='active', NOT NULL | ✅ IDX | 状态 |
| `deadline` | DATE | NULL | - | 预留字段 |
| `notes` | TEXT | NULL | - | 预留字段 |
| `created_at` | DATETIME | NOT NULL | - | UTC |
| `updated_at` | DATETIME | NOT NULL | - | UTC, on update |

**复合索引**：`(user_id, status)` — 查"当前 active 目标"用

**SQLAlchemy ORM 伪代码**：
```python
class UserGoal(Base):
    __tablename__ = "user_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    type = Column(
        Enum("cut", "bulk", "maintain", "strength", name="goal_type"),
        nullable=False
    )
    target_value = Column(Float, nullable=True)
    status = Column(
        Enum("active", "completed", "abandoned", name="goal_status"),
        default="active", nullable=False, index=True
    )

    # 预留字段
    deadline = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow,
        onupdate=datetime.utcnow, nullable=False
    )

    # 关系
    user = relationship("User", back_populates="goals")

    __table_args__ = (
        Index("idx_user_goals_user_status", "user_id", "status"),
    )

    def __repr__(self):
        return f"<UserGoal {self.id} {self.type} {self.status}>"
```

---

### 3.3 `body_measurements` 表

| 字段 | 类型 | 约束 | 索引 | 说明 |
|------|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | ✅ PK | 主键 |
| `user_id` | INT | FK→users.id, NOT NULL, ON DELETE CASCADE | ✅ IDX | 外键 |
| `weight` | FLOAT | NOT NULL | - | kg, 必填 |
| `body_fat` | FLOAT | NULL | - | 体脂率 % |
| `chest` | FLOAT | NULL | - | 胸围 cm |
| `waist` | FLOAT | NULL | - | 腰围 cm |
| `hip` | FLOAT | NULL | - | 臀围 cm |
| `bicep` | FLOAT | NULL | - | 上臂围 cm |
| `thigh` | FLOAT | NULL | - | 大腿围 cm |
| `calf` | FLOAT | NULL | - | 小腿围 cm |
| `squat_1rm` | FLOAT | NULL | - | 深蹲 1RM kg |
| `bench_1rm` | FLOAT | NULL | - | 卧推 1RM kg |
| `deadlift_1rm` | FLOAT | NULL | - | 硬拉 1RM kg |
| `recorded_at` | DATETIME | NOT NULL | ✅ IDX | 用户测量时间 |
| `notes` | TEXT | NULL | - | 预留字段 |
| `created_at` | DATETIME | NOT NULL | - | 系统插入时间 |
| `updated_at` | DATETIME | NOT NULL | - | UTC, on update |

**复合索引**：`(user_id, recorded_at)` — 查"最近测量"用

**重要**：允许同一用户同一天录入多条测量记录（一天可测多次）

**SQLAlchemy ORM 伪代码**：
```python
class BodyMeasurement(Base):
    __tablename__ = "body_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # 必填字段
    weight = Column(Float, nullable=False)

    # 可选身体数据（11 字段除 weight + body_fat + 6 围度 + 3 力量 = 10 + 1 = 11）
    body_fat = Column(Float, nullable=True)

    # 围度（6 个）
    chest = Column(Float, nullable=True)
    waist = Column(Float, nullable=True)
    hip = Column(Float, nullable=True)
    bicep = Column(Float, nullable=True)
    thigh = Column(Float, nullable=True)
    calf = Column(Float, nullable=True)

    # 力量 1RM（3 个）
    squat_1rm = Column(Float, nullable=True)
    bench_1rm = Column(Float, nullable=True)
    deadlift_1rm = Column(Float, nullable=True)

    # 业务时间 vs 系统时间分离
    recorded_at = Column(DateTime, nullable=False, index=True)

    # 预留字段
    notes = Column(Text, nullable=True)

    # 系统时间
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow,
        onupdate=datetime.utcnow, nullable=False
    )

    # 关系
    user = relationship("User", back_populates="measurements")

    __table_args__ = (
        Index("idx_user_measurements_user_recorded", "user_id", "recorded_at"),
    )

    def __repr__(self):
        return f"<BodyMeasurement user={self.user_id} weight={self.weight}>"
```

---

## 4. 关键设计决策（D17）

### D17-a：ON DELETE CASCADE

- **决策**：删 user 时自动删 goals / measurements
- **理由**：DB 层保证一致性，避免孤儿数据
- **面试话术**：
  > "我用 CASCADE 而非手动删——数据库保证一致性比应用层可靠。手动删可能因为代码 bug 留下孤儿，但 CASCADE 是 DB 原生约束，绕过不了。"

### D17-b：复合索引（user_id, status / recorded_at）

- **决策**：每对 N 表建复合索引
- **理由**：90% 查询是"某用户的列表"
- **面试话术**：
  > "索引设计跟着 WHERE 子句走——这是 SQL 调优的核心。我为每对一对多关系建 `(外键, 时间字段)` 复合索引，命中效率最高。"

### D17-c：业务时间 vs 系统时间分离

- **决策**：`recorded_at`（用户测量时间）+ `created_at`（系统插入时间）
- **理由**：用户可补录历史测量
- **面试话术**：
  > "我从来不用单一时间字段——`recorded_at` 是用户视角的业务时间，`created_at` 是系统视角的存储时间。两个分离能处理'补录 7 天前的测量'这种场景。"

### D17-d：ENUM 约束在 DB 层

- **决策**：`goal_type` / `goal_status` 用 MySQL ENUM，不只是 VARCHAR
- **理由**：DB 层拒绝非法值（即使应用层校验被绕过）
- **面试话术**：
  > "我用 ENUM 而非 VARCHAR——应用层校验可以被绕过（直接 SQL INSERT），DB 层 ENUM 是最后一道防线。'纵深防御'思想在 schema 设计中的应用。"

### D17-e：SQLAlchemy delete-orphan + CASCADE

- **决策**：Python ORM 层 `cascade="all, delete-orphan"`
- **理由**：业务代码少一层删除循环
- **面试话术**：
  > "SQLAlchemy 的 `delete-orphan` + DB 层 CASCADE 是双保险——我从 `db.session.delete(user)` 一次，goals/measurements 自动消失。即使 DB 层 CASCADE 被禁用，ORM 层也兜底。"

### D17-f：一律 UTC 时间戳

- **决策**：`created_at` / `updated_at` / `recorded_at` 全用 UTC
- **理由**：跨时区训练数据；用户从任何国家访问都对
- **面试话术**：
  > "时间戳一律 UTC，渲染时再转本地——避免时区错乱。最经典的 bug 是 '用户说记录在 7 月 1 日，但 DB 里是 6 月 30 日'——UTC + 渲染转换才能稳定。"

### D17-g：created_at/updated_at 全表统一

- **决策**：每张表都有这 2 个字段
- **理由**：上线后排查问题必备（出 bug 看哪一条数据什么时候改的）
- **面试话术**：
  > "我从表设计就加 created_at/updated_at——上线后排查'什么时候变成这样的'问题必备，没它们就只能看 binlog。"

---

## 5. 索引策略汇总

| 表 | 索引名 | 字段 | 用途 |
|----|--------|------|------|
| `users` | PRIMARY | id | 主键 |
| `users` | uq_users_username | username | 登录查询 |
| `users` | uq_users_email | email | 找回密码 |
| `user_goals` | PRIMARY | id | 主键 |
| `user_goals` | idx_user_goals_user_id | user_id | 用户过滤 |
| `user_goals` | idx_user_goals_status | status | 状态过滤 |
| `user_goals` | idx_user_goals_user_status | (user_id, status) | 查当前目标 |
| `body_measurements` | PRIMARY | id | 主键 |
| `body_measurements` | idx_body_measurements_user_id | user_id | 用户过滤 |
| `body_measurements` | idx_body_measurements_recorded_at | recorded_at | 时间排序 |
| `body_measurements` | idx_body_measurements_user_recorded | (user_id, recorded_at) | 查最近测量 |

**查询性能预期**：
- "查用户最近 5 次测量" → 命中 `idx_body_measurements_user_recorded`，O(log n)
- "查用户当前目标" → 命中 `idx_user_goals_user_status`，O(log n)
- "登录查询" → 命中 `uq_users_username`，O(1) hash 查找

---

## 6. 外键与级联策略

| 外键关系 | ON DELETE | 理由 |
|----------|-----------|------|
| `user_goals.user_id` → `users.id` | CASCADE | 删用户自动删目标 |
| `body_measurements.user_id` → `users.id` | CASCADE | 删用户自动删测量 |

**为什么不用 SET NULL**：
- 业务上"用户的目标"和"用户的测量数据"应该随用户消失
- SET NULL 会留孤儿，违反"用户控制全部数据"原则

**为什么不用 RESTRICT**：
- RESTRICT 拒绝删除用户，但 MVP 没有"账号注销"需求
- 未来需要"账号注销"再改策略

---

## 7. 时间戳策略（业务时间 vs 系统时间）

| 表 | 业务时间字段 | 系统时间字段 | 用法 |
|----|-------------|--------------|------|
| `users` | - | created_at, updated_at | 用户无业务时间（注册瞬间即创建） |
| `user_goals` | created_at（用户设定目标的时间） | updated_at | 单一时间字段 |
| `body_measurements` | **recorded_at**（用户测量时间，可补录） | created_at（系统插入时间）, updated_at | 两者分离 |

**场景示例**：
- 用户 2026-07-15 测量一次，写入 `recorded_at='2026-07-15 09:30'`
- 但他 2026-07-16 才录入系统 → `created_at='2026-07-16 12:00'`
- 后续修改 → `updated_at='...'`

**好处**：查询"2026-07-15 我测的体重"用 `recorded_at`；查询"系统里这条数据什么时候加的"用 `created_at`。

---

## 8. 测试策略（MVP 阶段）

### 8.1 测试层次

| 层 | 工具 | 覆盖 |
|----|------|------|
| 模型定义 | 启动 / alembic upgrade 跑通 | schema 正确生成 |
| 模型层 | pytest + sqlalchemy | 表能增删改查 |
| 关系测试 | 同上 | 删 user 自动删 goals/measurements |
| 约束测试 | 同上 | username 唯一、NOT NULL 生效 |
| 索引测试 | EXPLAIN 看 | 慢查询在索引范围 |

### 8.2 测试用例清单（MVP）

```python
# test_models.py

def test_create_user(session):
    user = User(username="alice", email="alice@example.com", password_hash="...")
    session.add(user)
    session.commit()
    assert user.id is not None

def test_username_unique(session):
    User(username="alice", ...)
    session.commit()
    with pytest.raises(IntegrityError):
        User(username="alice", ...)  # 重名应失败
        session.commit()

def test_cascade_delete_user(session):
    user = User(username="alice", ...)
    session.add(user)
    session.flush()
    goal = UserGoal(user_id=user.id, type="cut")
    session.add(goal)
    session.commit()

    session.delete(user)
    session.commit()
    # 自动删了 goal
    assert session.query(UserGoal).count() == 0

def test_body_measurement_indexed(session):
    # EXPLAIN 验证 (user_id, recorded_at) 索引被使用
    # ... 详见具体测试
```

---

## 9. Alembic 迁移计划

### 9.1 alembic 初始化（周三上午）

```bash
alembic init alembic
# 修改 alembic/env.py 配置 DATABASE_URL
```

### 9.2 第一次迁移（创建 users 表）

```bash
alembic revision --autogenerate -m "create users table"
# review 生成的 revision 文件，确认 SQL 正确
alembic upgrade head
```

### 9.3 第二次迁移（创建 user_goals 表）

```bash
alembic revision --autogenerate -m "create user_goals table"
alembic upgrade head
```

### 9.4 第三次迁移（创建 body_measurements 表）

```bash
alembic revision --autogenerate -m "create body_measurements table"
alembic upgrade head
```

### 9.5 必须做的 review 动作

- 每次 `autogenerate` 后**人工 review**生成的 SQL
- 特别检查：外键 CASCADE、复合索引、ENUM 约束
- autogenerate 不能识别所有变更（如 ENUM 值变更）— 手动补充

---

## 10. 下一步（D18 决策建议）

| # | 下一步 | 期望时间 |
|---|--------|---------|
| 1 | 周三上午：`pip install alembic asyncmy` | 10 分钟 |
| 2 | alembic init + 配置 DATABASE_URL | 30 分钟 |
| 3 | `core/db.py` 写 SQLAlchemy 异步 engine | 30 分钟 |
| 4 | 3 张 model 文件从占位改正式 | 1 小时 |
| 5 | alembic 3 次 autogenerate | 1 小时 |
| 6 | 写 `tests/test_models.py` 跑通 | 1 小时 |

---

## 11. 面试话术（汇总）

### Q1：MVP 数据库怎么设计？

> "我的 FitForge MVP 设计 3 张表：users、user_goals、body_measurements。设计原则是 **YAGNI + 双层防御**——应用层校验 + DB 层约束（ENUM、CASCADE）。3 个亮点：① 业务时间 vs 系统时间分离，处理补录；② 复合索引跟随 WHERE 子句设计；③ 一律 UTC 时间戳，渲染层再转本地。MVP 阶段用 INT 自增主键，但保留迁移到 UUID 的扩展性。"

### Q2：为什么不立刻用 UUID？

> "UUID 在分布式系统有价值，但 MVP 阶段单库单服务，INT 自增性能更好（InnoDB 聚簇索引顺序写）。等真要拆微服务或做数据迁移时再换 UUID——这是 **演进式架构** 的思维。"

### Q3：怎么处理"用户注销"？

> "MVP 没有账号注销——CASCADE 保证用户主动删账号时数据不残留。未来加账号注销功能时，把 CASCADE 改成 SOFT DELETE：所有表加 `deleted_at`，删除用户时标记，CASCADE 改成软传播。这是 schema 设计的'未来钩子'。"

### Q4：复合索引为什么这么设计？

> "90% 查询是'某用户的时间序列'——按 (user_id, status) 或 (user_id, recorded_at) 建复合索引能让查询走索引扫描，避免回表。如果只有外键单列索引，会回表 N 次才能拿到状态/时间。**复合索引的列顺序遵循最左前缀**——我把高频过滤字段放前面。"

### Q5：ENUM 的局限性？

> "MySQL 8.0 的 ENUM 是字符串枚举，底层存的是整数序号（省空间），但加新值要 `ALTER TABLE`。这是我用 ENUM 的风险——MVP 4 个 goal_type 够用，未来加需要 schema migration。这正是为什么我引入 Alembic——schema 变更需要版本管理。"

---

## 12. 附录：枚举值定义

```sql
-- goal_type
'cut'         -- 减脂
'bulk'        -- 增肌
'maintain'    -- 保持
'strength'    -- 提升力量

-- goal_status
'active'      -- 当前进行中（周期化算法读这个）
'completed'   -- 已完成（用户达成目标）
'abandoned'   -- 已放弃（用户主动放弃）
```

---

## 📚 参考资源

- [SQLAlchemy 2.0 异步文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic 教程](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [MySQL 8.0 ENUM 类型](https://dev.mysql.com/doc/refman/8.0/en/enum.html)
- [数据库索引设计原则](https://use-the-index-luke.com/)

---

**审批状态**：✅ 用户于 2026-07-02 头脑风暴中通过整体设计（4 个澄清问题 + 4 个细节全部拍板）
