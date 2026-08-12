# SSH 实战 + Cursor Remote SSH 完整指南

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D14（SSH 别名 `fitforge`）、D15（SSH config 别名管理）、D18（Windows SSH 私钥权限收紧）、D7（RSA 密钥 → 实际 ed25519）
> **关联文档**：`tech_notes/2026-07-02-ssh-essentials.md`（旧版）、`error_logs/2026-07-06-cursor-ssh-permission.md`
> **目的**：SSH 概念速查 + Cursor Remote SSH 原理 + 踩坑清单

---

## 1. SSH 是什么（初学者友好版）

**SSH = Secure Shell** —— 远程"登录"另一台电脑的命令行协议。

```
你的电脑（Git Bash）                远程服务器（Ubuntu 22.04）
┌─────────────────┐                ┌──────────────────┐
│ Windows 11       │ ═══SSH 隧道═══> │ Ubuntu Server    │
│ + Git Bash       │                │ 114.132.83.99    │
│                 <═══ 安全双向 ═══ │                  │
└─────────────────┘                └──────────────────┘
```

**类比**：
- 远程桌面（图形界面）vs **SSH 命令行**（纯文字）
- 区别：SSH 不传图像，只传命令和输出文本——更快、更安全、更适合服务器

**为什么要用 SSH**：
- 服务器没有显示器（headless），只能命令行管理
- 加密传输（不会明文泄露密码）
- 非对称加密（私钥 + 公钥）—— 比密码登录安全 100 倍

---

## 2. 一次 SSH 连接的 3 个要素

```bash
ssh -i <私钥路径> <用户名>@<服务器IP>
```

| 要素 | FitForge 实际值 | 说明 |
|------|----------------|------|
| **服务器 IP** | `114.132.83.99` | 腾讯云 CVM 公网 IP |
| **用户名** | `ubuntu` | Ubuntu 22.04 默认用户 |
| **私钥路径** | `D:/ssh/id_ed25519` | 本地私钥（永远不外传）|
| **私钥算法** | ed25519 | 256 位椭圆曲线，比 RSA-2048 安全且快（D13 决策）|
| **服务器公钥** | 腾讯云控制台绑定的 | 登录时跟私钥匹配 |

**为什么需要 3 个要素**：
- **IP**：找到目标服务器
- **用户名**：服务器上的"账号"
- **私钥**：证明"你是你"（不是密码登录，是私钥签名）

---

## 3. 3 种连接方式（按推荐度排序）

### 3.1 方式 A：直接命令行（最简单，临时用）

```bash
ssh -i D:/ssh/id_ed25519 ubuntu@114.132.83.99
```

**缺点**：
- 每次都要输一长串（包括私钥路径）
- 多个服务器管理麻烦
- 适用场景：偶尔连一次

### 3.2 方式 B：SSH config 别名（推荐，日常用）⭐

#### 配置文件位置

| OS | config 路径 |
|----|------------|
| Windows | `C:\Users\<你的用户名>\.ssh\config` |
| Linux/Mac | `~/.ssh/config` |

#### 配置内容

```config
# FitForge 腾讯云 CVM（D14 决策）
Host fitforge
    HostName 114.132.83.99
    User ubuntu
    IdentityFile D:/ssh/id_ed25519
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3

# 未来加服务器只需复制一段
# Host another-server
#     HostName <IP>
#     User <user>
#     IdentityFile <key>
```

#### 配置项详解

| 配置项 | 作用 | 不写的后果 |
|--------|------|----------|
| `Host` | 别名（自己取的名字） | 必填 |
| `HostName` | 服务器 IP 或域名 | 必填 |
| `User` | 登录用户名 | 必填 |
| `IdentityFile` | 私钥绝对路径 | 必填 |
| `IdentitiesOnly yes` | 强制只用指定私钥 | SSH agent 提供其他私钥 → 认证失败 |
| `ServerAliveInterval 60` | 每 60 秒发心跳 | 长时间不动 → 连接断 |
| `ServerAliveCountMax 3` | 3 次没心跳才断 | 配合 AliveInterval |

#### 使用

```bash
# 配好 config 后，只需
ssh fitforge

# 不需要输 -i / 用户名 / IP / 私钥路径
```

**优点**：
- 简洁 10 倍
- 多个服务器集中管理
- 适用场景：每天都要连

### 3.3 方式 C：Cursor Remote SSH（IDE 集成，最强）⭐⭐

