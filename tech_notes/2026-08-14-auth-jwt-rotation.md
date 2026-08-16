# /auth/login + refresh + logout 完整沉淀

> **日期**：2026-08-14（周四）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D5（PyJWT）、D7（RS256）、D28（双 token + rotate）、D29（DB 存 jti）、D30（revoke 字段）、D31（统一错误消息）
> **关联 spec/plan**：`docs/superpowers/specs/2026-08-14-auth-login-design.md` + `docs/superpowers/plans/2026-08-14-auth-login-plan.md`
> **关联 commit**：`da04aec` → `d11fbf4` → `bf57200` → `43515c7` → `6e17323` → `f97bb9b` → `46cc077` → `e23c120` → `79bccc2` → `1aa7c11`
> **目的**：面试前复习 + JWT 双 token 完整工程实践

---

## 1. 整体架构（4 端点 + 1 中间件 + 3 张表改动）

```
POST /auth/register   (Q1-Q6 已完成)         # 创建 user
        ↓
POST /auth/login      (新)                   # email+password → access+refresh
        ↓                                    # access 30min, refresh 14d
GET  /auth/me         (新)                   # Depends(get_current_user)
        ↓
POST /auth/refresh    (新)                   # rotate refresh（防重放）
        ↓
POST /auth/logout     (新)                   # revoke refresh (幂等)
        ↓
[业务路由]              (新)                   # Depends(get_current_user) 鉴权
```

**3 张表的改动**：

- `users`：加 `refresh_tokens` relationship
- `refresh_tokens`（新）：jti + expires_at + revoked + FK CASCADE
- `alembic_version`：2 个 revision（ec5983897455 → 8d6db464011d）

---

## 2. 4 个新增设计决策（D28-D31）

### D28：双 token + refresh rotate

**决策**：access 30 分钟 + refresh 14 天 + 每次 refresh rotate。

**为什么双 token**：

- access 短寿命 → 泄露风险低
- refresh 长寿命 → 用户体验好（不频繁登录）
- access 泄露 → 30 分钟窗口
- refresh 泄露 → 14 天窗口（**但 DB 验证 + rotate 兜底**）

刚开始登录会发送一个生成token有效30分钟和一个刷新token，也就是前端存有两个token，而刷新token是用来刷新掉旧的这两个token生成新的两个

**为什么 rotate**：

```
[登录成功]
   ↓
你手里: [Access A (30分)] + [Refresh R (14天)]
黑客手里: [Refresh R (14天)]  <-- 偷到了

   ↓ (过了30分钟，A 过期了)

[你发起刷新] -------------------------------------------------> [黑客发起刷新] (稍晚一点)
   ↓                                                              ↓
后端: 验证 R 通过 ✓                                          后端: 验证 R ...
后端: 把 R 标记为【已作废】❌                                 后端: 查数据库...
后端: 发给你 [Access A2] + [Refresh R2]                       后端: 发现 R 已经【作废】了❌
   ↓                                                              ↓
你更新: 扔掉 A,R，存好 A2,R2                                 后端: 报错 401！滚蛋！

若黑客先刷新：
你会被强制下线，然后重新登录，那会怎么样？

你输入正确的账号密码 → 后端验证通过。
后端强制撤销该用户的所有 Refresh Token（这是进阶安全策略，或者即使不撤销，也会签发全新的）。
后端给你发一对全新的票：Access(NEW) + Refresh(NEW)。
```

**rotate 防重放**——旧 refresh 立刻失效。

### D29：refresh token DB 存储 + jti

JWT 本身是“发出去就不管了”的（无状态）。但我们在业务中有个强需求：**我要能主动让 Token 失效**（比如用户点了“退出登录”，或者改了密码）。

**决策**：refresh token 写 DB（jti + expires_at + revoked）。

**为什么存 DB**：

- 可主动撤销（用户点 Logout，我们就在数据库里把这条记录标为“删除”或“作废”。下次黑客拿来用，一查数据库，发现已经没了，直接拒绝）
- 可 rotate（每次刷新时，把旧记录标为作废，插入一条新记录。这就实现了“旧 Token 立即失效”）
- 可审计（你可以查这个表，看到用户“上次登录是什么时候”、“用了几个设备”）

