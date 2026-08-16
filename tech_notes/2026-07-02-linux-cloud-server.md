# Linux 基础与云服务器知识复盘

> 2026/07/02 周二任务产出
> 目标：把 Linux 常用命令、云服务器特有概念系统梳理一遍
> 注意：本周还**没在服务器上实操命令**（计划下一步：apt 装 Python+MySQL），本文件是知识预热

## 一、服务器连上后第一眼看到什么？

**MOTD**（Message of the Day）—— 每次 SSH 登录都会显示的系统信息：

```
Welcome to Ubuntu 22.04.4 LTS (GNU/Linux 5.15.0-105-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

 System information as of 2026/07/02 ...

 * System load:  0.08              ← CPU 负载
 * Usage of /:   11.1% of 39.26G  ← 根分区使用
 * Memory usage: 7%                ← 内存使用
 * Processes:    125               ← 进程数
 * Users logged in: 0              ← 当前登录用户
 * IPv4 address for eth0: 10.1.0.15 ← 内网 IP

 ubuntu@VM-0-15-ubuntu:~$
```

**8 个关键信息**：
1. **系统版本**：Ubuntu 22.04.4 LTS（长期支持版，到 2027 年）
2. **内核版本**：5.15.0-105-generic（Linux 内核）
3. **架构**：x86_64（64 位）
4. **System load**：0.08（0-1 健康，> CPU 核数表示卡）
5. **磁盘使用**：11.1% of 39.26G（系统盘 40G，剩 35G）
6. **内存使用**：7%（很闲）
7. **进程数**：125（正常）
8. **内网 IP**：10.1.0.15（公网 IP 是 114.132.83.99）

**面试话术**：
> "我每次连服务器先看 MOTD——5 秒判断服务器健康度。`load` 最重要，0.08 表示基本闲置；`/ ` 用了 11% 表示不会很快满；`memory` 7% 表示没有内存泄漏。这些数字异常能 80% 反映问题。"

## 二、Linux 文件权限（chmod）

**3 组 3 位**：
```
-rw-r--r--  1 user group  size  date  filename
│├─┤├─┤├─┤
│ │  │  │
│ │  │  └── 其他用户 (other)
│ │  └───── 同组用户 (group)
│ └──────── 所有者 (owner)
└────────── 文件类型 (- 普通文件, d 目录, l 链接)
```

**9 个权限位**：
- `r` (read, 4)：读
- `w` (write, 2)：写
- `x` (execute, 1)：执行

**chmod 数字表示**：
```bash
chmod 600 file   # owner 读写，其他人无权限
chmod 644 file   # owner 读写，其他人只读
chmod 755 file   # owner 全部，其他人读+执行
chmod 777 file   # 全部权限（危险！生产禁用）
```

**面试话术**：
> "我有个反直觉的发现：Windows 上 `chmod 600` 后 `ls` 看到的 mode 没变（因为 NTFS 不支持），但 SSH 仍然能工作——这说明 SSH 在 Windows 上不验证 mode。**但生产 Linux 服务器会**——这就是为什么 Docker 镜像、CI 流水线都在 Linux 跑。"

## 三、进程查看（ps / top / htop）

### ps（snapshot 快照）
```bash
ps aux                       # 所有进程（传统 BSD 风格）
ps -ef                       # 所有进程（System V 风格）
ps aux | grep python         # 找 Python 进程
```

**关键列**：
- `USER`：进程所有者
- `PID`：进程 ID
- `%CPU`：CPU 使用率
- `%MEM`：内存使用率
- `COMMAND`：启动命令

### top（实时动态）
```bash
top                         # 实时进程（默认 3 秒刷新）
top -p 1234                 # 监控特定 PID
```

**关键快捷键**（top 内）：
- `P`：按 CPU 排序
- `M`：按内存排序
- `1`：显示每个 CPU 核心
- `q`：退出

### htop（top 的升级版）
```bash
# 安装
sudo apt install htop
htop
```
优势：彩色、可鼠标点击、树状显示父子进程关系。

