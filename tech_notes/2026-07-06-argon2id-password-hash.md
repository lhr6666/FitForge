# Argon2id 密码哈希沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D6（Argon2id，passlib + argon2-cffi）
> **关联 commit**：`434f6a9`（plan Task 4）
> **目的**：面试前复习 + 密码学安全原则

---

## 1. Argon2id 的"hybrid"本质（OWASP 为什么推荐它）

Argon2id 不是独立算法，而是 **Argon2i + Argon2d 的组合**：

```
Argon2id 工作流程：
┌─────────────────────────────────────────────┐
│ Pass 1（前 1/2）：Argon2i（data-independent）│  ← 抗侧信道攻击
├─────────────────────────────────────────────┤
│ Pass 2（后 1/2）：Argon2d（data-dependent）   │  ← 抗时空权衡攻击
└─────────────────────────────────────────────┘
抗侧信道攻击:时序攻击：发现“以 s 开头”的请求耗时明显更长一点点；再试“se…”、“sec…”、“secr…”…通过时间差异，一位一位把密码猜出来。
Argon2id 的“内存硬”特性：就是专门克制 GPU 的：它要求一次哈希必须占满 64MB 内存。GPU 虽然核心多，但总显存有限（比如 24GB）。如果每个哈希都要占 64MB，那 24GB 只能同时算几百个，而不是几万个
```


| 算法           | 抗什么攻击               | 不抗什么攻击 |
| ------------ | ------------------- | ------ |
| **Argon2i**  | 侧信道攻击（cache timing） | 时空权衡攻击 |
| **Argon2d**  | 时空权衡攻击              | 侧信道攻击  |
| **Argon2id** | ✅ 两种都抗              | —      |


> **面试话术**：「Argon2id 是 Argon2i 和 Argon2d 的 hybrid——i 抗侧信道、d 抗时空权衡，id 同时抗两种。这是 OWASP 2023+ 推荐它而非 Argon2i 或 Argon2d 的核心理由：'选一个算法继承两种保护'。」

---

## 2. memory-hard vs time-hard（**核心区分**）


| 算法           | 类型                 | GPU 攻击难度             |
| ------------ | ------------------ | -------------------- |
| **bcrypt**   | time-hard（迭代）      | ⚠️ 易受攻击——每 GPU 核独立算  |
| **Argon2id** | memory-hard（64MB+） | ✅ 极难攻击——单次 hash 占满显存 |


黑客攻击：“算密码”就是：  
**用同一个哈希算法，对“候选密码”算出哈希，再和数据库里存的哈希比对。**

流程大概是这样：

1. 黑客拿到你数据库里的一串哈希：  
`$argon2id$v=19$m=65536,t=3,p=4$...`
2. 他知道这是 Argon2id，参数也都在字符串里写着。
3. 他准备一个密码字典：  
`123456`, `password`, `qwerty`, `admin123`, …
4. 对每个候选密码，用同样的算法、同样的盐、同样的参数，算一遍哈希。
5. 如果算出来的哈希和你数据库里那串完全一样，就说明：  
**这个候选密码 = 真实密码。**

**GPU 的作用**：  
几千个核心同时做第 4 步——同时试几千个密码。

**为什么 memory-hard 抗 GPU**：


| 维度           | bcrypt                  | Argon2id               |
| ------------ | ----------------------- | ---------------------- |
| **单次成本**     | CPU 计算（少）               | 内存 64MB（多）             |
| **GPU 显存**   | 每核 1MB（并行 24000 个 hash） | 每核 64MB（并行 384 个 hash） |
| **攻击 1 亿字典** | RTX 4090 ~5 天           | RTX 4090 ~4 个月         |


> **面试话术**：「Argon2id 是 memory-hard（内存硬性），bcrypt 是 time-hard（时间硬性）。区别在于：bcrypt 只需 CPU 算力，GPU 可并行加速；Argon2id 需要大内存，GPU 显存有限——同样的 1 亿次字典攻击，Argon2id 比 bcrypt 慢 100 倍。这是抗 GPU/ASIC 攻击的'内存墙'防御。」

---

## 3. 默认 cost 参数解读

```python
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
# 实际生成的 hash 字符串：
# $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>
#              └──┘ └──────┘ └─┘
#              version 内存    time
#              19     64MB    3次
```