**jti 是什么**：

- JWT ID，UUID4 字符串
- 每个 refresh token 唯一
- 验证时，拿着 Token 里的 JTI 去数据库里**精确匹配**，找到唯一的那条记录。

**为什么不存 access token**：

- access 短寿命（30 分钟），过期自动失效
- 如果每次请求 API 都要查数据库验证 Access Token，那数据库压力太大了，速度也会变慢。

### D30：refresh token revoke 字段（不用 Redis 黑名单）

**决策**：在数据库表里加一个布尔类型字段 `revoked`（ true / false ） + 复合索引 `(user_id, revoked)`。

**vs Redis 黑名单**：

- ✅ 单字段查询快（`WHERE jti=? AND revoked=false`）
- ✅ 不引入新依赖
- ✅ MVP 够用
- ❌ 撤销延迟（access 30min 仍可用）—— 这是指 Access Token。因为 Access Token 不存库，所以即便你撤销了 Refresh Token，那个已经发出去的 Access Token 在 30 分钟内依然是有效的。这是 JWT 机制的通病，业界都接受这个 trade-off（折衷）。

**复合索引**（用于**查询某用户所有有效的 Token”**）：

- `idx_refresh_tokens_user_active (user_id, revoked)`：按 user_id 查 active token

eg：

你想实现一个功能：“**强制踢掉某用户的所有设备**”（也就是让他在所有手机上都下线）。  
你需要执行的 SQL 逻辑是：

SELECT * FROM refresh_tokens 

WHERE user_id = 1   -- 找这个用户

AND revoked = false; -- 找还没作废的

然后把这些记录的 `revoked` 都改成 `true`。

### D31：统一错误消息 "邮箱或密码错误"

**决策**：用户不存在 + 密码错 返回同一消息。

**为什么**：

- 防止枚举攻击（攻击者通过响应区分"用户不存在"和"密码错"）
- 业界标准（GitHub / Google 都是这样）
- `detail` 字段写"邮箱或密码错误"——**绝对不能**分别说"邮箱不存在"和"密码错误"

---

## 3. 7 个核心原理

### 3.1 JWT 结构 = 3 段 Base64 编码

```
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9  .  eyJzdWIiOiIxIiwiaWF0IjoxNzE0MDk5MDAwLCJleHAiOjE3MTQxMDk5MDAsInR5cGUiOiJhY2Nlc3MifQ  .  <signature>

↑ Header (alg=RS256, type=JWT)            ↑ Payload (claims)                                ↑ RSA 签名
```

**Payload 包含 4 个 claims**：

- `sub`：subject（用户 ID，str 类型）
- `iat`：issued at（签发时间）
- `exp`：expiration（过期时间）
- `type`：access 或 refresh（**区分 token 类型**）

### 3.2 RS256 vs HS256


| 维度    | HS256（对称）       | **RS256（非对称）**  |
| ----- | --------------- | --------------- |
| 算法    | HMAC + 共享密钥     | RSA + 公私钥       |
| 签发    | 用 secret        | 用**私钥**         |
| 验证    | 用**同一个** secret | 用**公钥**         |
| 性能    | 快               | 慢（非对称）          |
| 用途    | 单服务             | **微服务**（公钥可公开）  |
| 我们的选择 | ❌               | ✅ D7 决策（第一周直接上） |


**为什么用 RS256**：

- 第一周就建立"私钥签发 + 公钥验证"工程心智
- 未来拆 auth-service 微服务时，**公钥发给其他服务**（私钥只留 auth-service）

### 3.3 get_current_user 中间件

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidTokenError("缺少 Bearer token")
    token = credentials.credentials
    payload = decode_access_token(token)  # 失败抛 InvalidTokenError
    user = await db.get(User, int(payload["sub"]))
    if not user:
        raise InvalidTokenError("user not found")
    return user
