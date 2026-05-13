# TabiClaw OpenSpec Project

本文件是 OpenSpec 入口，用来记录项目规格边界和后续变更位置。项目知识和操作手册放在 `docs/`，需求、规格和变更记录放在 `openspec/`。

## 项目范围

TabiClaw 是一个持续运行的 AI 旅行档案项目。核心能力包括：

- 维护旅行角色、路线、状态和余额。
- 每日推进一站并生成游记和图片。
- 生成指定时间范围的阶段总结和路线海报。
- 维护人可读索引、机器状态和 Git 历史。

## 非目标

- 不是订单、支付、退款、MQ 或事务系统。
- 不维护真实旅游预订或资金结算。
- 不把 OpenSpec 规格混入 `docs/`。

## 当前规格入口

当前仓库尚未建立正式 feature spec。新增需求时建议使用：

- `openspec/changes/`：进行中的变更提案、任务和设计。
- `openspec/specs/`：已接受的当前规格。
- `openspec/archive/`：归档的历史变更。

## 与文档层的关系

- `AGENTS.md`：代理入口和硬规则。
- `docs/project-map.md`：项目导航。
- `docs/workflows/`：任务操作手册。
- `docs/runbooks/`：本地运行和排障。
- `openspec/`：正式需求和规格。

## 当前约束

- 当前状态面板属于 `data/journals/index.md`。
- 每日工作流可以改写状态、路线、索引、图片和游记。
- 阶段总结不应推进路线，也不应修改 `data/status.json`。
- 缺失外部工具或 API Key 时，应报告依赖问题，不应伪造事实数据。