#### 工作原理

```
┌──────────────────────────────────┐         ┌─────────────────────────┐
│ 你的 Windows + Cursor              │═════════│  Ubuntu 22.04 服务器     │
│ （左下角显示 SSH: fitforge）        │  SSH    │  + 完整开发环境           │
│                                  │  隧道   │  - Python 3.10          │
│ 视觉上看：本地 Cursor 跑在 Windows │         │  - 远程工作区            │
│ 实际：所有文件操作都在服务器上      │         │  - 远程 Python 解释器     │
│                                  │         │  - 远程终端（Ctrl+`）    │
└──────────────────────────────────┘         └─────────────────────────┘
```

**关键点**：
- Cursor 视觉上在 Windows 跑
- 文件编辑 → SSH 传过去 → 服务器保存
- 终端执行 → 服务器上跑
- **所见即所得**：左边文件栏显示的"工作区"是服务器上的文件夹

#### Cursor Remote SSH 操作步骤

```
Step 1: Cursor 装 Remote-SSH 扩展（首次启动 Cursor 已自带）
  ↓
Step 2: Ctrl+Shift+P → 输入 "Remote-SSH: Connect to Host"
  ↓
Step 3: 选 fitforge（SSH config 里的别名）
  ↓
Step 4: 选服务器系统 Linux
  ↓
Step 5: 等 5-10 秒连上，左下角显示 "SSH: fitforge"
  ↓
Step 6: File → Open Folder → 选服务器路径（如 /home/ubuntu/fitforge）
  ↓
Step 7: 左侧文件栏显示服务器文件 —— 可以直接编辑
  ↓
Step 8: Ctrl+` 打开终端 —— 终端是服务器的命令行
  ↓
Step 9: 写代码 → 跑命令 → 都跟服务器一致
```

#### 适用场景

- ✅ **大项目代码直接在服务器跑**（不用 scp/git 同步）
- ✅ **真环境测试**（不是本地 Docker）
- ✅ **服务器上跑生产代码**（性能、直连 DB）
- ❌ 临时调试（用方式 B Git Bash 就够）

#### 为什么 FitForge 用 Cursor Remote SSH（vs 只用 Git Bash）

按你早期规划："本地 Windows 写代码 + 测，最后用 Cursor Remote SSH 同步到服务器跑 alembic"

但**更好**的方式：
- **直接**在 Cursor Remote SSH 里写代码 → 跑 alembic → 跑 uvicorn
- 不用 scp/git 同步到服务器
- "本地"和"服务器"两套环境一致

按你目前实际：**也用 Docker MySQL 本地开发**（fitforge-mysql 容器），所以：
- 本地开发：Docker MySQL + 本地 uvicorn
- 服务器部署：scp/git 同步 + 服务器 MySQL + 服务器 uvicorn
- 两者并存，符合 D26 决策

---

## 4. 私钥权限：D18 决策详解

### 4.1 为什么私钥权限重要

SSH 私钥是"身份凭证"——拿到的人就**能进服务器**。所以私钥权限必须严格：

- **太松**（其他用户可读）：SSH 拒绝用（报警"private key is too open"）
- **太严**（自己都读不了）：SSH 拒绝用（permission denied）

### 4.2 Windows 上的权限工具：D18 决策

```powershell
# ❌ 不要用 chmod（NTFS 不支持 Unix mode，D18 决策）
chmod 600 D:/ssh/id_ed25519   # 没效果

# ✅ 用 icacls（Windows 原生命令）
powershell -Command 'icacls "D:\ssh\id_ed25519" /inheritance:r /grant:r "$env:USERNAME:(R)"'
```

**参数详解**：
- `/inheritance:r` —— **移除**所有继承的权限（cut 掉家庭组等）
- `/grant:r "$env:USERNAME:(R)"` —— **只**给当前用户**只读**权限（R）

**验证权限**：
```powershell
icacls D:/ssh/id_ed25519
# 输出应该只有 1 行权限：你的用户名:(R)
```

### 4.3 Git Bash OpenSSH vs Cursor Remote SSH 的差异

| 客户端 | 私钥权限检查 | 严格度 |
|--------|-------------|--------|
| Git Bash OpenSSH | 不严格（NTFS 文件权限不影响） | ⚠️ 宽松 |
| **Cursor Remote SSH** | **严格（按 Unix mode 检查）** | ✅ 严格 |

