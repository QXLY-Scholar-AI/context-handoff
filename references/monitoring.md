# 计量与定点检查

ROOT为本会话记录目录，SCRIPT为scripts/session_meter.py。Python3.10+。字符计数无第三方依赖；选o200k_base时需已有tiktoken，缺失则提示，不自动安装。

```text
python SCRIPT --root ROOT init --every 10 --threshold 30000 --metric characters
python SCRIPT --root ROOT record-turn --user-file 本轮用户原文.txt --assistant-file 本轮可见答复.md --key 01
```

record-turn只做本地计数、原文副本和哈希，返回completed_rounds与checkpoint_due。宿主/调度器已经登记时，助手不要重复执行。原文是已有文本，不为登记再让模型生成“本轮总结”。一次任务问答才增加任务轮数；控制回合用`--kind control`，仍统计长度。

材料实际读取后可用`record --role material --file 实际材料.txt --key material-唯一标识`登记，不触发模型整理。同次读取不重复登记；需要回读片段时保存实际片段，不把局部当整篇。首次完整原文未提供时标明范围。

```text
python SCRIPT --root ROOT checkpoint
```

未到间隔时checkpoint报错，不提前触发。到点后，返回的checkpoint_report保存检查当时的规模和archive_suggested；检查本身只写数值日志，不生成项目摘要或交接。archive_suggested同时要求“间隔已到”和“规模达线”。一次长文输入超过提醒线也不单独提前触发。

默认阈值30000字符；显式选择`--metric o200k_base --threshold 30000`可用统一分词器计token。阈值是项目策略，不是模型压缩点。不得中途混换单位。批准/状态消息虽不增加任务轮数，仍计入文本规模。

用户同意之后：

```text
python SCRIPT --root ROOT approve --file 用户批准原文.txt
python SCRIPT --root ROOT archive --memory 项目记忆.md --explanation 压缩说明.md
```

“好的，请帮我压缩”直接通过；其他明确同意措辞加`--explicit-consent`并保留原文。该标志是调用者对用户意图的判断，不是脚本自动理解授权。用户暂缓时只跳过归档，不能停止正常问答。

raw/和events.jsonl保留明确登记的文本及来源；archives/保存逐批快照；state.json仅计数与范围；checkpoints.jsonl仅数值检查。普通轮次不重写project-memory.md或handoff.md。迁移前明确检查属于用户主动操作，不要求等待下一间隔，但新增归档仍需同意。

索引例：`{"sessions":{"A":"项目相对记录目录"},"active":"A"}`。只定位本项目。脚本单进程串行写同一ROOT，不是后台钩子或原生弹窗；未接宿主事件不得声称自动监控已实现。
