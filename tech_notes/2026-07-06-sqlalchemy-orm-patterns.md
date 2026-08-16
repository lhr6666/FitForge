# SQLAlchemy 2.0 ORM 模式沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D4（SQLAlchemy 2.0 异步 + asyncmy）、D17（3 张表 schema）
> **关联 commit**：`bbeb0a2`（plan Task 6-9 + models/**init**.py 引入 3 model）
> **目的**：面试前复习 + ORM 设计原则

---

## 1. DeclarativeBase vs 旧版 declarative_base()

```python
# ❌ SQLAlchemy 1.4 旧版：函数调用
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()  # 全局函数

# ✅ SQLAlchemy 2.0 新版：类继承
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass  # 用户定义的类，PEP 8 风格
class User(Base):#用继承类的话IDE 知道 Base 是个类，能给你类型提示，你写 User. IDE 会弹出属性列表
......
```

**为什么 2.0 改类继承**：

- 类继承支持 IDE 类型补全，
- 类继承支持 mixin（Mixin 就是**"贴纸"**，一段经常被使用的代码，可以贴到任何类上，不用每个类重复写，给它加点功能。）
- 类继承是 Pythonic 风格
- 类型注解（`Mapped[int]`、`mapped_column()`）只在 2.0 类继承下支持


| 维度       | 1.4 旧版 | 2.0 新版           |
| -------- | ------ | ---------------- |
| 风格       | 函数调用   | 类继承              |
| IDE 跳转   | 弱      | 强                |
| 类型注解     | 无      | `Mapped[int]` 风格 |
| mixin 复用 | 难      | 容易               |
| Pythonic | ⚠️     | ✅                |


> **面试话术**：「我用 SQLAlchemy 2.0 DeclarativeBase 而非 1.4 的 declarative_base()——因为 2.0 是类继承、支持类型注解、IDE 友好；1.4 的函数调用风格已经被弃用。2.0 还有新的 `Mapped[int]` 风格（type-safe），但我项目里用传统 Column() 是为了降低学习成本，spec §4.2 已经有完整伪代码。」

---

## 2. relationship 字符串引用 vs 类引用

```python
# ✅ 字符串引用（约定俗成）
class User(Base):
    goals = relationship("UserGoal", back_populates="user", cascade="all, delete-orphan")
#User 说：“我的 goals 在那边”，back_populates 就是告诉对方：“你拽这头，我拽那头”

class UserGoal(Base):
    user = relationship("User", back_populates="goals")

# ❌ 类引用（会循环 import）
from models.user import User  # 需要 User 已定义
from models.user_goal import UserGoal
class User(Base):
    goals = relationship(UserGoal, ...)  # 直接引用
```

**为什么用字符串引用**：

- 避免循环 import（A 引 B，B 引 A → ImportError）程序就会崩
- 不强制顺序：利用relationship加个引号变成字符串 `"UserGoal"`。Python 启动时不立马去找这个类，等所有文件都加载完了，再回过头来找。这叫**延迟加载**。
- 代价：失去 IDE 跳转**（**你按住 Ctrl 点它，光标不会**跳到**定义 `class UserGoal` 的地方，你不能看到它的代码）

**SQLAlchemy 内部机制**：字符串引用通过 `clsregistry` 全局 registry 解析类名，运行时查找。

> **面试话术**：「我用字符串 'UserGoal' 而非直接引用类——因为如果两个 model 文件互相 import（User 引 UserGoal，UserGoal 反引 User），直接引用会触发循环 import。字符串引用让 SQLAlchemy 运行时通过 registry 查找类，避开这个问题。代价是 IDE 跳转失效，但 IDE 配合 type stub 可以弥补。」

---

## 3. cascade="all, delete-orphan" + ON DELETE CASCADE 双层防御（D17-e）

```python
# DB 层（FK 约束）
#user_id 这个字段，必须引用 users 表的 id 字段。而且我立了个规矩：如果 users 表里的某条记录被删了，这条记录必须跟着一起删！”

#ForeignKey("users.id")：告诉数据库，这是个外键，连着 users 表的 id。

#ondelete="CASCADE"：这是数据库层面的强制规则。只要 User 没了，Goal 自动消失。
user_id = Column(
    Integer,
    ForeignKey("users.id", ondelete="CASCADE"),  # DB 层 CASCADE
    nullable=False,
)

# ORM 层（relationship）
#"UserGoal"：连着 UserGoal 这个类。
#back_populates="user"：告诉对方，“你也用 user 这个属性来找我”。
#cascade="all, delete-orphan"：
#all：所有操作都传下去（保存、删除都传）。
#delete-orphan：关键点。如果某个 Goal 失去了它的 User（成了孤儿），就把它删掉。
goals = relationship(
    "UserGoal",
    back_populates="user",
    cascade="all, delete-orphan",  # ORM 层 CASCADE
)
```


| 触发场景                                  | DB 层 CASCADE                | ORM 层 cascade               |
| ------------------------------------- | --------------------------- | --------------------------- |
| `db.session.delete(user)` + commit    | ⚠️ 不触发（ORM 操作不走 DB CASCADE） | ✅ ORM 检测到 user 删除，自动删 goals |
| 直接 SQL `DELETE FROM users WHERE id=1` | ✅ DB 自动删 goals              | ❌ ORM 层管不到                  |
| `user.goals.clear() + commit`         | ⚠️ 不触发                      | ✅ ORM 自动删 orphan goals      |


数据层工作流程：

Step 1: 数据库解析 SQL

```
    "哦，你要删 [users.id](http://users.id) = 1"
```

Step 2: 数据库检查约束

```
    "等等，user_goals 表有个 FK 指向 [users.id](http://users.id)"

    "而且 ondelete=CASCADE"
```

Step 3: 数据库查找关联数据

```
    SELECT * FROM user_goals WHERE user_id = 1;

    -- 找到了 Goal #1 和 Goal #2
```

Step 4: 数据库执行级联删除

```
    DELETE FROM user_goals WHERE user_id = 1;

    -- Goal #1 和 Goal #2 被删
```

Step 5: 数据库完成原删除

```
    DELETE FROM users WHERE id = 1;

    -- 张三被删
```

ORM层：

```
1. 检查 User 类的定义

user_class = User

2. 找到所有 relationship

relationships = user_class.mapper.relationships

找到：goals 和 measurements

for rel in relationships:
if "delete" in rel.cascade:

    # 找到了！goals 有 delete cascade

    

    # 4. 定位关联数据

    related_objects = getattr(zhang_san, rel.key)

    # 这会触发 SQL: SELECT * FROM user_goals WHERE user_id = 1

    

    # 5. 逐个删除

    for obj in related_objects:

        session.delete(obj)
```

**双保险的意义**：

- 应用代码 `db.session.delete(user)` → ORM 层 cascade 先删 goals → 触发 commit
- 直接 SQL `DELETE FROM users WHERE id=1` → DB 层 CASCADE 删 goals
- **任一层失效，另一层兜底**——纵深防御

> **面试话术**：「我用 SQLAlchemy 的 `cascade='all, delete-orphan'` + DB 层 `ON DELETE CASCADE` 双保险——业务代码 `db.session.delete(user)` ORM 层自动删 goals；即使 ORM 层被绕过（直接 SQL），DB 层 CASCADE 也会删。这是'纵深防御'：单层防御总有可能失效，叠加后失败概率指数级降低。」

---

## 4. 复合索引 (user_id, status) 的最左前缀原则（D17-b）

把两个字段合在一起做目录。

```python
__table_args__ = (
    Index("idx_user_goals_user_status", "user_id", "status"),
)
```


| 查询                                       | 命中索引？               |
| ---------------------------------------- | ------------------- |
| `WHERE user_id = ?`                      | ✅ 命中（最左前缀）          |
| `WHERE user_id = ? AND status = ?`       | ✅ 命中（完整）            |
| `WHERE status = ?`                       | ❌ 不命中（缺最左字段）        |
| `WHERE user_id = ? AND notes LIKE '%?%'` | ⚠️ 部分命中（user_id 部分） |


**为什么 90% 查询都是 (user_id, status)**：

- "查我所有 active 目标"：`WHERE user_id=? AND status='active'`
- "查我所有目标"：`WHERE user_id=?`
- 几乎不会有"查所有 active 用户的 active 目标"——这种查询频率极低

**索引决策流程**：

1. 看 SQL：`SELECT * FROM user_goals WHERE user_id=? AND status=?`
2. 提 WHERE 子句：`user_id=` + `status=`
3. 复合索引按高频字段放前面 → `(user_id, status)`

> **面试话术**：「我建复合索引 `(user_id, status)` 是基于'最左前缀原则'——因为 90% 查询是'某用户某状态'。如果只查 status 不带 user_id，这个索引帮不上（这是 B-Tree 索引的物理限制）。复合索引的列顺序遵循最左前缀——把高频过滤字段放前面。D17 蓝图里所有 N 表都建了 (外键, 业务字段) 复合索引，是同一原则的应用。」

---

## 5. ENUM（枚举） 在 DB 层 vs Python 校验（双层防御）

```python
# Python 端（Pydantic，spec §4.2 schemas/user.py）
class UserGoalCreate(BaseModel):
    type: Literal["cut", "bulk", "maintain", "strength"]

# DB 端（MySQL ENUM）
type = Column(Enum("cut", "bulk", "maintain", "strength", name="goal_type"), nullable=False)
```


| 层级                   | 校验机制             | 错误信息                               |
| -------------------- | ---------------- | ---------------------------------- |
| **Python**（Pydantic） | `Literal` 字段自动校验 | "type must be one of..."           |
| **DB**（MySQL ENUM）   | 存储层拒绝非法值         | "Data truncated for column 'type'" |


**为什么双层**：

- 应用层 Pydantic 校验：给清晰错误信息（"type 必须是 cut/bulk/maintain/strength 之一"）
- DB 层 ENUM 拒绝：应用层被绕过时（直接 SQL）兜底
- 攻击场景：黑客绕过 API 直接 INSERT → DB ENUM 拒绝

> **面试话术**：「我用 Python Literal + DB ENUM 双层校验——应用层给清晰错误（'type 必须是 cut/bulk/...'），DB 层 ENUM 兜底（应用层被绕过时拒绝）。MySQL ENUM 底层存整数序号省空间，但加新值要 ALTER TABLE——这就是为什么我引入 Alembic：schema 变更需要版本管理。」

---

## 6. 业务时间 vs 系统时间分离（D17-c）

```python
# body_measurements 表
recorded_at = Column(DateTime, nullable=False, index=True)  # 业务时间（用户测量时间）
created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 系统时间
updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```


| 字段              | 来源          | 可修改            | 用途             |
| --------------- | ----------- | -------------- | -------------- |
| **recorded_at** | 用户传入（业务视角）  | ✅ 用户可改（如补录）    | 查"我某天测的体重"     |
| **created_at**  | DB 自动（系统视角） | ❌ 永不变          | 查"系统里数据什么时候加的" |
| **updated_at**  | DB 自动（系统视角） | DB 自动 onupdate | 排查"数据什么时候改的"   |


**场景示例**：

- 用户 7/15 09:30 测量 → 7/16 12:00 才录入系统
- `recorded_at = 2026-07-15 09:30:00`（业务时间）
- `created_at = 2026-07-16 12:00:00`（系统时间）
- 查询"我 7/15 测的体重"用 `WHERE recorded_at BETWEEN '2026-07-15 00:00' AND '2026-07-15 23:59'`
- 查询"这条数据什么时候加的"用 `created_at`

> **面试话术**：「BodyMeasurement 用 `recorded_at`（业务时间）+ `created_at`（系统时间）两个字段——业务时间可补录历史，系统时间不可改。两个时间分离处理'补录 7 天前的测量'这种场景。算用户减肥曲线时，用 `recorded_at`，不然曲线会错乱。我从来不用单一时间字段——上线后排查 bug 时经常需要'用户视角的时间'和'系统视角的时间'分开查。」

---

## 7. 面试 Q&A（6 题预演）

### Q1：SQLAlchemy 1.4 vs 2.0 区别？

> "1.4 是函数式 declarative_base()、2.0 是类继承 DeclarativeBase。2.0 支持 IDE 类型补全、mixin 复用、PEP 8 风格、新的 `Mapped[int]` 类型注解。1.4 已弃用，新项目我一律用 2.0。"

### Q2：relationship 字符串引用 vs 类引用的取舍？

> "字符串引用避免循环 import、降低 import 顺序约束，代价是 IDE 跳转失效。类引用更安全（IDE 跳转 + 类型检查），但要小心循环 import。我项目里用字符串引用——因为 3 个 model 互相关联，循环 import 风险高。"

### Q3：cascade='all, delete-orphan' 和 DB CASCADE 是什么关系？

> "双层防御。ORM 层 cascade 处理 Python 代码 `db.session.delete(user)`，DB 层 CASCADE 处理直接 SQL。任一层失效另一层兜底。生产环境两者都开，绝不只开一层。"

### Q4：复合索引最左前缀原则怎么用？

> "复合索引 (a, b) 命中 `WHERE a=?` 和 `WHERE a=? AND b=?`，但不命中 `WHERE b=?`。设计复合索引时把高频过滤字段放前面——我是按'90% 查询的 WHERE 子句'来定列顺序。D17 蓝图里所有 N 表都建了 (外键, 业务字段) 复合索引。"

### Q5：MySQL ENUM 的局限性？怎么加新值？

> "ENUM 底层存整数序号，省空间但加新值要 ALTER TABLE——这是 ENUM 的代价。我用 Alembic 做 schema 版本管理，加 ENUM 值要走 migration。如果未来 ENUM 值频繁变化，应该改用 VARCHAR + CHECK 约束或独立 lookup 表。"

### Q6：为什么 recorded_at 和 created_at 分开？

> "业务时间（用户测量时间）可补录历史；系统时间（DB 插入时间）不可改。两者分离处理'补录 7 天前的测量'这种场景——recorded_at 可以写 7/15，created_at 自动是 7/16。我从来不用单一时间字段——上线排查 bug 时'用户视角时间'和'系统视角时间'要分开查。"

---

## 8. 踩坑清单


| 坑                                  | 现象                       | 解法                                                |
| ---------------------------------- | ------------------------ | ------------------------------------------------- |
| 1.4 旧 `declarative_base()` 用在新项目   | DeprecationWarning       | 升级到 2.0 的 `DeclarativeBase`                       |
| 字符串引用拼错                            | `KeyError: 'UserGaol'`   | unit test 覆盖 model import                         |
| 循环 import                          | ImportError on startup   | 用字符串引用 + 把所有 model 在 models/**init**.py 集中 import |
| `cascade="all"` 但没 `delete-orphan` | `goals.clear()` 不删数据库    | 加 `delete-orphan` 显式声明                            |
| ENUM 改值没走 migration                | 生产环境 `Data truncated` 报错 | 加 ENUM 值要走 Alembic 手动 SQL                         |
| 复合索引列顺序错                           | `WHERE status=?` 不命中索引   | 把高频过滤字段放最左                                        |
| recorded_at 设为 UTC 但应用传本地时间        | 时区错乱                     | 数据库统一存 UTC，渲染层转本地                                 |


---

## 9. 参考资源

- [SQLAlchemy 2.0 ORM 文档](https://docs.sqlalchemy.org/en/20/orm/)
- [SQLAlchemy 2.0 迁移指南](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html)
- [MySQL 8.0 ENUM 类型](https://dev.mysql.com/doc/refman/8.0/en/enum.html)
- [使用索引 (Use The Index, Luke!)](https://use-the-index-luke.com/)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