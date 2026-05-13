# TabiClaw Agent Guide

本文件给代码代理使用，用来快速理解当前项目、选择正确入口，并避免误改运行数据。

## 项目定位

TabiClaw 是一个持续运行的 AI 旅行档案项目，不是后端订单系统或普通内容生成脚本。

核心角色是“旅行的阿虾”。每执行一次每日工作流，阿虾会沿路线前进一步，生成当天游记和图片，并把状态、路线、索引、产物和 Git 历史一起留在仓库中。

## 优先响应语言

对用户回复使用简体中文。

## 先读哪些文件

按任务加载上下文，不要一次性读取所有文档。

- 项目概览：`README.md`
- 导航地图：`docs/project-map.md`
- 工作机制：`docs/how-it-works.md`
- 当前状态入口：`data/journals/index.md`
- 机器状态：`data/status.json`
- 当前路线：`data/route.md`
- 运行配置：`config/settings.yaml`
- Skill 说明：`skills/tabi-claw/SKILL.md`

查询“阿虾现在在哪”“余额还有多少”“当前旅行第几天”时，优先读 `data/journals/index.md`，再用 `data/status.json` 补充。不要只读 README。

## 硬规则

- 不要把当前旅行状态写回 README 顶部；状态面板属于 `data/journals/index.md`。
- 查看类请求不要运行会推进路线或生成内容的脚本。
- `scripts/daily_workflow.sh` 会改写状态、生成文件，并可能自动 Git 提交。
- `scripts/clean_data.sh` 会清空运行数据，只有用户明确要求时才运行。
- 不要提交 `.env` 或真实 API Key、token、cookie。
- 不要把这个仓库当作订单、支付、退款、MQ 或事务系统分析，除非用户提供其他代码或路径。
- 不要编造当前仓库不存在的业务模块、历史决策或规格。

## 常用入口

```bash
# 初始化检查
bash scripts/init.sh

# 执行一次每日旅行工作流
bash scripts/daily_workflow.sh
bash scripts/daily_workflow.sh YYYY-MM-DD

# 生成阶段总结
bash scripts/period_summary.sh --start-date YYYY-MM-DD --end-date YYYY-MM-DD

# 生成最近 7 个自然日的周总结
bash scripts/weekly_summary.sh

# 重新规划路线
bash scripts/replan_route.sh 起点 终点
bash scripts/replan_route.sh 起点 终点 --reset

# 从当前路线末尾继续追加路线
bash scripts/continue_route.sh 终点
```

## 文档导航

- `docs/project-map.md`：项目地图和任务导航。
- `docs/workflows/daily-travel.md`：每日旅行工作流操作手册。
- `docs/workflows/period-summary.md`：阶段总结和周总结操作手册。
- `docs/workflows/route-planning.md`：重规划和追加路线操作手册。
- `docs/runbooks/local-dev.md`：本地依赖、配置和排障。
- `openspec/project.md`：OpenSpec 项目入口和规格边界。

## Git 注意事项

- 做代码改动前先检查工作区状态，避免覆盖用户已有变更。
- 不要使用 `git reset --hard`、`git checkout --` 等会丢弃用户变更的命令，除非用户明确要求。
- 每日工作流可能自动提交，是否自动 push 由 `config/settings.yaml` 的 `git_auto_push` 控制。

