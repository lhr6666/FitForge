# SSH 远程连接知识复盘

> 2026/07/02 周二任务产出
> 目标：把 SSH 密钥对、客户端配置、首次登录流程系统梳理一遍

## 一、SSH 是什么？为什么要用 SSH？

SSH（Secure Shell）是一种**加密的网络传输协议**，用于在不安全的网络中安全地远程登录和操作服务器。

**FitForge 用 SSH 的场景**：
- 本地 Windows → 腾讯云 Ubuntu 服务器（部署 FastAPI）

**为什么不用密码登录**：
- 密码有被暴力破解的风险（服务器 22 端口常年被扫描）
- 密码可能在传输中被窃听（虽然 SSH 本身加密，但弱密码易被攻破）
- 密钥对登录：**私钥签名** vs **密码明文**——前者是数学难题（RSA/Ed25519），后者是"知道不知道"

## 二、密钥对机制（公钥 + 私钥）

```
本地 Windows                              腾讯云服务器
┌──────────────────┐                    ┌──────────────────┐
│ 私钥 (private)    │                    │ 公钥 (public)     │
│ id_ed25519        │ ──── 签名证明身份 ──→│ authorized_keys  │
│ (永 远 不 外 泄)   │                    │ (可给任何人)      │
└──────────────────┘                    └──────────────────┘
```

**关键点**：
- **私钥留在本地**（永远不外传，包括不传 GitHub）
- **公钥放到服务器**（放多个服务器都行，公钥本身就是公开的）
- 登录时，服务器用公钥验证一个**只有私钥能产生的签名**——证明"你就是私钥持有者"

**面试话术**：
> "我把 SSH 登录类比为现实中的印章：私钥是印章本身（一旦丢失就要作废重刻），公钥是印章的备案复印件（任何机构都可以留一份）。你用印章盖个章，对方拿备案复印件比对——这就是非对称加密的本质。"

## 三、ed25519 vs RSA

| 维度 | ed25519 | RSA-2048 |
|------|---------|----------|
| 密钥长度 | 256 位 | 2048 位 |
| 生成速度 | 极快 | 较慢 |
| 签名速度 | 极快 | 较慢 |
| 安全等级 | 128 位（足够） | 112 位 |
| 标准化年份 | 2011 | 1977 |
| 抗量子计算 | 较弱（但目前都较弱） | 较弱（但目前都较弱） |
| 现代推荐度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

**D13 决策**：FitForge 选 ed25519（实际是用户 ssh-keygen 默认生成的）

**理由**：
- 更短（密钥文件小、传输快）
- 更快（签名验证都更快）
- 更现代（2011 年后标准化）
- NIST 2019 后推荐替代 RSA

**RSA 优势**：
- 兼容性更广（老系统都支持）
- 已部署 30+ 年，审计充分

**面试话术**：
> "我选 ed25519 而非 RSA-2048，是因为 ed25519 用 256 位密钥就能达到 RSA-2048 的安全等级，密钥文件小 8 倍、签名速度快 10 倍。短期看不出差异，但大规模部署（如 GitHub）会显著降低 CPU 负载。"

## 四、ssh-keygen 命令详解

```bash
# FitForge 实际用的命令
ssh-keygen -t ed25519 -f D:/ssh/id_ed25519 -C "fitforge@lhr6666"

# 解释：
# -t ed25519             密钥类型
# -f D:/ssh/id_ed25519   私钥输出路径
# -C "comment"           注释（一般填邮箱或用途，便于识别）
```

**生成后会问**：
```
Enter passphrase (empty for no passphrase):  [输入密码]
Enter same passphrase again:                 [再输入一次]
```

**密码的作用**：
- 即使私钥被偷，攻击者仍需破密码
- **强烈建议设密码**（生产环境硬性要求）

**FitForge 实际**：用户为私钥设了密码（增加安全性）

## 五、~/.ssh/config 别名机制

**FitForge 实际配置**：
```
Host fitforge
    HostName 114.132.83.99
    Port 22
    User ubuntu
    IdentityFile D:/ssh/id_ed25519
    IdentitiesOnly yes
```

**配置项解释**：

| 字段 | 作用 |
|------|------|
| Host | 别名（自己起的小名） |
| HostName | 真实 IP 或域名 |
| Port | SSH 端口（默认 22） |
| User | 登录用户名 |
| IdentityFile | 私钥路径 |
| IdentitiesOnly | 只用这个私钥（防止 SSH agent 提供其他） |

**好处**：
- `ssh fitforge` 替代 `ssh -i D:/ssh/id_ed25519 ubuntu@114.132.83.99 -p 22`
- 多个服务器可以各自配不同别名

**面试话术**：
> "我用 SSH config 别名管理多台服务器——开发环境一台、测试环境一台、生产环境一台、GitHub 一份。`ssh dev` / `ssh prod` / `ssh github` 比每次记 IP 端口用户名高效 10 倍。"

## 六、首次登录的指纹验证

