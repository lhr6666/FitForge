# Git 常用命令复盘

> 2026/07/01 周一任务产出
> 目标：把 Git 核心命令、底层原理、面试常见考点系统梳理一遍

## 一、配置层（每个项目必做）

```bash
# 全局配置（影响所有仓库）
git config --global user.name "lhr6666"
git config --global user.email "1274810842@qq.com"
git config --global init.defaultBranch main  # 默认分支名

# 项目级配置（只影响当前仓库，优先级高于 global）
cd FitForge
git config user.name "lhr6666"
git config user.email "1274810842@qq.com"
```

**底层原理**：Git 配置有 3 个层级：
1. **系统级**：`/etc/gitconfig`（影响所有用户）
2. **全局级**：`~/.gitconfig`（影响当前用户所有仓库）
3. **仓库级**：`FitForge/.git/config`（只影响当前仓库）

优先级：**仓库 > 全局 > 系统**。这与大多数配置加载顺序一致。

**面试考点**：
> "我在 FitForge 用了仓库级配置（`git config user.name`，不带 `--global`），因为这台电脑还有其他项目（如 pomodoro），每个项目用不同身份提交更安全——比如开源项目用个人邮箱，公司项目用公司邮箱。"

## 二、核心工作流（5 个最常用命令）

```bash
# 1. 初始化 / 克隆
git init -b main                # 新建仓库并指定默认分支
git clone <url>                 # 克隆远程仓库

# 2. 查看状态
git status                      # 查看工作区状态
git status -sb                  # 短格式 + 分支追踪信息

# 3. 暂存与提交
git add <file>                  # 暂存指定文件
git add .                       # 暂存所有变更
git commit -m "message"         # 提交到本地仓库
git commit -am "message"        # add + commit 一步（仅对 tracked 文件）

# 4. 推送与拉取
git push -u origin main         # 首次推送 + 设置上游
git push                        # 后续推送
git pull                        # 拉取并合并

# 5. 查看历史
git log                         # 详细历史
git log --oneline               # 简洁历史（每条一行）
git log --graph --oneline       # 图形化分支历史
git show <commit>               # 查看某个 commit 的改动
```

## 三、暂存区（Index）的本质

Git 与其他 VCS（如 SVN）最大的区别是**多了一个暂存区**：

```
工作区（Working Directory）
    ↓ git add
暂存区（Index / Staging Area）
    ↓ git commit
本地仓库（Local Repository）
    ↓ git push
远程仓库（Remote Repository）
```

**为什么要分暂存区？**
- **精准提交**：可以只暂存部分文件（多个文件改了 5 处，只想提交 3 处）
- **检查预览**：`git diff --cached` 看暂存区内容，确认无误再 commit
- **回滚灵活**：`git restore --staged <file>` 把文件从暂存区退回工作区

**面试考点**：
> "我每次 commit 前都会 `git status` + `git diff --cached` 检查暂存区内容——这是从'提交了不该提交的文件'事故里学到的。有一次我把 .env 误提交到 GitHub，攻击者 1 小时就拿到数据库连接信息。从此我养成了 add 前必看的习惯。"

## 四、文件状态机

Git 文件有 4 种状态（在 `git status` 里能看到）：

| 状态 | 含义 | 例子 |
|------|------|------|
| Untracked | 未跟踪 | 新建的文件，Git 不知道它存在 |
| Modified | 已修改 | 跟踪过的文件，工作区内容变了 |
| Staged | 已暂存 | 改动用 `git add` 加入了暂存区 |
| Unmodified | 未修改 | 跟踪过的文件，工作区 = 仓库 |

状态转移：

```
新建文件 ──git add──> Staged
                    ↓
              git commit
                    ↓
              Unmodified
                    ↓
              修改文件
                    ↓
              Modified ──git add──> Staged
```

**面试考点**：
> "我建 FitForge 时第一次 `git add .` 后，git status 显示有些文件是 'A'（Added 即将提交），有些是 'Ignored'（被 .gitignore 排除）——这就是 4 状态的实际体现。"

## 五、.gitignore 的匹配规则

```gitignore
# 注释以 # 开头
*.log           # 通配符：所有 .log 文件
/secret.env     # 绝对路径：仅根目录的 secret.env
logs/           # 目录：所有 logs/ 目录
**/tmp/         # 任意层级的 tmp/ 目录
!important.log  # 否定：排除规则的反义
```

**6 条核心规则**：
1. `*` 匹配除 `/` 外的任意字符
2. `?` 匹配单个字符
3. `[abc]` 匹配字符集
4. `**` 跨目录匹配
5. `/` 开头表示锚定到 .gitignore 所在目录
6. `!` 开头表示"不忽略"（覆盖前面的规则）

