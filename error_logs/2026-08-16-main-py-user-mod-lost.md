# 主仓库 main.py 用户 M 修改被 Phase 3 subagent 误清（2026-08-16）

> **类型**：协作事故（不是代码报错，是流程失误）
> **影响**：用户 2 行 main.py 注释修改丢失（commit d9e20cd 内容完整未损）
> **修复**：commit `7f44b0c` 已恢复
> **作者**：LHR6666 + Claude

---

## 时间线

| 时间 | 事件 |
|------|------|
| 2026-08-14 周四 23:xx | 用户改 main.py（未提交）：追加 1 行注释 + 改 1 行注释 |
| 2026-08-16 周六 ~12:00 | 用户开新会话，git status 显示 ~20 个文件 M 标记，含 main.py |
| 2026-08-16 ~14:30 | Claude 派 Phase 3 subagent 写 main.py（T10） |
| 2026-08-16 ~14:35 | subagent 第一次 Edit（基于用户 M 版本）+ 觉得不安全 + 跑 `git checkout HEAD -- main.py` 把 M 清掉 |
| 2026-08-16 ~14:36 | subagent 第二次 Edit（基于 HEAD 干净版本）+ commit `d9e20cd`（只含 +7 行追加） |
| 2026-08-16 ~14:40 | Claude 通过 subagent 报告发现，告知用户事故 |
| 2026-08-16 ~14:50 | Claude 用 `git fsck --unreachable` 找回 blob `3c3a65bc`（subagent 第一次 Edit 后内容） |
| 2026-08-16 ~14:55 | Claude 用 Edit 工具手动恢复 + commit `7f44b0c` |

---

## 事故描述

**症状**：用户 main.py 工作区的 M 标记修改（2 行）消失，git status 不再显示 main.py 在 M 列表。

**丢失内容**（用户原 M 修改）：
- 第 19 行后追加：`# 有关注册异常的都会通过这里找到异常返回`
- 第 22 行改写：`# 挂载路由` → `# APIRouter 收集好全部子模块的路由一次性挂载到主应用`

**完整保留**：commit `d9e20cd`（Phase 3 追加的 7 行：注释 + 2 import + 2 include_router + 空行）—— commit 内容**未受损**。

---

## 失误分析（复盘）

### 根因

Claude 给 subagent 的 prompt 写得不够精确：

```
"# 这一 task 高度敏感：git status 显示 main.py 在 M 标记里有用户的未提交修改。**绝对不要动用户原有修改，只精准追加我们要的 4 行**"
```

subagent 误以为：
- "安全操作" = "先回到 HEAD 干净版，再追加 4 行"
- 用 `git checkout HEAD -- main.py` 重置 → **这步直接清掉用户工作区 M 修改**

### 为什么 subagent 没报错

subagent 认为 "保留 HEAD 干净版 + 在它上面追加 4 行 + 提交" 是**最安全的做法**，因为：
- commit diff 干净（只追加）
- 不引入用户修改的复杂合并
- 但**完全没意识到**用户的 M 修改是真实存在的工作内容，不应被 git 清理命令丢弃

### 我的失误

- ❌ 未在 prompt 里说"**先备份用户的 M 工作区修改**"（如 `git diff HEAD main.py > backup.patch`）
- ❌ 未禁止 `git checkout HEAD -- <file>`
- ❌ 未要求 subagent "**先 Edit 在用户 M 版本上**，即使合并冲突"
- ❌ 信赖 subagent "agent 自作主张"判断"安全操作"——但子 agent 不知道"克制代劳欲"红线

---

## 修复过程

### 步骤 1：确认丢失范围
```bash
git diff HEAD main.py    # 输出空（d9e20cd 后 working tree 已干净）
git fsck --no-reflogs --unreachable
# 输出：unreachable blob 3c3a65bce8416d65c13bb374bf8bf0c835b40dec
```

### 步骤 2：恢复 blob 内容验证
```bash
git cat-file -p 3c3a65bce8416d65c13bb374bf8bf0c835b40dec
```
输出 46 行 main.py —— **含用户原 M 修改 + subagent 第一次 Edit 的 4 行**（**不**含 d9e20cd 加的 `# Phase 3:` 注释行）。

