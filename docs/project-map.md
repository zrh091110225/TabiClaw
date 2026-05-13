# TabiClaw 项目地图

这份文档是项目导航入口，用来帮助维护者和代码代理快速定位应该阅读和修改的文件。它不是完整设计文档。

## 项目目的

TabiClaw 把一次虚拟旅行拆成可重复执行的日常工作流。每次运行每日脚本，项目都会推进路线、生成游记与配图、更新状态与索引，并把结果留在仓库历史中。

## 核心流程

每日旅行流程：

1. 读取 `data/status.json` 和 `data/route.md`。
2. 计算下一站，并查询路线、景点、天气等事实。
3. 根据 `config/` 中的人设、文风、图片风格生成游记和图片。
4. 更新 `data/status.json`、`data/route.md`、`data/journals/index.md`。
5. 写入每日游记、图片和中间产物。
6. 根据配置决定是否自动提交和 push。

阶段总结流程：

1. 从 `data/journals/index.md` 和单篇游记抽取时间范围内的事实。
2. 读取同日期景点和天气补充数据。
3. 生成阶段总结 Markdown、路线海报和结构化事实 JSON。
4. 更新 `data/journals/index.md` 中的阶段总结入口。

## 代码和数据地图

- `scripts/daily_workflow.sh`：每日旅行主入口。
- `scripts/period_summary.sh`：指定时间范围的阶段总结入口。
- `scripts/weekly_summary.sh`：最近 7 个自然日周总结入口。
- `scripts/replan_route.sh`：从起点到终点重新规划路线。
- `scripts/continue_route.sh`：从当前路线末尾继续追加目的地。
- `scripts/clean_data.sh`：清空运行数据并重置状态。
- `scripts/lib/config.sh`：Shell 侧共享配置和索引更新逻辑。
- `scripts/lib/settings.py`：Python 侧配置读取。
- `scripts/lib/template_renderer.py`：模板渲染工具。
- `config/settings.yaml`：运行时默认配置。
- `config/persona.md`、`config/style.md`、`config/image_style.md`：角色、文风和图片风格。
- `data/status.json`：机器可读的当前状态。
- `data/route.md`：当前剩余路线。
- `data/journals/index.md`：人可读状态面板、游记索引和阶段总结入口。

## 任务导航

- 继续旅行：读 `docs/workflows/daily-travel.md`。
- 生成阶段总结或周总结：读 `docs/workflows/period-summary.md`。
- 重规划路线或追加路线：读 `docs/workflows/route-planning.md`。
- 配置本地环境或排查依赖：读 `docs/runbooks/local-dev.md`。
- 查看规格边界：读 `openspec/project.md`。

## 文档分层

- `AGENTS.md`：AI 入口、硬规则和最短导航。
- `docs/project-map.md`：项目地图和任务导航。
- `docs/workflows/`：可执行任务手册。
- `docs/runbooks/`：本地运行和排障。
- `openspec/`：规格入口、需求和后续变更记录。

