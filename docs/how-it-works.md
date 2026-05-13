# TabiClaw 如何运作

这个项目把一次旅行拆成了可重复执行的日常工作流。每运行一次 `bash scripts/daily_workflow.sh`，阿虾就向前推进一天，并把结果写回仓库。

## 运行机制

每日工作流的主入口是 [`scripts/daily_workflow.sh`](../scripts/daily_workflow.sh)。

它会按顺序完成这些事情：

1. 读取当前状态 [`data/status.json`](../data/status.json)
2. 从 [`data/route.md`](../data/route.md) 找到下一站
3. 查询路线价格、景点和天气
4. 生成当天游记
5. 生成当天配图
6. 回写新的状态、路线和索引
7. 更新 `data/journals/index.md` 顶部状态区
8. 自动提交到 Git

## 阶段总结机制

除了日更流程，项目现在还支持对一个时间范围内已经发生的旅程做阶段总结。

入口脚本是 [`scripts/period_summary.sh`](../scripts/period_summary.sh)。

如果只想生成“以今天为结束日、最近 7 个自然日”的周总结，可以直接运行 [`scripts/weekly_summary.sh`](../scripts/weekly_summary.sh)。它会先自动计算 `start-date` 和 `end-date`，再底层调用 [`scripts/period_summary.sh`](../scripts/period_summary.sh)。

它会按顺序完成这些事情：

1. 从 [`data/journals/index.md`](../data/journals/index.md) 和单篇游记中抽取指定时间范围的事实
2. 读取同日期的景点和天气补充数据，并在城市不匹配时自动丢弃
3. 生成一篇阶段总结 Markdown
4. 生成一张卷轴式风格化路线海报
5. 在 [`data/journals/index.md`](../data/journals/index.md) 里更新“阶段总结”入口

## 主要数据文件

- [`data/status.json`](../data/status.json)：当前天数、当前城市、余额、最后更新时间
- [`data/route.md`](../data/route.md)：当前剩余路线，阿虾往前走后会裁掉已完成的节点
- [`data/journals/index.md`](../data/journals/index.md)：游记总索引
- [`data/journals/`](../data/journals/)：每天一篇游记
- [`data/summaries/`](../data/summaries/)：阶段总结文章
- [`data/images/`](../data/images/)：每天一张图
- [`data/images/summaries/`](../data/images/summaries/)：阶段路线海报
- [`data/logs/`](../data/logs/)：工作流日志和报错日志
- [`data/output/`](../data/output/)：路线、天气、景点、图片提示词等中间产物

## 脚本入口

- [`scripts/init.sh`](../scripts/init.sh)：检查配置和运行时文件是否齐全
- [`scripts/daily_workflow.sh`](../scripts/daily_workflow.sh)：执行阿虾的一整天
- [`scripts/period_summary.sh`](../scripts/period_summary.sh)：生成一个时间范围内的阶段总结
- [`scripts/weekly_summary.sh`](../scripts/weekly_summary.sh)：生成最近 7 个自然日（含今天）的周总结
- [`scripts/replan_route.sh`](../scripts/replan_route.sh)：从起点到终点重新规划路线
- [`scripts/continue_route.sh`](../scripts/continue_route.sh)：从当前路线末尾继续追加后续目的地
- [`scripts/auto_commit.sh`](../scripts/auto_commit.sh)：在工作流结束后自动提交 Git

## 配置来源

项目的配置主要分三层：

- 人设与文风：
  [`config/persona.md`](../config/persona.md)、
  [`config/style.md`](../config/style.md)、
  [`config/image_style.md`](../config/image_style.md)
- 运行时默认值：
  [`config/settings.yaml`](../config/settings.yaml)
- 密钥与模型参数：
  [`.env.example`](../.env.example) 对应的本地 `.env`

常见可改内容包括：

- 改人格和叙述口吻
- 改图片风格
- 改起点、初始余额、默认模型
- 改工具路径与图片生成脚本路径

## 依赖与外部能力

运行这个项目依赖：

- Shell 脚本工作流
- Python 工具脚本
- `jq`、`bc`、`curl`
- `bun` 用于图片生成链路
- 外部路线、天气、景点查询工具
- 兼容 OpenAI 风格接口的 LLM 服务

当前运行时还会读取 [`config/city_map.json`](../config/city_map.json) 作为城市映射配置。

## 你可以怎么改造它

- 换掉阿虾的人格，让它变成别的旅行角色
- 改路线规划，让它走不同城市或不同节奏
- 替换 LLM 或图片模型
- 调整每日工作流，让它记录更多字段
- 把游记、图片和状态发布到其他平台

如果你只是想快速上手，看首页 README；如果你准备二次开发，从这些文件开始最直接：

- [`scripts/daily_workflow.sh`](../scripts/daily_workflow.sh)
- [`config/settings.yaml`](../config/settings.yaml)
- [`config/persona.md`](../config/persona.md)
- [`data/status.json`](../data/status.json)