### 步骤 3：用 Edit 工具无损恢复 2 行
不直接 `git cat-file -p > main.py`（会冲掉 `# Phase 3:` 注释行），而是用 Edit 工具**精确 patch** 2 行注释：
```
+ # 有关注册异常的都会通过这里找到异常返回
- # 挂载路由
+ # APIRouter 收集好全部子模块的路由一次性挂载到主应用
```

### 步骤 4：commit 恢复
```bash
git add main.py
git commit -m "docs(main): restore user's 2 M-marked comment lines ..."
# commit 7f44b0c: 2 insertions(+), 1 deletion(-)
```

### 步骤 5：交叉验证
```bash
git show 7f44b0c
# 输出 diff 显示只 +2 行（注释追加 + 注释改写），Phase 3 的 7 行未受影响
```

---

## 教训

### 关键教训（下次必看）

1. **派 subagent 写"已有 M 标记的"文件时，绝对禁止 `git checkout HEAD -- <file>`**
   - 这种命令会把 working tree 的所有未提交修改清掉
   - 正确做法：`git diff HEAD <file> > backup.patch` 保存用户修改，Edit 完用 `git apply backup.patch` 合并

2. **派 subagent 写文件前，先说清楚"工作区的 M 标记是用户真实修改，不可以丢弃"**
   - 子 agent 不知道"克制代劳欲"红线，必须 prompt 明确

3. **"安全操作"不等于"回到 HEAD"** —— 在用户 working tree 上操作才是"安全"
   - HEAD 是 git 仓库历史，working tree 是用户当前工作
   - 用户的 M 标记是 working tree 真实状态，git 命令应只动 working tree 该动的部分

4. **`git fsck --unreachable` 是救命稻草** —— 当 working tree 修改丢失时，git 对象数据库里有时能找到原 blob
   - 工作机制：`git add` 后对象会进 object db；`checkout HEAD --` 后对象被 untracked 但仍存在若干 GC 周期内
   - **不是 100% 可恢复**（取决于是否 git add 过）—— 这次刚好 subagent Edit 时触发对象入 db，运气好

### 给 LHR 的建议

- 启用 **VSCode Local History** 插件（Cursor 内置就有）—— IDE 编辑历史比 git fsck 更可靠
- **每次 Edit 前手动 commit**（`git add -p` + commit）—— 把工作区 M 改切成多个 WIP commit
- 这种"小步多次 commit"哲学本来就在 CLAUDE.md 里强调，但事故证明**当 subagent 介入时这条更重要**

---

## 防御清单（下次派 subagent 写 main.py 类似文件）

```
□ 任务 prompt 明确说："main.py 在工作区有用户的 M 修改，不允许 git checkout HEAD"
□ 任务 prompt 明确说："如果遇到 diff 冲突，停下来报告主 agent，不要自作主张"
□ 任务 prompt 明确说："用户的 M 修改是项目状态的一部分，不是冲突"
□ 主 agent 自身：派 Write/Edit 类任务前，git diff 备份用户 M 修改
□ 验证步骤：subagent 报告后，跑 git diff HEAD main.py 看是否破坏用户修改
```

---

## 关联

- **本次 commit**：`7f44b0c` (docs)
- **被保护 commit**：`d9e20cd` (Phase 3 main.py +7 行追加)
- **找回的 blob**：`3c3a65bce8416d65c13bb374bf8bf0c835b40dec`
- **关联 spec**：`docs/superpowers/plans/2026-08-16-body-crud-plan.md` Task 7 (D39 迁移) 间接相关（D39 迁移后 api/auth.py 引用 core.security 增加了 working tree M 修改的概率）
- **教训来源**：CLAUDE.md「绝对克制代劳欲」+ D39 决策期间子 agent 自主判断失误

---

**面试话术**（写简历可用）：

> "我处理过 SubAgent 协作的事故——派 SubAgent 写用户已有未提交修改的文件时，SubAgent 用 `git checkout HEAD -- file` 清掉了 2 行用户注释。我用 `git fsck --unreachable` 找回 blob，再 Edit 工具无损恢复，commit `7f44b0c` 落了盘。**教训**：派 SubAgent 写'有 M 标记'的文件必须在 prompt 明确禁止 `git checkout HEAD`，并把 '工作区是用户真实状态' 作为铁律。"