**FitForge 实际过程**：
```
The authenticity of host '114.132.83.99' can't be established.
ED25519 key fingerprint is SHA256:K5vT4n9j8mP2xQ7yR3sB6cD1eF0gH5iJ8kL2mN9oP4q.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

**为什么会有这一步**？

SSH 第一次连服务器，本地 `known_hosts` 文件里没有这个服务器的"指纹"——SSH 问你要不要信任这个服务器。

**指纹是什么**？
- 服务器公钥的哈希（SHA256）
- 每个服务器一对公钥 → 一个独一无二的指纹
- 理论上没人能伪造（公钥长度保证）

**该点 yes 还是 no**？
- **是新服务器**（刚买的、确认 IP 对）→ `yes`
- **不是新服务器**（之前用过、突然问）→ `no`（可能中间人攻击）

**FitForge 实际情况**：用户点了 yes（确认是新买的腾讯云服务器）

**面试考点**（SSH 钓鱼攻击）：
> "我每次 ssh 到新服务器都会核对指纹——尤其是生产环境，'指纹对不上'可能是中间人攻击（MITM）。GitHub 的 SSH 指纹在官网公开，可以对比防止假冒。"

## 七、Windows 上 SSH 的特殊性

**问题 1：chmod 600 无效**
```bash
chmod 600 D:/ssh/id_ed25519
# ls -la 后仍然显示 -rw-r--r--
```

**原因**：Windows NTFS 文件系统不支持 Unix mode 位，Git Bash 模拟的 mode 不会真的改变文件权限。

**真正起作用的是**：NTFS ACL（Access Control List）——Windows 的"权限"机制。

**解法**：
- 在 Windows 资源管理器右键 → 属性 → 安全 → 高级 → 删除其他用户
- 或者直接用 `icacls` 命令

**重要**：SSH 不验证 Unix mode，**但 macOS / Linux 上会验证**——如果私钥 mode 太松，SSH 拒绝使用。

**问题 2：路径分隔符**
```bash
# Windows 风格
D:/ssh/id_ed25519
# Git Bash 转 Unix
/d/ssh/id_ed25519
```

两个都有效，Git Bash 自动转换。

**问题 3：known_hosts 位置**
- Windows: `C:\Users\<user>\.ssh\known_hosts`
- Linux: `~/.ssh/known_hosts`
- macOS: `~/.ssh/known_hosts`

**面试话术**：
> "我装 FitForge 时发现一个 Windows 上的'假问题'——`chmod 600` 改了 `ls` 显示的 mode 位，但 NTFS 不支持 Unix mode，SSH 还是能用。这教会我'不要靠 `ls` 看到的权限判断安全与否，要看实际能不能用'。"

## 八、服务器主机名解读

FitForge 服务器首次登录后看到：
```
Welcome to Ubuntu 22.04.4 LTS (GNU/Linux 5.15.0-105-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

 System information as of 2026/07/02 ...

 * System load:  0.08              ← 系统负载（0-1 健康）
 * Usage of /:   11.1% of 39.26G  ← 磁盘使用
 * Memory usage: 7%                ← 内存使用
 * Processes:    125               ← 进程数
 * Users logged in: 0              ← 当前登录用户
 * IPv4 address for eth0: 10.1.0.15 ← 内网 IP

 ubuntu@VM-0-15-ubuntu:~$
```

**解读**：
- `VM-0-15-ubuntu`：腾讯云给的内网主机名
- `10.1.0.15`：内网 IP（同一可用区服务器间通信用）
- `114.132.83.99`：公网 IP（外网访问用）
- `ubuntu`：当前登录用户（sudo 权限用户）
- `~`：当前目录（家目录 = `/home/ubuntu`）
- `$`：普通用户提示符（`#` 是 root 提示符）

**面试话术**：
> "我通过 MOTD（Message of the Day）快速判断服务器健康度——看 load / disk / memory / processes。0.08 的 load 表示 CPU 几乎空闲，刚买的服务器就该是这样。如果 load > CPU 核数，说明有进程卡住了。"

## 九、FitForge 周二实操记录

### 1. SSH 密钥生成
- 命令：`ssh-keygen -t ed25519 -f D:/ssh/id_ed25519 -C "fitforge@lhr6666"`
- 私钥密码：用户自行设置（保护私钥）

### 2. SSH config 配置
- 文件：`C:\Users\ab888\.ssh\config`
- 内容：见第五节

### 3. 指纹验证
- 第一次登录服务器，确认指纹后输入 `yes`

### 4. 失败 → 成功的过程
- 失败：服务器默认禁密码认证，连接被关
- 成功：腾讯云控制台绑定密钥对 + 重置 ubuntu 密码

**详见 error_logs/2026-07-02-ssh-troubleshooting.md**

## 十、一句话总结

> SSH 的核心是**非对称加密** + **首次信任锚定**（指纹） + **配置复用**（config 别名）。

把这三件事理解透，SSH 就不再神秘。

---

**参考资源**：
- [OpenSSH 官方文档](https://www.openssh.com/manual.html)
- [SSH 配置文件详解](https://man.openbsd.org/ssh_config)
- [腾讯云 SSH 密钥对文档](https://cloud.tencent.com/document/product/213/6092)