**面试考点**：
> "我在 FitForge 的 .gitignore 里加了两个关键规则：① `keys/` 整目录排除（保护 RSA 私钥）；② `*.docx` 排除（保护云服务器笔记）。这两个规则一旦写错，敏感文件就会被推到 GitHub——所以我会在 commit 前用 `git status --ignored` 验证忽略规则生效。"

## 六、5 个最常被问的 Git 场景

### 场景 1：commit 写错了怎么改？

```bash
# 改最近一次 commit 的 message（未推送）
git commit --amend -m "new message"

# 改最近一次 commit 的内容（加新文件 / 删除文件）
git add forgotten-file
git commit --amend
```

⚠️ **警告**：如果 commit 已经推送到远程，amend 会**改写历史**，团队其他人的本地仓库会冲突。生产环境慎用。

### 场景 2：想撤销工作区的修改

```bash
# 撤销单个文件的修改（危险！未暂存的修改会丢失）
git restore <file>

# 撤销所有工作区修改
git restore .

# 把已暂存的文件退回到工作区（不丢修改）
git restore --staged <file>
```

### 场景 3：merge 冲突怎么解决？（周日下午演练）

```bash
# 1. 制造冲突
git checkout -b feature
# 在 main.py 加一行：print("feature")
git commit -am "feature change"
git checkout main
# 在 main.py 加一行：print("main")
git commit -am "main change"
git merge feature
# 出现冲突！

# 2. 查看冲突文件
git status
# both modified: main.py

# 3. 编辑 main.py，手动解决冲突
# <<<<<<< HEAD
# print("main")
# =======
# print("feature")
# >>>>>>> feature
# 选择保留哪个，或都保留，删除冲突标记

# 4. 完成 merge
git add main.py
git commit -m "merge: resolve conflict"
```

**面试考点**：
> "我周日下午会专门演练一次 merge 冲突——手动改冲突文件、add、commit。这是从'听说 merge 冲突可怕'到'亲手解决过'的跨越。"

### 场景 4：想把某个老 commit 拿回来

```bash
# 1. 找到目标 commit
git log --oneline
# abc1234 old commit
# def5678 newer commit

# 2. 创建一个新 commit 反向应用（推荐，保留历史）
git revert abc1234

# 3. 或直接回到那个状态（危险，改写历史）
git reset --hard abc1234
```

### 场景 5：不小心把敏感文件推到了远程

```bash
# 1. 立刻从远程仓库删除（保留本地）
git rm --cached <file>
git commit -m "remove sensitive file"
git push

# 2. ⚠️ 关键：历史 commit 里仍有该文件！
# 必须用 git filter-branch 或 BFG Repo-Cleaner 重写历史
# 3. 如果文件含密码/密钥，**立刻轮换密钥**（GitHub 历史无法真正删除）
```

**面试考点**：
> "我会先 `git status --ignored` 检查 .gitignore 规则生效，再加上 `git diff --cached --name-only | grep -E '\.env$|\.pem$'` 二次扫描——这是'纵深防御'思想在 Git 中的应用。"

## 七、FitForge 周一实操记录

### 1. 父 monorepo 嵌套问题

发现 `D:/My Agnet/my_coding_projects/` 已经是 git 仓库跟踪多个项目（pomodoro 等），FitForge 子目录不能直接 `git init`。

**解法**：在子目录内 `git init` 形成**嵌套 git 仓库**（gitlink 形式），父 monorepo 不会跟踪子目录内部文件。

**面试讲解**：
> "我遇到了 monorepo 嵌套仓库的场景——父 monorepo 跟踪多个项目，子项目又想作为独立仓库。这种场景下 `git submodule` 是更工程化的方案，但第一周用裸嵌套仓库够用，复杂度更低。"

### 2. .docx 笔记误差点

`git status` 时发现 `云服务器相关知识与注意事项.docx` 在 untracked 列表——文件名暗示含敏感信息。**立刻**加入 .gitignore 排除。

**教训**：第一次 `git add .` 前，**永远先 `git status --ignored` 看一下会被跟踪的所有文件**。

## 八、一句话总结

> Git 的核心是**三个区**（工作区 / 暂存区 / 仓库） + **四个状态**（Untracked / Modified / Staged / Unmodified） + **三类对象**（blob / tree / commit）。

把这三组概念理解透，Git 就不再是黑盒。

---

**参考资源**：
- [Pro Git（免费电子书）](https://git-scm.com/book/zh/v2)
- [Conventional Commits 规范](https://www.conventionalcommits.org/zh-hans/)
- [Oh Shit, Git!?!（救命手册）](https://ohshitgit.com/)
