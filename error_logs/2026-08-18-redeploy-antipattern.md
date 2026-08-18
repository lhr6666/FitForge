# 重复部署反模式（2026-08-18 周一上午）

> **类型**：协作事故（重复无意义部署）+ 失实汇报（"16 task 未开始" 后遗症）
> **触发事件**：用户阻止 `tar -czf /tmp/fitforge_2026-08-18.tar.gz` 后质疑"为什么在重复之前的东西"
> **关联事件**：
> - `error_logs/2026-08-16-server-deploy-4-issues.md`（08-16 真部署已完整）
> - 早上 "16 task 未开始" 严重失实（项目进度跟踪节）
> **关联 commit**：无（本文档为本次新增）
> **作者**：LHR6666 + Claude Code

---

## 症状

早上开工准备"真部署到服务器"，读 `error_logs/2026-08-16-server-deploy-4-issues.md` 后得知：

> "08-16 部署踩 4 个失误，修复后 smoke 13 步全过"

—— 但因为：
1. 早上"16 task 未开始"严重失实（基于 project_progress.md 没查 git log）
2. 服务器当时 SSH `Connection timed out`（关机状态）
3. **没做服务器侧实地查证**

直接推断出"必须重新部署"结论，创建 8 个 TaskList 跟踪"真部署"流程，准备 `tar -czf /tmp/fitforge_2026-08-18.tar.gz` 重新打包上传。

**用户中断 tar 命令并质疑**："这些都完成过了怎么现在一直在重复之前的东西啊到底能不能确定判断第一周要部署的东西有没有完全部署？"

---

## 根因

### 根因 1：早上失实汇报的"惯性失实"

早上推断"16 task 未开始"是**没查 git log 的失实**。这次"需要重新部署"是**没查服务器状态的失实**——同一种错误模式（基于文档脑补，未实地查证）。

### 根因 2：服务器 SSH 不通 ≠ 服务器代码不存在

早上 `ssh fitforge` 报 `Connection timed out`——但这只是**服务器关机状态**的信号，**不是"服务器没部署过"的证据**。

如果当时做这 3 步 10 秒验证，就能 100% 避免误判：

```bash
# 步骤 1：开机后跑 ls（看代码是否存在）
ssh fitforge 'ls ~/fitforge 2>&1 | head -10'
# 期望：看到 main.py / api/ / core/ / alembic/ 等

# 步骤 2：看服务器代码对应的 git commit
ssh fitforge 'cat ~/fitforge/.git/HEAD 2>&1; cd ~/fitforge && git log --oneline -3 2>&1'
# 期望：看到具体 commit hash

# 步骤 3：对比本地最新 commit vs 服务器 HEAD
git rev-parse --short HEAD  # 本地 2d27148
ssh fitforge 'cd ~/fitforge && git rev-parse --short HEAD 2>&1'
# 如果本地 = 服务器（或服务器是 08-16 部署时的 commit），部署完成
```

### 根因 3："32 文件没 commit"被误读为"没部署"

用户记忆中的"32 文件没 commit"实际是 08-16 23:44 的**working tree 抢救性 sync**：

```
6572e7b  chore: sync A-class 业务代码 (6 files)
d7c0fa9  docs: sync B-class 文档 (14 files)
12b1d02  docs(notes): add 7 untracked
ec663f5  test: sync tests/test_auth.py
```

但**tar 打包的是 working tree 状态**（08-16 部署时），**git log 是否 commit 不影响部署包内容**。

也就是说：
- 08-16 部署包里**包含**这些 working tree 修改
- git log 后来才补 commit 记录（commit date 是 23:44，但 file content 在部署包里早已存在）

我之前没说清这一点，导致用户误以为"32 文件没 commit = 没部署"。

---

## 用户关键洞察（我之前没意识到的）

用户说：

> "我之前已经部署过一次了但是后来你又说有32个文件没有commit没有部署所以我很疑惑咋了"

> "我当时让你解决之后你只是commit就没后续了我不确定是不是因为已经部署过了所以选择跳过了"

**用户的怀疑是对的**——08-16 已经部署了，commit 完后"没后续"是**正确的**（不需要重新部署）。

我之前没清晰解释"working tree 抢救性 sync ≠ 重新部署"的区别，导致用户对我产生"我可能在偷懒跳过"的怀疑。