**踩坑**（D18 决策）：
- Cursor Remote SSH 拒连 → 即使 Windows 上文件能读
- 解决：icacls 收紧权限（`/inheritance:r` + 只给自己 R）
- 教训：**跨 SSH 客户端时私钥权限要看"最小公倍数"——用最严的那个**

---

## 5. 实战工作流（从 0 到第一次连接）

```bash
# ===== Step 1: 打开 Git Bash =====
# Windows 终端 / Git Bash / Cursor 内置终端

# ===== Step 2: 测试 SSH 连接（按方式 B 配好 config 后） =====
ssh fitforge

# 首次会问：
# The authenticity of host 'fitforge (114.132.83.99)' can't be established.
# ED25519 key fingerprint is SHA256:abcdefghijklmnop...
# Are you sure you want to continue connecting (yes/no/[fingerprint])?
# → 输入 yes（信任这台服务器）

# ===== Step 3: 登录成功，看到服务器提示符 =====
# Welcome to Ubuntu 22.04 LTS (GNU/Linux 5.15.0-...)
# Last login: Tue Jul  6 14:30:00 2026 from 1.2.3.4
# 
# ubuntu@VM-0-15-ubuntu:~$ 
#  ↑ 现在你在远程服务器上

# ===== Step 4: 跑命令验证 =====
uname -a     # 看 Linux 内核
python3 --version   # 看 Python 版本
ls ~/        # 看 home 目录
pwd          # 当前路径

# ===== Step 5: 退出 SSH =====
exit        # 或 Ctrl+D
# Connection to fitforge closed.
```

---

## 6. 4 类常见 SSH 报错 + 排查

### 6.1 `Connection refused`

```
ssh: connect to host 114.132.83.99 port 22: Connection refused
```

**原因**：
- 服务器没开 SSH 服务 / 防火墙拦了 22 端口
- 腾讯云安全组没放行 22

**排查**：
1. 腾讯云控制台 → 实例 → 安全组 → 放行 22 端口
2. 服务器：`sudo systemctl status sshd`（看 SSH 服务是否运行）

### 6.2 `Permission denied (publickey)`

```
ubuntu@114.132.83.99: Permission denied (publickey).
```

**原因**：
- 私钥路径错
- 私钥权限太松（Cursor Remote SSH 严格模式）
- 服务器公钥没匹配（用了错私钥）

**排查**：
1. 检查 `IdentityFile` 路径正确
2. `icacls D:/ssh/id_ed25519` 看权限
3. 服务器上 `cat ~/.ssh/authorized_keys` 看是否包含本地公钥

### 6.3 `Host key verification failed`

```
The authenticity of host 'fitforge' can't be established.
ED25519 key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no)?
```

**原因**：**正常** —— 首次连接，SSH 不知道这台服务器

**处理**：
- 输入 `yes`（信任并写入 `~/.ssh/known_hosts`）
- 下次连接会自动验证

### 6.4 `Connection reset by peer` / `Connection closed`

```
Connection reset by 114.132.83.99 port 22
```

**原因**：
- 防火墙 / WAF 拦截
- 服务器 SSH 配置 AuthMethods 限制
- 腾讯云控制台没绑密钥对

**排查**：
- 腾讯云控制台 → 实例 → 重置密码 + 绑定 SSH 密钥对
- 服务器 `/etc/ssh/sshd_config` 看 `PasswordAuthentication`

---

## 7. 面试话术（5 题预演）

### Q1：SSH 是什么，怎么连？

> "SSH 是 Secure Shell 协议，远程登录 Linux 服务器用。3 个要素：服务器 IP、用户名、私钥路径。Git Bash 用 `ssh user@ip` 连。日常用我配 SSH config 别名（`Host fitforge` + `HostName` + `IdentityFile`），之后 `ssh fitforge` 一行连上。"

### Q2：SSH 密钥比密码安全在哪？

> "密码可能被暴力破解（每秒几百万次试），SSH 私钥是 256 位 ed25519 椭圆曲线密钥——数学难题破解不动。公钥存服务器，私钥只在本地，签名—验证流程天然防中间人攻击。"

### Q3：ed25519 vs RSA 怎么选？

> "ed25519 256 位密钥达到 RSA-2048 安全等级，签名验证快 10 倍，密钥小 8 倍（NIST 2019 推荐）。RSA 唯一优势是兼容性广——如果客户端都是老的才用 RSA。新项目直接 ed25519。"

