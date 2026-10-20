# 交接原件保护与用户修订

用户常用指令：

- “检查一下context-handoff当前压缩的对话”：展示已有内容，不重新压缩。
- “这里读者应当是工业工程硕士，改一下记录”：更新该要求及来源，保留原版本。
- “恢复上一版交接记录”：展示将恢复的版本与影响；用户已明确指明版本时直接恢复该版本。

## 保存保护版本

ROOT为当前会话记录目录。初次归档完成后保护项目记忆与本批压缩说明；迁移时加入交接入口。路径相对于ROOT，文件名沿用实际项目命名。

```text
python scripts/memory_guard.py --root ROOT publish --files project-memory.md compression-notes.md handoff.md --instruction 用户归档批准原文.txt --basis archive-approval
```

只列已生成的文件，尚无handoff.md时不填该项。每次发布保存完整的当前交接文件集合；新批次说明替代旧批次说明成为当前入口，历史批次仍在原档案及保护版本中。保护副本与逐版清单保存在protected-memory/revision-XXXXX，current.json记录当前版本与清单哈希。单进程串行操作。

## 随时查看

```text
python scripts/memory_guard.py --root ROOT inspect
```

输出当前版本、修改依据、逐文件原文、变更差异以及工作副本是否与保护版本一致。查看不修改任何文件，不触发计数检查点或归档。原件或清单哈希不匹配时先报告具体损坏，回查归档快照，不能自动接受被改写的内容。

助手把实际内容整理成便于用户核对的说明，给出原文件链接。要明确哪些材料只保留了关键点，原文在哪；不能把未保留内容说成已经完整记住。用户提出的纠正可直接执行，普通查看本身不代表确认所有字段。

## 纠正与恢复

按用户明确的纠正修改对应工作文件及交接入口，检查相关字段一致，然后发布完整当前文件集合：

```text
python scripts/memory_guard.py --root ROOT publish --files project-memory.md compression-notes.md handoff.md --instruction 用户纠正原文.txt --basis user-correction
```

脚本保存用户原话与逐文件改前/改后差异，旧版本不覆盖。用户纠正的事实或要求优先于旧摘要；涉及论文结论的纠正同时保存可定位来源，无法判定的冲突保留为未决。用户明确确认某版后，可用同样publish命令及--basis user-confirmation记录确认，归档批准不等于逐项事实确认。

```text
python scripts/memory_guard.py --root ROOT restore --revision 1 --instruction 用户恢复原文.txt
```

restore将指定历史保护版本中的文件恢复到工作位置，并创建一个新版本记录本次恢复；原修订历史保留。此前工作位置若有未发布的新修改，先保存到独立备份并说明将被替换的内容，避免丢掉未归档工作。旧版本没有包含的其他文件不会被删除，不再列为当前依据。

## 后续对话优化

助手主动整理上下文时，对保护信息引用原件路径与版本，保留其内容及有效性。只合并新增记录，不把已确认要求重新概括成更短或含糊的说法。宿主自动压缩若没有暴露控制接口，无法直接禁止其改写聊天；本地原件仍可在接续或发现遗漏时读取。没有事件钩子时，这套流程不在后台自行运行。