```

**4 步**：

1. HTTPBearer 提取 `Authorization: Bearer xxx`
2. decode_access_token 验签 + 验证过期 + 验证 type
3. DB 查 user（拿最新数据）
4. 返回 user 对象（**不是** user_id——业务层拿完整 user）

### 3.4 401 vs 422 vs 409 状态码


| 状态码     | 含义        | 触发                                                 |
| ------- | --------- | -------------------------------------------------- |
| 200     | 成功        | login/refresh 业务成功                                 |
| 204     | 成功无 body  | logout（无返回内容）                                      |
| **401** | **未授权**   | **InvalidCredentials（密码错）/ InvalidToken（token 错）** |
| **409** | **数据冲突**  | register 时 username/email 重复                       |
| **422** | **请求格式错** | Pydantic 校验失败（缺 email / 弱密码）                       |


**关键**：401 必须带 `WWW-Authenticate: Bearer` 头（OAuth 2.0 标准）。

---

## 4. 完整数据流

### 4.1 POST /auth/login

```
客户端              FastAPI                  service                      DB
  │                    │                       │                          │
  ├─ HTTP POST ────►   │                       │                          │
  │  {email,password}   │                       │                          │
  │                    ├─ Pydantic 校验 ────►   │                          │
  │                    │  （422 if fail）        │                          │
  │                    │                       │                          │
  │                    ├─ auth_service.login()► │                          │
  │                    │                       ├─ SELECT user WHERE email=?│
  │                    │                       │                          ├─► [DB]
  │                    │                       │  返回 user                 │
  │                    │                       │                          │
  │                    │                       ├─ verify_password(...)    │
  │                    │                       │  → 错则 InvalidCredentials│
  │                    │                       │                          │
  │                    │                       ├─ create_access_token(id) │
  │                    │                       ├─ create_refresh_token(id)│
  │                    │                       │  → (token, jti)           │
  │                    │                       │                          │
  │                    │                       ├─ INSERT refresh_tokens    │
  │                    │                       │                          ├─► [DB]
  │                    │                       │                          │
  │                    │                       └─ return (access, refresh)│
  │                    │                                            │
  │                    ├─ TokenResponse(...)                              │
  │ ◄── HTTP 200 ────  │                                            │
  │     {access, refresh, type=bearer, exp=1800}                       │
```

### 4.2 POST /auth/refresh（rotate）

```
client → POST /auth/refresh {refresh_token}
       ↓
service.refresh_token:
  1. decode_refresh_token(token)  # 验签 + 验证 type=refresh
  2. SELECT refresh_tokens WHERE jti=?  → 查 DB
  3. 验证: not None AND revoked=False AND expires_at > now
  4. UPDATE refresh_tokens SET revoked=True WHERE jti=?
  5. INSERT refresh_tokens (new jti)
  6. create_access_token(user_id) + create_refresh_token(user_id)
  7. return (new_access, new_refresh)
```

**4 步关键**：

- 验签 ✓
- 查 DB 验证 ✓
- **作废旧 refresh**（防重放）✓
- 签发新 refresh（新 jti）✓

### 4.3 POST /auth/logout

```
client → POST /auth/logout {refresh_token}
       ↓
service.logout:
  1. try decode_refresh_token(token)
  2. If InvalidTokenError: return (幂等)
  3. UPDATE refresh_tokens SET revoked=True WHERE jti=?
  4. return None (204)
```

**幂等**：无效 token 视作已登出（不报错）。

### 4.4 GET /auth/me

```
client → GET /auth/me + Authorization: Bearer xxx
       ↓
FastAPI:
  1. HTTPBearer 提取 token
  2. get_current_user(token, db):
     - 验证 token 签名 + 过期
     - DB.get(User, int(sub)) → user 对象
  3. UserRead.model_validate(user) → ORM → DTO（无 password_hash）
  4. return UserRead(id, username, nickname)
