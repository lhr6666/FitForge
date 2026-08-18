# 修复 requirements.txt 漏 PyJWT（2026-08-18 周一）

> **类型**：CLAUDE.md「依赖管理」红线违反 + 工程漏洞追溯修复
> **触发事件**：2026-08-18 周一开工，部署前 grep 验证发现
> **关联事件**：`error_logs/2026-08-16-server-deploy-4-issues.md` 失误 3（08-16 部署踩坑时**没修本地 requirements.txt**，只服务器装了）
> **关联 commit**：`1622384` `fix(deps): add PyJWT[crypto]==2.10.1`
> **关联决策**：D5（PyJWT 选型）

---

## 症状

早上开工准备部署前，按 08-16 教训部署清单 Step 6.5（grep 验证 requirements.txt）执行 `grep -i 'jwt\|pyjwt\|cryptography' requirements.txt`：

```
$ grep -i 'jwt' requirements.txt
（无输出）
```

**本地 requirements.txt 没有 PyJWT！** — 但 `core/security.py` 大量使用 `import jwt`（RS256 编解码）。

---

## 根因追溯

| 时间 | 事件 | requirements.txt 状态 |
|------|------|----------------------|
| 2026/06/30 | 项目初始化，requirements.txt 第一版 | 5 个核心包（无 PyJWT） |
| 2026/08/13 | 部署 `0460a14`，服务器装 PyJWT 用 `--user` 到 `~/.local/` | **未补 requirements.txt** |
| 2026/08/14 | 加 JWT 4 个函数 + login/refresh/logout/me 端点（commit `da04aec` 等 11 个） | **仍未补**——这是核心违规点 |
| 2026/08/16 | 部署踩 4 个坑，失误 3 报 `ModuleNotFoundError: No module named 'jwt'` | 服务器 `pip install 'PyJWT[crypto]'` **修了服务器但没修本地 requirements.txt** |
| 2026/08/18 | 周一开工，本次部署前 grep 验证才发现 | **本次 commit `1622384` 修复** |

---

## 为什么08-14 / 08-16 漏了

**08-14 时**：加 PyJWT 函数时，**用户已在 venv 中**（可能有 PyJWT 残留或从其他源安装），本地 import 正常就以为"依赖 OK 了"。**没**走 CLAUDE.md 红线要求的"每引入新包必须同步 requirements.txt"。

**08-16 时**：服务器部署失误 3 暴露后，**只**用 `pip install 'PyJWT[crypto]'` 修了服务器，**没**反向同步本地 requirements.txt。当时 deploy checklist（`24fa286`）只加了 Step 6.5 验证命令，但**没**说明"如果缺了要先补本地"。

---

## 修复（commit `1622384`）

**改 3 行**：

```diff
 # argon2-cffi：Argon2 的 C 语言实现（passlib 的依赖）
 argon2-cffi==23.1.0
+# PyJWT[crypto]：JWT 编解码库（D5 决策，弃用 python-jose）
+# [crypto] extras 提供 RS256 非对称签名所需的 cryptography 后端
+PyJWT[crypto]==2.10.1
```

**为什么 `PyJWT[crypto]`（不是 `PyJWT`）**：
- `[crypto]` extras 提供 RS256 需要的 `cryptography` 库后端
- 08-16 失误 3 修服务器时装的是 `PyJWT[crypto]==2.10.1`
- 本次补 requirements.txt 必须保持一致，否则下次部署还会报 `ImportError: No cryptography algorithms`

---

## 教训

### 教训 1：依赖脱漏是隐形技术债

本地 venv 有残留 → import 不报错 → **没人知道 requirements.txt 缺**，直到部署到干净 venv 才崩。这种"本地一切正常"的假象是技术债的温床。

### 教训 2：修复必须双向同步

08-16 修服务器时 `pip install 'PyJWT[crypto]'` 是一次性动作——只修了症状（服务器），没修根因（本地清单）。**真正的修复 = 本地清单 + 服务器一致**。

### 教训 3：CLAUDE.md 红线存在即合理

> 「依赖管理：每引入一个新的Python包，必须同步更新 requirements.txt」

这条红线不是"建议"——是**强制**。PyJWT 漏掉就是因为 08-14 时把"红线"当成了"建议"。**红线 = 不允许例外**。

### 教训 4：部署清单 Step 6.5 升级为"双向修复"

部署清单 Step 6.5（`tech_notes/2026-08-16-deploy-checklist.md`）原描述：

> "若没有 PyJWT：本地 requirements.txt 漏了核心依赖（D5 决策）。**手动装上**：`pip install 'PyJWT[crypto]==2.10.1'`，**之后手动更新本地 requirements.txt 加这行**。"

**这次补充**：如果发现缺失，**第一步是先 commit 修本地 requirements.txt**，再服务器装。这样 git 历史清楚 + 下次部署不会再踩。

---

## 防御 checklist（更新版）

部署前必须 grep 验证的不只是 PyJWT，应该**验证所有 D5-D12 决策依赖**：

```bash
grep -i 'pyjwt\|sqlalchemy\|asyncmy\|pymysql\|alembic\|passlib\|argon2' requirements.txt
# 必须全部命中（7 个核心决策包）
```

如果任何一项缺失，**先 commit 修本地，再继续部署**——不允许"服务器装一下就行"的捷径。

---

## 关联文档

- **失误源头**：`error_logs/2026-08-16-server-deploy-4-issues.md` 失误 3
- **决策依据**：D5（PyJWT vs python-jose）
- **部署清单**：`tech_notes/2026-08-16-deploy-checklist.md` Step 6.5（待修订：强调"先修本地再部署"）
- **修复 commit**：`1622384`

---

## 面试话术

> "我处理过一个**隐形技术债**：本地 venv 有 PyJWT 残留，import 一切正常，但 `requirements.txt` 漏了这一行。代码在本地测试 N 次都没事，直到部署到云端干净 venv 才崩 `ModuleNotFoundError`。教训：**本地能跑 ≠ 依赖清单完整**——必须按 CLAUDE.md 红线'每引入新包必须同步 requirements.txt'，否则就是给未来的自己埋雷。"