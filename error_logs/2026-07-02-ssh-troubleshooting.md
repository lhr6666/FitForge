# SSH 远程登录错误排查记录

> 2026/07/02 周二
> 记录 SSH 登录腾讯云服务器过程中遇到的 3 个错误及解法

## 错误 1：ls -la D:/ssh/ 无反应

**现象**：
用户输入 `ls -la D:/ssh/` 后，命令执行但没有显示任何文件列表。

**截图证据**：截图显示 `/d/ssh/` 下有 `id_ed25519` 和 `id_ed25519.pub` 两个文件，但 `D:/ssh/` 路径在 Git Bash 里似乎没生效。

**原因分析**：
Git Bash 在 Windows 上处理盘符路径有两种方式：
- `D:/ssh/` → Bash 把它当作相对路径下的 `D:` 目录
- `/d/ssh/` → 这是 Git Bash 推荐的 Unix 风格（盘符当根目录下的文件夹）

**解法**：
- 使用 `/d/ssh/` 而不是 `D:/ssh/`
- 或者 `cd /d/ssh` 然后 `ls -la`

**教训**：
> Git Bash 是模拟层，路径要按 Unix 风格来才稳定。

**简历亮点**：
> "我解决过 Git Bash 在 Windows 上的路径解析问题——盘符路径要转 Unix 风格（`/d/` 替代 `D:/`），这是 Git for Windows 的'方言'。"

---

## 错误 2：chmod 600 D:/ssh/id_ed25519 无效

**现象**：
```bash
chmod 600 D:/ssh/id_ed25519
ls -la D:/ssh/id_ed25519
# -rw-r--r-- 1 ...  （权限没变）
```

**原因分析**：
Windows NTFS 文件系统不支持 Unix mode 位（rwx 三组九位）。

Git Bash 显示的 mode 是**模拟**的（从 NTFS ACL 推导的近似值），但 `chmod` 命令实际上没有真正改变底层权限。

**真正起作用的权限系统**：
- **Windows**: NTFS ACL（Access Control List）
- **Linux/macOS**: Unix mode 位

**解法**：
- 方案 A：忽略 `ls` 显示的 mode，**直接测试 SSH 能否工作**
- 方案 B：在 Windows 资源管理器右键 → 属性 → 安全 → 高级 → 删除其他用户
- 方案 C：用 `icacls` 命令（Windows 原生命令）：
  ```bash
  icacls "D:\ssh\id_ed25519" /inheritance:r /grant:r "%USERNAME%:(R)"
  ```

**教训**：
> `chmod` 在 Windows 上是"假动作"——SSH 不会因为 mode 位不对而拒绝（因为 Windows 本来就没有 Unix mode）。
> 但**生产环境（Linux 服务器）会**——如果私钥 mode 是 644，SSH 直接拒绝使用并报错"Permissions 0644 for 'id_ed25519' are too open"。

**面试话术**：
> "我意识到跨平台开发的一个陷阱：同一命令（`chmod`）在 Windows 和 Linux 上行为不一样。`ls` 显示的 mode 在 Windows 上是模拟的——这教会我'工具的输出要看实际效果，不要相信表面'。"

---

## 错误 3：Connection closed by 114.132.83.99 port 22

**现象**：
成功验证指纹后，SSH 连接被服务器关闭：
```
ubuntu@114.132.83.99: Permission denied (publickey).
或
Connection closed by 114.132.83.99 port 22
```

**原因分析**（**核心问题**）：
腾讯云 Ubuntu 服务器**默认禁用密码认证**，只接受公钥认证。

但用户的公钥**还没传到服务器**——之前生成的公钥 `id_ed25519.pub` 还在本地 Windows 上。

**完整过程**：
1. 用户生成了密钥对（本地）
2. 用户配置了 `~/.ssh/config`（本地）
3. 用户尝试 SSH 连接（指纹 OK，连接失败）
4. 因为服务器 authorized_keys 里没有用户的公钥

**解法**（腾讯云特定流程）：
1. 登录腾讯云控制台
2. 进入 CVM 实例详情
3. 重置 ubuntu 用户的密码（**虽然用密钥登录，但 sudo 还需要密码**）
4. 在「密钥对」页面，上传用户的公钥 `id_ed25519.pub`
5. 绑定密钥对到该 CVM 实例
6. 重启 CVM 实例

**或者**（传统方法）：
- 在服务器上手动把公钥追加到 `/home/ubuntu/.ssh/authorized_keys`
- 但用户**没有服务器控制台访问权限**（云服务器不会给你 VNC），所以走控制台流程

**教训**：
> 首次访问新购买的云服务器，**密钥对绑定必须在控制台完成**——不是 SSH 能解决的事。
> 不同的云厂商流程不同：
> - **腾讯云**：控制台 → 密钥对 → 绑定实例
> - **AWS EC2**：启动实例时直接选密钥对
> - **阿里云**：控制台 → SSH 密钥对 → 绑定
> - **GCP**：元数据 → SSH 密钥 → 添加

**简历亮点**：
> "我处理过腾讯云 CVM 的'首次访问'特殊流程——SSH 失败不是因为密码错，而是因为服务器根本没收到我的公钥。需要在控制台绑定密钥对才能让 SSH 走通。这种'密钥对管理'经验是云原生的核心能力。"

---

## 总复盘

| 错误 | 表面现象 | 真实原因 | 解法 |
|------|----------|----------|------|
| 1 | ls -la 无反应 | Git Bash 路径处理 | 改用 `/d/ssh/` |
| 2 | chmod 600 无效 | Windows NTFS 不支持 Unix mode | 直接测 SSH 是否能工作 |
| 3 | Connection closed | 腾讯云默认禁密码 + 公钥未传 | 控制台绑定密钥对 + 重置密码 |

**核心经验**：
1. 工具的输出要分清"模拟"和"实际"（ls 看到的 mode ≠ 真实权限）
2. 跨平台开发要意识到命令在不同系统的行为差异
3. 云服务器首次访问**必须在云厂商控制台完成密钥对绑定**——SSH 自己解决不了

---

**Date**: 2026-07-02
**Author**: LHR6666 (with Claude Code assistance)
