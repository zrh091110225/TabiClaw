---
name: "tabi-claw"
description: "旅行的阿虾：一个持续运行的 AI 旅行仓库。按路线推进城市、生成游记与配图、维护状态和索引，并可自动提交 Git。当用户提到 TabiClaw、旅行的阿虾、阿虾游记、继续旅行、查看状态、重规划路线时使用。"
---

# TabiClaw / 旅行的阿虾

TabiClaw 不是一次性内容生成器，而是一个每天推进一天的旅行工作流项目。

阿虾会沿着 `data/route.md` 中的路线前进。每次执行每日工作流时，项目会：

- 读取当前状态
- 计算下一站
- 查询路线价格、景点、天气
- 生成一篇游记
- 生成一张配图
- 更新 `status.json`
- 更新 `data/journals/index.md` 顶部的当前状态面板和游记列表
- 记录 Git 提交

## When to use this skill

- 用户提到“旅行的阿虾”、“TabiClaw”、“阿虾”
- 用户想“生成今天的游记”、“让阿虾继续旅行”
- 用户想生成某一段时间的阶段总结或路线海报
- 用户想查看当前状态、余额、当前城市、路线
- 用户想重新规划路线或从当前终点继续追加路线
- 用户想初始化、清理、重置这个项目

## 当前项目结构

```text
TabiClaw/
├── README.md
├── README.en.md
├── config/
│   ├── city_map.json        # 城市中英文映射，已移入项目
│   ├── image_prompt.md      # 图片提示词模板
│   ├── image_style.md       # 图片风格配置
│   ├── journal_prompt.md    # 游记提示词模板
│   ├── persona.md           # 人设
│   ├── settings.yaml        # 路径 / 模型 / Git 行为等配置
│   └── style.md             # 文风配置
├── data/
│   ├── images/              # 生成图片
│   │   └── summaries/       # 阶段路线海报
│   ├── journals/
│   │   ├── index.md         # 当前状态面板 + 游记索引入口
│   │   └── YYYY-MM-DD-城市.md
│   ├── logs/
│   ├── output/              # 中间产物、prompt、JSON输出
│   ├── route.md             # 剩余路线
│   ├── summaries/           # 阶段总结
│   └── status.json          # 当前状态
├── docs/
├── scripts/
│   ├── auto_commit.sh
│   ├── check_stars.py
│   ├── clean_data.sh
│   ├── continue_route.sh
│   ├── daily_workflow.sh
│   ├── generate_period_summary.py
│   ├── generate_images.sh
│   ├── generate_landmarks.py
│   ├── init.sh
│   ├── period_summary.sh
│   ├── weekly_summary.sh
│   ├── replan_route.sh
│   └── lib/
│       ├── config.sh
│       ├── settings.py
│       └── template_renderer.py
└── skills/
    └── tabi-claw/
```

## 状态与索引约定

当前状态以两个文件为准：

- `data/status.json`：机器可读的运行状态
- `data/journals/index.md`：人可读入口，顶部包含“当前状态”面板，下面是游记列表

README 不再维护顶部状态表。查看“阿虾现在到哪了”，优先读：

1. `data/journals/index.md`
2. `data/status.json`

## 核心脚本

### 1. 初始化检查

```bash
bash scripts/init.sh
```

用途：

- 检查配置文件是否完整
- 检查运行时数据是否存在
- 检查外部工具路径是否可用
- 必要时初始化 `status.json`

### 2. 执行一次每日工作流

```bash
bash scripts/daily_workflow.sh
bash scripts/daily_workflow.sh 2026-03-31
```

这是项目最核心的入口。它会推进一天旅行，并更新：

- `data/status.json`
- `data/route.md`
- `data/journals/index.md`
- `data/journals/*.md`
- `data/images/*.png`
- `data/output/*`
- Git 提交记录

### 3. 重新规划完整路线

```bash
bash scripts/replan_route.sh 杭州 北京
bash scripts/replan_route.sh 杭州 北京 --reset
```

作用：

- 重写 `data/route.md`
- 使用 `--reset` 时重置 `status.json`
- 同步更新 `data/journals/index.md` 顶部状态

### 4. 从当前终点继续追加路线

```bash
bash scripts/continue_route.sh 广州
```

作用：

- 从 `data/route.md` 的最后一个城市继续规划
- 将新增路线追加到现有 `route.md`

### 5. 清空运行数据

```bash
bash scripts/clean_data.sh
```

作用：