| 参数          | 值      | 含义                                  | 调参方向                  |
| ----------- | ------ | ----------------------------------- | --------------------- |
| **m=65536** | 64MB   | 单次 hash 占 64MB 内存                   | 越大越抗 GPU（生产可调 131072） |
| **t=3**     | 3 次    | 3 次迭代                               | 越大越慢（生产可调 4-6）        |
| **p=4**     | 4 线程   | CPU 4 核并行（让你在多核机器上，用户体验不变差，同时仍然安全。） | 与 CPU 核数匹配            |
| **总成本**     | ~250ms | 单次 hash 耗时（4 核 CPU）                 | 目标 250-500ms          |


**生产调参指南**：

- 8 核 32GB 内存：m=131072（128MB）、t=4
- 4 核 8GB 内存：m=65536（默认）、t=3
- 2 核 2GB 内存：m=32768（32MB）、t=2

> **面试话术**：「Argon2id 默认参数 m=64MB、t=3 是 OWASP 平衡用户体验和安全性的推荐值——单次 hash 约 250ms。生产环境可以根据硬件调高：服务器 8 核 32GB 内存可以 m=128MB、t=4；用户体验优先的应用可以保持默认。调参原则：单次 hash 耗时 250-500ms 是甜蜜点。」

---

## 4. 自动 salt + 相同密码不同 hash

```python
h1 = hash_password('Password123')
# $argon2id$v=19$m=65536,t=3,p=4$RmiNEaKUEgJgjNGas/beuw$DoevFb...

h2 = hash_password('Password123')
# $argon2id$v=19$m=65536,t=3,p=4$xRjjvBcipDQGQAjBOEeIUQ$t+vgoi...

h1 != h2  # ✅ True（salt 自动随机）
```

**为什么需要 salt**：

- 没有 salt：100 万用户都用 `password123` → DB 里 100 万条相同 hash → 攻击者一次破解全中
- 有 salt：100 万用户 → 100 万条不同 hash → 攻击者每个都要单独破解
  - 用户 A：`123456` + 随机盐 `X` → `XYZ`。
  - 用户 B：`123456` + 随机盐 `Y` → `OPQ`。
  - 即使密码相同，结果也完全不同。黑客只能一个一个破解。

**salt 存在哪里**：

- passlib 把 salt 编码进 hash 字符串：`$argon2id$v=19$m=...,t=...,p=...$<salt_b64>$<hash_b64>`
- 16 字节 salt → base64 编码 22 字符
- verify 时自动从 hash 字符串解析 salt

**PHC（Password Hashing Competition）字符串格式**：

```
$argon2id$  ← 算法
v=19$       ← 算法版本
m=65536,t=3,p=4$  ← cost 参数（内存、时间、并行度）
<22 chars>$  ← salt（base64 编码 16 字节盐）
<43 chars>   ← 最终 hash（base64 编码 32 字节）
```

> **面试话术**：「salt 自动生成是 passlib 的内置行为——每次 hash 用 16 字节随机盐，相同密码产生不同 hash 字符串。这样即使两个用户都用 'password123'，DB 里两条 hash 也不同，攻击者无法用预计算的彩虹表批量破解。salt 存在 hash 字符串里（base64 编码），verify 时自动解析——无需额外存储。PHC 字符串格式是行业标准——'self-contained'格式让 DB 只需存一列。」

---

## 5. timing-safe 比较（防侧信道攻击）

```python
# ❌ 普通 == 比较：短路求值，第一个字符不等立即返回
def bad_verify(plain, hashed):
    return plain == hashed  # 攻击者可测响应时间推断前缀

# ✅ passlib 内部：恒定时间比较
def good_verify(plain, hashed):
    return pwd_context.verify(plain, hashed)  # 内部用 hmac.compare_digest
```

**timing attack 原理**：

```
攻击者请求 verify("a...", "$argon2id$...") → 1ms 返回
攻击者请求 verify("b...", "$argon2id$...") → 1ms 返回
攻击者请求 verify("A...", "$argon2id$...") → 1.001ms 返回（多比较 1 字节）
...
通过时间差异推断每个字符 → 1 字符 1ms → 8 字符密码 8ms 就能破解
```

**passlib 怎么防**：

```python
# passlib 内部用了类似 hmac.compare_digest 的恒定时间算法
# 不管密码匹配还是错误，验证耗时都一样（固定 N 字节比较）
# 这消除了"通过响应时间推断信息"的可能性
```

> **面试话术**：「passlib 内部用 hmac.compare_digest 实现恒定时间比较——不管密码匹配还是错误，验证耗时都一样。普通 `==` 短路求值会被 timing attack 利用：攻击者通过响应时间差异逐字符推断密码。这是密码学里经典的'侧信道攻击'防御。我把'防 timing attack'作为面试标准答案——因为 90% 候选人不会主动提这个。」

---

## 6. 与 bcrypt 的对比（面试常考）