**面试话术**：
> "我线上排查进程问题的标准流程：`ps aux | grep <keyword>` 找 PID → `top -p <pid>` 看这个进程的资源 → `cat /proc/<pid>/status` 看详细状态。这是 L1 排查能力——99% 的'服务挂了'问题用这三步能定位。"

## 四、网络与端口（ss / netstat）

### ss（取代 netstat 的新工具）
```bash
ss -tulnp                    # 所有监听的 TCP/UDP 端口
ss -tulnp | grep 8000         # 找 8000 端口（FastAPI 默认）
ss -ant                      # 所有 TCP 连接
```

**列解读**：
- `State`：LISTEN（监听）/ ESTABLISHED（已连接）
- `Local Address`：本地 IP:端口
- `Process`：占用进程

### netstat（已废弃但仍广泛使用）
```bash
netstat -tulnp               # 同 ss
netstat -ant                 # 所有连接
```

### 防火墙（ufw）
```bash
sudo ufw status              # 查看防火墙状态
sudo ufw allow 22            # 放行 22 端口（SSH）
sudo ufw allow 8000          # 放行 8000 端口（FastAPI）
sudo ufw enable              # 启用防火墙
```

**FitForge 部署时**：需要 `ufw allow 8000` 让 FastAPI 能被外网访问。

**面试话术**：
> "我部署 FastAPI 时的标准动作：`ss -tulnp` 确认服务在监听 → `ufw allow 8000` 放行端口 → `curl http://localhost:8000/health` 本地自测 → 浏览器访问 `http://公网IP:8000/docs`。少一步都可能'连不上但查不到原因'。"

## 五、服务管理（systemctl）

```bash
systemctl status nginx       # 看 nginx 状态
systemctl start nginx        # 启动
systemctl stop nginx         # 停止
systemctl restart nginx      # 重启
systemctl enable nginx       # 开机自启
systemctl disable nginx      # 取消开机自启
systemctl list-units --type=service --state=running  # 看所有运行中的服务
```

**为什么用 systemctl？**
- 服务异常自动重启
- 开机自启
- 统一日志（`journalctl -u nginx`）

**FitForge 计划**：
- 周六部署时把 FastAPI 注册成 systemd 服务
- `systemctl start fitforge` 启动
- `systemctl status fitforge` 看状态

**面试话术**：
> "我不会用 `nohup` + `&` 跑后台进程（这种'野进程'重启机器就没了），而是用 `systemctl` 注册成系统服务——开机自启、崩溃自动拉起、统一日志。这是把'脚本'变成'服务'的关键。"

## 六、文件查找（find / locate）

### find（实时查找）
```bash
find / -name "*.py"                  # 全盘找 .py 文件
find . -name "main.py"                # 当前目录找
find / -type f -size +100M            # 找大于 100M 的文件
find . -mtime -7                       # 7 天内修改的文件
```

### locate（基于数据库的快速查找）
```bash
sudo apt install mlocate
sudo updatedb                          # 更新数据库（每天自动）
locate main.py                         # 快速找
```

**面试话术**：
> "`find` 实时但慢，`locate` 快但可能过时——我用 `find` 找刚改的文件（精确），用 `locate` 找系统文件（快速）。这是工具选择的'精确性 vs 速度'权衡。"

## 七、文本查看（cat / less / head / tail）

```bash
cat file.log              # 全部输出（小文件用）
less file.log             # 分页查看（大文件用，q 退出）
head -n 20 file.log       # 前 20 行
tail -n 20 file.log       # 后 20 行
tail -f file.log          # 实时跟踪日志（Ctrl+C 退出）
```

**关键场景**：
- `tail -f /var/log/nginx/access.log`：实时看访问日志
- `head -n 5 main.py`：快速看文件前 5 行

**面试话术**：
> "我看日志 90% 用 `tail -f`——实时跟踪，调试 FastAPI 时能立刻看到请求路径和返回码。这是排查 5xx 错误的利器。"

## 八、磁盘与内存（df / du / free）

```bash
df -h                     # 磁盘使用（人类可读格式）
df -h /                   # 看根分区
du -sh /var/log           # 看 /var/log 目录大小
du -sh * | sort -h        # 当前目录所有项大小排序

free -h                   # 内存使用
free -h | grep Mem        # 看物理内存
```

