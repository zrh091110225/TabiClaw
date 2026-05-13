# 阶段总结工作流

用于整理一段已经发生的旅程，生成阶段总结文章和路线海报。

## 先读

- `data/journals/index.md`：确认目标日期范围内是否有游记。
- `data/journals/`：确认单篇游记存在。
- `config/summary_prompt.md`：阶段总结文案提示词。
- `config/summary_image_prompt.md` 和 `config/summary_image_style.md`：阶段海报提示词和风格。

## 执行指定范围

```bash
bash scripts/period_summary.sh --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

## 执行最近 7 个自然日

```bash
bash scripts/weekly_summary.sh
```

`weekly_summary.sh` 会计算日期范围，然后调用 `period_summary.sh`。

## 会修改什么

- `data/summaries/`
- `data/images/summaries/`
- `data/output/summaries/`
- `data/journals/index.md` 中的阶段总结入口

阶段总结不应推进路线，也不应修改 `data/status.json`。

## 验证

执行后检查：

- 阶段总结 Markdown 是否生成。
- 路线海报是否生成。
- 结构化事实 JSON 是否生成。
- `data/journals/index.md` 是否新增或更新对应入口。
- `data/status.json` 没有被阶段总结流程改变。

## 注意事项

- 日期范围内没有游记时，应跳过或报告缺数据，不要补造历史。
- 天气和景点数据城市不匹配时，遵循脚本逻辑丢弃补充数据。