| 维度           | bcrypt         | Argon2id            |
| ------------ | -------------- | ------------------- |
| **算法年代**     | 1999           | 2015 PHC 冠军         |
| **类型**       | time-hard      | memory-hard         |
| **抗 GPU**    | ⚠️ 弱           | ✅ 强                 |
| **抗侧信道**     | ⚠️ 弱（依赖实现）     | ✅ Argon2i 设计        |
| **OWASP 推荐** | 历史选择（2023 前）   | **当前推荐**（2023+）     |
| **标准**       | OpenBSD bcrypt | PHC 标准              |
| **库支持**      | passlib/bcrypt | passlib/argon2-cffi |


**什么时候还用 bcrypt**：

- 老项目代码兼容（迁移成本高）
- 嵌入式设备内存小（Argon2id 64MB 跑不起来）

**什么时候必须 Argon2id**：

- 新项目
- 涉及用户密码
- 对标 OWASP 2023+

> **面试话术**：「bcrypt 1999 年发布时是好的（password hashing 第一次工业级方案），Argon2id 2015 年 PHC 竞赛冠军是更好的——抗 GPU/ASIC 攻击更强。新项目我一定用 Argon2id，老项目迁移成本高可保留 bcrypt 但加 cost 因子。」

---

## 7. 面试 Q&A（5 题预演）

### Q1：Argon2id 为什么比 bcrypt 安全？

> "memory-hard vs time-hard。Argon2id 单次 hash 占 64MB 显存，bcrypt 只占少量 CPU。一张 RTX 4090 24GB 显存跑 bcrypt 可并行 24 万个 hash，跑 Argon2id 只能 384 个——同样 1 亿字典攻击，Argon2id 比 bcrypt 慢 100 倍。这是抗 GPU/ASIC 的'内存墙'防御。"

### Q2：什么是 hybrid 模式？为什么不直接用 Argon2d？

> "Argon2id = Argon2i（前 1/2）+ Argon2d（后 1/2）。Argon2i 抗侧信道、Argon2d 抗时空权衡，hybrid 同时抗两种。直接用 Argon2d 会被侧信道攻击（cache timing），直接用 Argon2i 又被时空权衡攻击。hybrid 是'两边都不得罪'的折中。"

### Q3：memory_cost=65536 是怎么选的？

> "OWASP 标准推荐——平衡用户体验和安全性。单次 hash 250ms 是甜蜜点（用户能接受 + 攻击者难破解）。生产可以根据硬件调高：服务器 8 核 32GB 可以 m=128MB、t=4。原则就是'单次 hash 250-500ms 内'。"

### Q4：salt 自动生成 vs 手动管理？

> "自动生成是 passlib 默认——每次 hash 用 16 字节随机盐，相同密码产生不同 hash。手动管理有两个问题：① 业务方要额外存 salt 列，DB schema 复杂；② 程序员忘加 salt 是常见 bug。passlib 的自动 salt 编码进 hash 字符串（base64 22 字符），verify 时自动解析——'self-contained'格式让 DB 只需存一列。"

### Q5：timing attack 是什么？怎么防？

> "攻击者通过响应时间差异推断密码前缀——普通 `==` 短路求值，第一个字符不等立即返回。passlib 用 hmac.compare_digest 实现恒定时间比较，不管匹配还是错误，验证耗时都一样。这是密码学里'侧信道攻击'的经典防御。我把这点作为面试标准答案——90% 候选人不会主动提。」

---

## 8. 踩坑清单


| 坑                     | 现象                          | 解法                                       |
| --------------------- | --------------------------- | ---------------------------------------- |
| 漏装 argon2-cffi        | passlib 报 backend not found | 用 `passlib[argon2]` extras               |
| bcrypt 老项目迁移 Argon2id | 老用户登不上                      | 设 `deprecated="auto"` + verify 时自动用老算法验证 |
| 单次 hash > 1 秒         | 用户体验差                       | 调低 m（如 32768）或 t（如 2）                    |
| 存储空间大                 | hash 字符串 100+ 字节            | 正常——密码 hash 就该这么大（vs 明文 8-20 字节）         |
| timing attack 泄漏      | 攻击者逐字符破解                    | 用 passlib（已内置）而不是手写 `==`                 |


---

## 9. 参考资源

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [Argon2 RFC 9106](https://datatracker.ietf.org/doc/html/rfc9106)
- [PHC string format](https://github.com/P-H-C/phc-string-format/blob/master/phc-sf-spec.md)
- [passlib Argon2 文档](https://passlib.readthedocs.io/en/stable/lib/passlib.hash.argon2.html)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