```

---

## 5. 7 题面试 Q&A

### Q1：为什么用 JWT 而不是 session？

> "JWT 是无状态的——服务器不存 session，只验签。**好处**：水平扩展容易（多实例不用共享 session）；**代价**：撤销困难（access 30 分钟内仍可用）。我们用双 token + DB 存 jti 折中：access 30 分钟（短 → 泄露风险低），refresh 14 天（DB 可主动撤销 + rotate 防重放）。"

### Q2：RS256 vs HS256 怎么选？

> "HS256 对称（一个 secret），RS256 非对称（私钥签发 + 公钥验证）。**单服务**用 HS256 简单，**微服务**用 RS256（公钥可公开给其他服务）。FitForge 第一周就上 RS256——D7 决策——为未来拆 auth-service 微服务铺路。"

### Q3：access token 泄露怎么办？

> "泄露后最多 30 分钟窗口（access 寿命）——这是 trade-off。**生产缓解**：① HTTPS 加密传输；② token 短寿命；③ 客户端存内存（不存 localStorage）避免 XSS 窃取；④ refresh token 验证 + rotate 兜底。撤销延迟 30 分钟是 JWT 业界标准 trade-off。"

### Q4：refresh token 怎么防重放？

> "**rotate 机制**——每次 refresh 作废旧 refresh + 签发新 refresh。攻击者即使截获旧 refresh，等他拿来用时 server 查 DB 发现已 revoked → 拒绝 401。这是 D28 设计的核心——'旧 refresh 一旦 rotate 就废'。"

### Q5：为什么 refresh token 要存 DB？session 不行吗？

> "session 存在 server 内存或 Redis——但**微服务架构**多实例共享 session 麻烦（需要 sticky session 或共享 Redis）。**DB 存 jti** 是无状态的——任何实例都能查 + 撤销 + rotate。代价是每次 refresh 多 1 次 DB 查询（~1ms），换架构灵活性。"

### Q6：密码错统一消息"邮箱或密码错误"为什么重要？

> "防**枚举攻击**——攻击者通过响应差异能探测出'哪些 email 已注册'。**统一消息**让攻击者无法区分'用户不存在'和'密码错'。GitHub / Google / 各大厂都是这个做法——安全最佳实践。代价是真实用户报错时少一些上下文（但可以靠'忘记密码'功能找回）。"

### Q7：401 状态码必须带 WWW-Authenticate 头吗？

> "**是**——OAuth 2.0 RFC 7235 标准。`WWW-Authenticate: Bearer` 让客户端知道怎么重新认证（带 Bearer token）。没这个头时，客户端只知道 401 但不知道怎么重试。这是工程上的'协议合规'，对 SDK 兼容性重要。"

---

## 6. 5 个真实踩坑 + 修法

### 踩坑 1：MySQL fitforge 用户密码不一致（D27 疏漏）

**现象**：D27 决策把服务器密码改成 `lhr076200`，但**本地 Docker MySQL** 的 fitforge 用户密码还是 D26 默认的 `fitforge_dev_password_2026`。alembic autogenerate 报 `Access denied for user 'fitforge'@'172.17.0.1'`。

**修法**：`docker exec fitforge-mysql mysql -uroot -p...` 改本地密码为 `lhr076200`。3 处全一致。

**教训**：决策变更要全链路同步，**不只改一处**。

### 踩坑 2：datetime naive vs aware 报错

**现象**：`TypeError: can't compare offset-naive and offset-aware datetimes`。

**根因**：

- `db_token.expires_at` 来自 MySQL `DateTime` → Python 读出来是 **naive**（无 tzinfo）
- `datetime.now(timezone.utc)` 是 **aware**（带 tzinfo）
- 两者不能直接比较！

**修法**：统一用 `datetime.utcnow()`（naive）跟 model 的 `default=datetime.utcnow` 一致。

**教训**：MySQL `DateTime` 不存时区——**要 naive 一致**；PostgreSQL `TIMESTAMPTZ` 存时区——可以 aware。

### 踩坑 3：refresh 测试的 access 断言错误

**现象**：`AssertionError: new_access != access` —— rotate 后 access token 内容相同。

**根因**：access token payload 是 `{sub, iat, exp, type}`，同一 user_id 1 秒内签发 → payload 完全相同 → 字符串相同。

**修法**：测试只断言 `new_refresh != refresh`（D28 关键行为），不要求 `new_access != access`。

**教训**：access 内容可以相同（用户不在意），关键是 **refresh token 的 jti 唯一**（每次 rotate 新 jti）。

