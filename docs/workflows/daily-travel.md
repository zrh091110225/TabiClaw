# 每日旅行工作流

用于让阿虾向前旅行一天，并生成当天游记和图片。

## 先读

- `data/journals/index.md`：确认当前城市、天数、余额。
- `data/status.json`：确认机器状态。
- `data/route.md`：确认下一站是否存在。
- `config/settings.yaml`：确认模型、工具路径和 Git 行为。

## 执行

```bash
bash scripts/daily_workflow.sh
```

指定日期执行：

```bash
bash scripts/daily_workflow.sh YYYY-MM-DD
```

## 会修改什么

- `data/status.json`
- `data/route.md`
- `data/journals/index.md`
- `data/journals/YYYY-MM-DD-城市.md`
- `data/images/`
- `data/output/`
- 可能产生 Git commit 和 push

## 验证

执行后检查：

- `data/journals/index.md` 顶部状态是否更新。
- `data/status.json` 是否是合法 JSON。
- 新游记和图片路径是否存在。
- `data/route.md` 是否裁掉已完成节点。
- 如果自动提交开启，检查 Git 历史是否出现当天提交。

## 注意事项

- 查看状态时不要运行此脚本。
- 如果外部路线、天气、景点工具缺失，先修复依赖，不要手写假数据。
- 如果用户没有要求自动推进旅行，不要主动执行。