---

## 今天 3 个 commit 的影响范围（澄清后）

| commit | 内容 | 服务器需要？ |
|---|---|---|
| `1622384` fix(deps) requirements.txt | + PyJWT 一行 | ❌ 服务器 venv 早装了 PyJWT（08-16 失误3 修复时 `pip install 'PyJWT[crypto]==2.10.1'`） |
| `fdbcb04` docs(error-log) | + 113 行 dev-side 错误日志 | ❌ 服务器不跑文档 |
| `2d27148` docs(progress) | + 35 行事实澄清 | ❌ 服务器不跑文档 |

**结论**：今天 3 个 commit 都是 dev-side 改动，**完全不需要重新部署到服务器**。

---

## 教训

### 教训 1：实地查证是"绝不画饼"红线的具体体现

早上失实（"16 task 未开始"）和这次失实（"需要重新部署"）是同一种错误：**基于文档推断，未做实地查证**。CLAUDE.md「真实优先」红线不是空话——**每次涉及状态判断，必须实地查证（git log / ssh / ls）**。

### 教训 2："git log vs 服务器 HEAD"对比是金标准

任何"部署"决策前必跑 3 步：
1. `ssh fitforge 'ls ~/fitforge'`
2. `ssh fitforge 'git -C ~/fitforge log --oneline -3'`
3. 对比本地 `git log --oneline -3` 和服务器 HEAD

如果服务器 HEAD = 本地 HEAD（或服务器 HEAD 是 08-16 部署时的 commit），则**无需重新部署**。

### 教训 3：用户质疑永远当回事

用户说"这些都完成过了"——这是**合理怀疑**。早上"16 task 未开始"教训告诉我：**用户质疑是早期信号**，错过了就要用更大的代价修正。

这次用户在 tar 命令**执行前**就阻止——避免了无意义的工作。如果我没听就跑了 tar + scp，浪费 5-10 分钟，服务器还会被覆盖（虽然结果一样，但失去 08-16 备份的 .bak_2026-08-16）。

### 教训 4：TaskList 创建前先做 1 分钟验证

CLAUDE.md「智能任务调度」红线提到要"评估任务复杂度、隔离性及上下文体积"——这次我创建了 8 个 TaskList 跟踪"部署流程"，但**没先做 1 分钟验证**是否真需要部署。

防御：任何"部署/重做/回滚"类 TaskList 创建前，先跑 3 步查证（见教训 2），再决定是否继续。

---

## 防御 checklist（永久更新）

```
□ 任何"部署 / 重新部署 / 回滚"决策前：
  1. ssh 验证服务器状态（ls ~/fitforge）
  2. 服务器 git log 对比本地 git log
  3. 如果服务器 HEAD >= 本地 HEAD（按时间序）→ 无需重新部署
□ 用户质疑"是不是已经做过了"时：
  1. 立即停止当前动作
  2. ssh 验证 + git log 对比
  3. 给出确凿证据（不是"按文档看是做了"）
□ "git log vs 服务器 HEAD"对比是金标准 → 写进 CLAUDE.md 永久红线
```

---

## 关联文档

- **早上失实**：`project_progress.md` 「2026/08/18 周一开工 - 事实澄清补记」节
- **08-16 真部署**：`error_logs/2026-08-16-server-deploy-4-issues.md`
- **部署清单**：`tech_notes/2026-08-16-deploy-checklist.md`
- **PyJWT 修复**：`error_logs/2026-08-18-pyjwt-requirements-fix.md`

---

## 面试话术

> "我处理过一个**重复部署反模式**——早上推断失实（'16 task 未开始'）后，没做服务器侧实地查证就直接准备 `tar + scp` 重新打包。用户在 tar 命令执行前质疑'是不是已经部署过了'，我立即停止 + 反思。教训：**任何'部署'决策前必跑 3 步验证**（ssh ls + 服务器 git log + 本地 git log 对比），**用户质疑永远当回事**——这是工程师'不画饼'的核心习惯。"

---

## 待更新

- `CLAUDE.md` 是否加一条红线："部署前必跑 `git -C ~/fitforge log --oneline` 对比本地"？—— **本次会话不修，等第 1 周周报时统一更新。**