**关键点**：
- `df` 看**整个分区**使用情况
- `du` 看**目录/文件**大小
- `free` 看**内存 + 交换分区**

**面试话术**：
> "我用 `df -h` + `du -sh *` 排查'磁盘满了'问题——前者定位是哪个分区满了，后者定位是哪个目录/文件占空间。常见案例如：日志文件没清理（`/var/log` 几十 G）、Docker 镜像没清理（`/var/lib/docker` 几十 G）。"

## 九、用户与权限（sudo / su / whoami）

```bash
whoami                    # 当前用户
sudo command              # 以 root 权限执行
sudo -i                   # 进入 root shell
su - username             # 切换到其他用户

id                        # 当前用户的 UID/GID
id ubuntu                 # 看 ubuntu 用户的 UID/GID
```

**关键概念**：
- `ubuntu` 是腾讯云默认的 sudo 用户
- `root` 是超级管理员（UID=0）
- `sudo` 让普通用户临时获得 root 权限

**安全原则**：
- **永远不直接用 root 登录**（SSH 配置 `PermitRootLogin no`）
- 用 `sudo` 提权（每条命令独立授权）
- `sudo` 需要 ubuntu 的密码（**不是私钥密码**）

**面试话术**：
> "我线上从来不直接 `su -` 切 root——`sudo` 每条命令都审计，root 切走就不知道谁在干什么。生产环境的'权限最小化'原则：能用普通用户做的事，就别用 root。"

## 十、vim 基础（必须会）

**3 个模式**：
- **普通模式**（默认）：移动光标、删除、复制、粘贴
- **插入模式**（i 进入）：输入文字
- **命令模式**（: 进入）：保存、退出、查找

**最常用命令**：
```bash
i              # 进入插入模式（在光标前）
Esc            # 退到普通模式
:w             # 保存
:q             # 退出
:wq            # 保存并退出
:q!            # 强制退出（不保存）
dd             # 删除整行
yy             # 复制整行
p              # 粘贴
/keyword       # 查找 keyword
n              # 查找下一个
```

**面试话术**：
> "我线上编辑配置的标准流程：`vim file.conf` → `/keyword` 找目标 → `i` 进入编辑模式 → 修改 → `Esc` → `:wq` 保存。这 5 个命令能覆盖 90% 场景——vim 难学但学会后效率高 5 倍。"

## 十一、FitForge 部署会用到什么？

| 任务 | 命令 | 用途 |
|------|------|------|
| 系统更新 | `sudo apt update && sudo apt upgrade -y` | 更新包索引 + 升级 |
| 装 Python | `sudo apt install python3.10 python3-pip python3-venv -y` | 装 Python 环境 |
| 装 MySQL | `sudo apt install mysql-server -y` | 装 MySQL 8.0 |
| 配 MySQL | `sudo mysql_secure_installation` | 设置 root 密码、删测试库 |
| 跑 FastAPI | `uvicorn main:app --host 0.0.0.0 --port 8000` | 启动服务（--host 0.0.0.0 让外网能访问） |
| 后台跑 | `nohup uvicorn ... &` 或注册 systemd 服务 | 退出 SSH 不挂 |
| 开放端口 | `sudo ufw allow 8000` | 让外网访问 |
| 看日志 | `tail -f app.log` | 实时跟踪请求日志 |

**面试话术**：
> "我的部署清单会按这个顺序：① 更新系统 → ② 装依赖 → ③ 配服务 → ④ 跑应用 → ⑤ 开放端口 → ⑥ 验证 → ⑦ 配置开机自启。每一步独立可验证——不会'配完发现中间某步错了'。"

## 十二、一句话总结

> Linux 的核心是**文件**（一切皆文件）+ **权限**（rwx 三组九位）+ **进程**（ps/top/htop）+ **服务**（systemctl）。

把这四件事理解透，Linux 就不再神秘。

---

**参考资源**：
- [Ubuntu 官方文档](https://help.ubuntu.com/)
- [Linux 命令手册](https://man7.org/linux/man-pages/)
- [ExplainShell](https://explainshell.com/)（命令逐段解释）