### 踩坑 4：Edit 找不到字符串（linter 加中文注释）

**现象**：`Edit old_string not found in file`。

**根因**：linter 自动加中文注释（如 `# 关系字段：定义了两个一对多关系...`），改变了文件内容。

**修法**：`cat` 文件看实际内容，用 linter 改后的字符串作为 old_string。

**教训**：频繁 Read 文件，别凭记忆 Edit。

### 踩坑 5：LoginRequest 弱密码被接受（业务认知错误）

**现象**：测试 `LoginRequest(password='12345678')` 不报 422。

**根因**：LoginRequest **不应该**校验密码强度——密码已在注册时检查，登录用现有密码。弱密码登录会因为 verify_password 失败返回 401（service 层处理）。

**修法**：测试断言改成 401 而不是 422（business correct）。

**教训**：注册 + 登录密码语义不同——注册是"创建密码"（必须强），登录是"验证密码"（已存在）。

---

## 7. 5 个关键 commit 模式


| Commit    | 模式                   | 关键                              |
| --------- | -------------------- | ------------------------------- |
| `da04aec` | 核心模块加函数              | security.py 加 JWT 函数 + key 启动加载 |
| `d11fbf4` | 异常体系扩展               | 业务异常继承 FitForgeException 基类     |
| `bf57200` | ORM 模型加表             | User 加关系 + RefreshToken 新模型     |
| `43515c7` | alembic autogenerate | 人工 review 生成的 migration         |
| `f97bb9b` | 业务层加流程               | service 3 函数含完整数据流              |
| `46cc077` | 异常 → HTTP 映射         | 401 + WWW-Authenticate: Bearer  |
| `e23c120` | 路由层 + 中间件            | Depends(get_current_user) 设计    |
| `79bccc2` | pytest e2e           | 9/9 全过（4 旧 + 5 新）               |
| `1aa7c11` | smoke 7 新场景          | 14/14 全过                        |


---

## 8. 部署清单（生产环境）

```bash
# 1. 生成 RSA 密钥对
cd /path/to/project
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem

# 2. 设置私钥权限（Linux）
chmod 600 keys/private.pem
chmod 644 keys/public.pem

# 3. .env 加 RSA 路径
cat >> .env << EOF
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ALGORITHM=RS256
JWT_EXPIRE_MINUTES=1440
EOF

# 4. alembic upgrade（创建 refresh_tokens 表）
alembic upgrade head

# 5. 启动 uvicorn
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# 6. 验证
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Password123"}'
# 预期：200 + access_token + refresh_token
```

---

## 9. 关联文档

- 关联 spec：`docs/superpowers/specs/2026-08-14-auth-login-design.md`
- 关联 plan：`docs/superpowers/plans/2026-08-14-auth-login-plan.md`
- 关联 `/auth/register` spec：`docs/superpowers/specs/2026-07-06-auth-register-design.md`
- 部署文档：`docs/deploy-to-server.md`
- 异常体系沉淀：`tech_notes/2026-07-06-business-exceptions.md`
- 路由层沉淀：`tech_notes/2026-07-06-fastapi-route-layer.md`
- Alembic 沉淀：`tech_notes/2026-07-06-alembic-migration-workflow.md`

---

## 10. 11 个 pytest + 14 个 smoke = 完整测试覆盖

**pytest（tests/test_auth.py）**：

```
✓ test_register_success               ← 旧
✓ test_register_duplicate_username    ← 旧
✓ test_register_weak_password         ← 旧
✓ test_register_missing_email         ← 旧
✓ test_login_success                  ← 新
✓ test_login_wrong_password          ← 新
✓ test_refresh_rotate_and_revoke     ← 新
✓ test_me_with_valid_token            ← 新
✓ test_me_without_token               ← 新
= 9/9 全过
```

**smoke（tests/smoke.sh）**：

```
✓ Test 1-7: register 7 个场景          ← 旧
✓ Test 8-14: login/refresh/logout/me    ← 新
= 14/14 全过
```

---

**沉淀状态**：✅ 用户于 2026-08-14 批准落盘