- 清空图片和单篇游记
- 重建 `data/journals/index.md`
- 保留索引顶部说明文字
- 重置 `status.json`
- 清空 `route.md`

### 6. 生成阶段总结

```bash
bash scripts/period_summary.sh --start-date 2026-03-31 --end-date 2026-04-06
```

作用：

- 基于历史游记生成阶段总结 Markdown
- 生成一张阶段旅程主视觉海报
- 更新 `data/journals/index.md` 中的阶段总结入口
- 运行时在控制台直接打印阶段总结文案 prompt、阶段海报 prompt 和模型调用参数

### 7. 生成周总结

```bash
bash scripts/weekly_summary.sh
```

作用：

- 自动以今天为结束日，向前覆盖最近 7 个自然日（含今天）
- 底层转调 `scripts/period_summary.sh`
- 不需要手动传递日期参数

## 配置规则

项目当前把以下运行参数收敛到 `config/settings.yaml`：

- `tools_path`
- `city_map_file`
- `image_gen_script`
- `llm_provider_default`
- `llm_base_url_default`
- `writer_model_default`
- `image_provider_default`
- `image_model_default`
- `summary_image_mode_default`
- `git_auto_push`

其中：

- `city_map.json` 已经移入项目内，默认指向 `./config/city_map.json`
- `git_auto_push=false` 时，自动提交后只 `commit`，不 `push`
- 阶段海报默认复用游记图片生成的 `IMAGE_PROVIDER` / `IMAGE_MODEL`
- `summary_image_mode_default` 当前默认值是 `single_pass`

## 外部依赖

项目仍依赖外部工具目录 `tools_path` 下的脚本：

- `route.py`
- `attractions.py`
- `photo_spots.py`
- `weather.py`
- `route_planner.py`

但 `city_map.json` 已不再依赖外部目录，已经内置在项目的 `config/` 中。

## 环境变量

至少需要：

```bash
LLM_PROVIDER=minimax
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.minimax.chat/v1
WRITER_MODEL=MiniMax-Text-01
```

图片生成常见变量：

```bash
IMAGE_PROVIDER=google
IMAGE_MODEL=gemini-3.1-flash-image-preview
GEMINI_API_KEY=your_key
```

或：

```bash
IMAGE_PROVIDER=dashscope
IMAGE_MODEL=qwen-image-2.0-pro
DASHSCOPE_API_KEY=your_key
```

可选：

```bash
TINYPNG_API_KEY=your_key
```

阶段总结脚本不会单独要求 `SUMMARY_IMAGE_PROVIDER` / `SUMMARY_IMAGE_MODEL`；
默认直接沿用上面这组游记图片变量。

## 用户请求到操作的映射

### 用户：帮我初始化旅行的阿虾

做法：

- 运行 `bash scripts/init.sh`
- 汇报缺失配置、当前状态、当前路线

### 用户：今天阿虾的游记 / 让阿虾继续旅行

做法：

- 运行 `bash scripts/daily_workflow.sh`
- 返回新城市、余额、生成的游记和图片路径

### 用户：阿虾现在在哪 / 余额还有多少

做法：

- 优先读取 `data/journals/index.md`
- 再用 `data/status.json` 做机器状态补充

### 用户：帮我总结过去一周 / 总结某一段旅程

做法：

- 如果用户明确是“过去一周”或“最近 7 天”，优先运行 `bash scripts/weekly_summary.sh`
- 如果用户给了明确的开始日期和结束日期，运行 `bash scripts/period_summary.sh --start-date YYYY-MM-DD --end-date YYYY-MM-DD`
- 返回总结文件、路线海报和索引入口

### 用户：重规划从杭州到北京

做法：

- 运行 `bash scripts/replan_route.sh 杭州 北京`
- 如果用户明确要求重置状态，则加 `--reset`

### 用户：从当前路线继续往广州走

做法：

- 运行 `bash scripts/continue_route.sh 广州`

### 用户：清空历史重新开始

做法：

- 运行 `bash scripts/clean_data.sh`
- 说明会清空图片、游记和路线，并重置状态

## 重要注意事项

- 不要再把“项目状态”写回 README；当前状态面板属于 `data/journals/index.md`
- 查询当前状态时，不要只读 README
- 清理数据时，要保留 `index.md` 顶部说明文字
- 每日工作流会产生真实文件变更，且可能自动 Git 提交
- 如果只是查看状态，不要主动执行 `daily_workflow.sh`