### Q4：Cursor Remote SSH 是什么原理？

> "Cursor 通过 SSH 隧道连服务器，远程文件 + 远程 Python 解释器 + 远程终端。你视觉上在 Windows 用 Cursor 写代码，实际所有文件操作都在服务器上跑。优点是真环境测试（不是本地 Docker 模拟），不用 scp/git 同步代码。"

### Q5：Windows 上 SSH 私钥权限怎么设？

> "NTFS 不支持 Unix mode，chmod 600 没效果。用 `icacls D:/ssh/id_ed25519 /inheritance:r /grant:r "$env:USERNAME:(R)"` 收紧——移除继承权限 + 只给当前用户读。Cursor Remote SSH 严格检查 Unix mode，Git Bash OpenSSH 不严格——以最严的为准。"

---

## 8. 踩坑清单（按发生概率排序）

| 坑 | 现象 | 解法 |
|----|------|------|
| **chmod 600 无效** | Windows NTFS 不支持 | `icacls` 替代（D18 决策）|
| **Permission denied (publickey)** | 私钥权限太松 | `icacls /inheritance:r /grant:r USERNAME:(R)` |
| **Connection refused** | 腾讯云安全组没放行 22 | 控制台 → 安全组 → 放行 22 |
| **Host key verification failed** | 首次连接 | 正常，输入 `yes` |
| **Connection closed after 5min** | 长时间不动 + 防火墙超时 | `~/.ssh/config` 加 `ServerAliveInterval 60` |
| **公钥不匹配** | 用错私钥 | 服务器 `cat ~/.ssh/authorized_keys` 检查 |
| **中文乱码** | Putty 终端编码 | Git Bash 自动 UTF-8，没问题 |
| **scp 慢** | 用 Git 替代 | `git push` + 服务器 `git pull` |
| **Cursor Remote SSH 拒连** | 私钥权限 | `icacls` 修（D18）|
| **SSH agent 干扰** | 用了错的私钥 | `IdentitiesOnly yes` 强制只用指定私钥（D14）|

---

## 9. FitForge 项目特定的 SSH 用法

### 9.1 部署流程（部署到服务器）

```bash
# 1. 开发完成 → 在 Cursor Remote SSH 里直接改服务器代码（或 git push + pull）
# 2. 服务器跑 alembic
cd ~/fitforge
source venv/bin/activate
alembic upgrade head

# 3. 服务器跑 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000

# 4. 客户端访问
curl http://114.132.83.99:8000/auth/register -X POST ...
```

### 9.2 安全清单

- [ ] 私钥用 ed25519（不要 RSA-2048）
- [ ] 私钥 chmod 600 / icacls 收紧
- [ ] SSH config 加 `IdentitiesOnly yes`
- [ ] 服务器 SSH 关闭密码登录（`PasswordAuthentication no`）
- [ ] 服务器防火墙只放行 22 + 80 + 443
- [ ] 私钥加 passpharse（额外一层保护）

---

## 10. 参考资源

- [SSH 官方文档](https://www.openssh.com/manual.html)
- [ed25519 算法原理](https://ed25519.cr.yp.to/)
- [Visual Studio Code Remote SSH 文档](https://code.visualstudio.com/docs/remote/ssh)
- [腾讯云 SSH 密钥对使用](https://cloud.tencent.com/document/product/213/16691)
- [Windows icacls 命令](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls)

---

## 附录 A：FitForge SSH 配置完整示例

```config
# ~/.ssh/config（Windows: C:\Users\用户名\.ssh\config）

# FitForge 腾讯云 CVM（D14 决策）
Host fitforge
    HostName 114.132.83.99
    User ubuntu
    IdentityFile D:/ssh/id_ed25519
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
    # 如需 SSH 端口转发（开发用，本地 3307 → 服务器 3307）
    # LocalForward 3307 localhost:3307
```

---

## 附录 B：腾讯云 CVM 首次 SSH 设置流程

```
1. 腾讯云控制台 → CVM → 实例
2. 选择实例 → 更多 → 密码/密钥 → 重置密码
3. 绑定 SSH 密钥对：
   - 创建新密钥对 → 自动下载 .pem 私钥
   - 或绑定已有密钥（公钥）
4. 安全组 → 入站规则 → 放行 22 端口
5. 实例状态 → 运行中
6. 客户端 ssh ubuntu@<IP>
```

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