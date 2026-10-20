# Context Handoff · 长任务交接

把长任务的有效要求、进度和关键证据保存在项目文件中，换窗口后读取原件继续工作。

适合多轮改稿、长期研究、代码排查和需要跨对话继续的任务。日常只轻量登记；到指定检查点且达到提醒线时，才提醒整理。得到同意后归档，保留原文与历史版本。

## 能做什么

- 按每 10 轮或指定间隔检查已登记的内容规模，避免逐轮摘要打断工作。
- 归档任务目标、有效要求、证据位置、产物和下一步；保存压缩取舍说明。
- 保护交接原件，查看工作副本差异，按用户纠正发布新版本。
- 恢复旧版本前另存当前工作副本，历史记录仍可回查。
- 新对话从项目索引找到交接入口，再读取必要原件。

## 安装

下载仓库 ZIP 并解压，将包含 `SKILL.md` 的目录命名为 `context-handoff`。可以把目录或 GitHub 地址交给 Codex：

> 请安装这个仓库中的 context-handoff，保留脚本和资源文件，并检查是否能调用。

手动安装（在该仓库根目录运行 Windows PowerShell）：

```powershell
$skillHome = Join-Path $env:USERPROFILE '.agents\skills'
$skillTarget = Join-Path $skillHome 'context-handoff'
New-Item -ItemType Directory -Force $skillHome | Out-Null
if (Test-Path -LiteralPath $skillTarget) { throw '已安装同名 Skill，请先备份再更新。' }
Copy-Item -LiteralPath (Get-Location).Path -Destination $skillTarget -Recurse
```

安装后确认 `context-handoff/SKILL.md` 位于 Skill 目录的第一层，再重新打开对话。不要只复制 SKILL.md。其他宿主请使用它实际扫描的 Skill 目录。

macOS / Linux（同样在仓库根目录运行）：

```sh
mkdir -p ~/.agents/skills
test ! -e ~/.agents/skills/context-handoff && cp -R . ~/.agents/skills/context-handoff
```

## 开始使用

在项目中说：

> 启动 context-handoff，每 10 轮检查一次。

提醒线默认 30000 字符，也可以明确选择 30000 个 o200k_base tokens。它是个人整理策略，不代表模型的系统上下文上限。字符计量不需要依赖；token 计量另需 tiktoken。

收到提醒后：

> 好的，请帮我压缩。

随时检查或纠正：

> 检查一下 context-handoff 保存了什么。这里的目标读者应改成工业工程硕士，请保留修订记录。

迁移前：

> 准备换窗口，请检查已经保存的批次和未归档尾部，整理交接入口。

新窗口中给出同一项目或入口文件：

> 使用 context-handoff，读取这个项目的交接记录并继续任务。

## 运行方式

需要 Python 3.10+。这是 AI 执行说明加本地脚本，不是常驻后台。宿主若已经登记计数，助手不能重复计数；未接入时只登记实际可访问的问答和材料。没有宿主事件接口时，不会自动获取完整聊天或禁止系统压缩。

```text
python scripts/session_meter.py --root RECORDS init --every 10 --threshold 30000 --metric characters
python scripts/session_meter.py --root RECORDS status
python scripts/memory_guard.py --root RECORDS inspect
```

完整登记、批准归档命令见 [monitoring.md](references/monitoring.md)；保护、纠正和恢复见 [protected-memory.md](references/protected-memory.md)。脚本计数和校验哈希，AI 负责整理语义。归档批准只覆盖批准时的记录，不会自动覆盖之后新增的尾部。

## 文件与迁移

项目根的 `.context-handoff-index.json` 指向记录目录。记录目录保存 `raw/` 原文、`archives/` 批次、`protected-memory/` 保护版本及项目记忆、压缩说明、handoff.md。

换电脑时连同索引、记录目录和原始材料一起带走，检查入口路径。记录可能包含研究材料及对话内容；对外上传 Skill 时不要把这些个人项目档案一起打包。

## 检查与排错

```sh
python -m unittest discover -s tests -v
```

“Checkpoint not due”表示还没到指定轮数；继续任务即可。“Duplicate key”表示同一登记编号对应的内容变了，应核对来源，不要覆盖原文。保护哈希不匹配时检查具体损坏及历史快照；不要把损坏文件重新当作已确认版本。

计量脚本使用单进程串行写入；同一个记录目录不要由多个助手同时写。查看和纠正不推进任务轮数；用户未同意归档时照常工作。
