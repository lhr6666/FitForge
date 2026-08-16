# Cursor Remote SSH 权限错误（Windows 私钥太开放）

> 2026/07/06（项目周二后续调试）
> 记录 Cursor 连服务器失败的原因和解法

## 错误现象

Cursor → `Ctrl+Shift+P` → "Remote-SSH: Connect to Host" → 输入 `fitforge` → 失败

错误弹窗内容：
```
Permissions for 'D:/ssh/id_ed25519' are too open.
It is required that your private key files are NOT accessible by others.
This private key will be ignored.
Load key "D:/ssh/id_ed25519": bad permissions
ubuntu@114.132.83.99: Permission denied (publickey).
```

## 根本原因（**为什么 Git Bash 能连但 Cursor 不能**）

之前用 `chmod 600` 在 Git Bash 改私钥权限，**Windows NTFS 不支持 Unix mode**（详见 `error_logs/2026-07-02-ssh-troubleshooting.md` 错误 2）。

但 Cursor 的 SSH 库（VS Code Remote-SSH）**比 Git Bash 的 OpenSSH 严格**——它真的检查 Unix mode 位，发现权限"太开放"就拒绝用这个私钥。

| SSH 客户端 | 检查机制 | Windows 上的行为 |
|-----------|----------|-----------------|
| Git Bash OpenSSH | Windows ACL（宽松） | mode 显示 644 也能用 |
| Cursor Remote-SSH | Unix mode（严格） | mode 必须 600 |

## 解法

`chmod` 是"假动作"，必须用 **Windows 原生命令 `icacls`** 真正收紧权限。

### Git Bash 上第一次失败的坑

```bash
icacls "D:\ssh\id_ed25519" /inheritance:r /grant:r "%USERNAME%:(R)"
```

**报错**：
```
%USERNAME%: 账户名与安全标识间无法做任何映射完成。
已成功处理 0 个文件；处理 1 个文件时失败
```

**原因**：Git Bash 是 Unix-like shell，**不展开 Windows 风格的 `%USERNAME%`**。它被当字面字符串传给 icacls，icacls 找不到这个"账户名"。

### 三种正确的解法（任选一种）

#### 方案 A：用 PowerShell 调用（最稳妥）

```bash
powershell -Command 'icacls "D:\ssh\id_ed25519" /inheritance:r /grant:r "$env:USERNAME:(R)"'
```

`$env:USERNAME` 是 PowerShell 的环境变量语法，会正确展开为 `ab888`。

#### 方案 B：用 bash 的 `$(whoami)` 命令替换

```bash
icacls "D:\ssh\id_ed25519" /inheritance:r /grant:r "$(whoami):(R)"
```

**坑**：Git Bash 的 `whoami` 有时返回 `DESKTOP-xxx\ab888`，有时只返回 `ab888`——行为不统一。

#### 方案 C：用 bash 的 `$USERNAME` 变量

```bash
icacls "D:\ssh\id_ed25519" /inheritance:r /grant:r "$USERNAME:(R)"
```

Git Bash 通常把 `$USERNAME` 当环境变量展开。

### 参数解释

| 参数 | 含义 |
|------|------|
| `/inheritance:r` | 移除所有继承的权限（包括 `BUILTIN\Users`、`Authenticated Users`） |
| `/grant:r "$env:USERNAME:(R)"` | 只给当前用户读权限（`:r` 表示替换现有 grant） |
| `(R)` | 只读权限（私钥不需要写） |

### 验证

```bash
icacls "D:\ssh\id_ed25519"
```

预期看到**只有一行**：
```
D:\ssh\id_ed25519 DESKTOP-xxx\ab888:(R)
```

如果还有 `BUILTIN\Users` 或 `Authenticated Users` → 没成功。

## icacls 输出"开放模式"对照

修复**前**会看到：
```
D:\ssh\id_ed25519 BUILTIN\Administrators:(I)(F)
                  NT AUTHORITY\SYSTEM:(I)(F)
                  NT AUTHORITY\Authenticated Users:(I)(M)   ← ⚠️ 任何登录用户
                  BUILTIN\Users:(I)(RX)                       ← ⚠️ Users 组（读+执行）
```

修复**后**只剩：
```
D:\ssh\id_ed25519 DESKTOP-xxx\ab888:(R)
```

## 教训

1. **Windows 私钥权限**：永远不要靠 `chmod`，用 `icacls` 才对（NTFS 不支持 Unix mode）
2. **跨工具兼容性**：Git Bash SSH 和 Cursor SSH 严格度不同，私钥权限要"按最严"
3. **Git Bash 不展开 `%VAR%`**：要用 PowerShell `$env:VAR` 或 bash `$VAR` / `$(cmd)`
4. **`/inheritance:r` 是关键**：不只设当前用户权限，还要**移除继承**——否则 BUILTIN\Users 还会继承读权限

## 简历亮点

> "我处理过 Windows 上 SSH 私钥权限的两套标准——Git Bash 用 Windows ACL（宽松）、Cursor Remote-SSH 用 Unix mode（严格）。用 `icacls /inheritance:r` + PowerShell `$env:USERNAME` 解决 Git Bash 不展开 Windows 环境变量的坑。这是跨平台开发'细节决定成败'的真实案例——Windows + 多个 SSH 客户端的'最小公倍数'权限策略。"

---

**Date**: 2026-07-06
**Author**: LHR6666 (with Claude Code assistance)
**关联决策**：D18