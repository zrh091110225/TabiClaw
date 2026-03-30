# RoamShrimp / 旅行的阿虾

模拟旅行青蛙的自动内容生成系统。

## 项目状态

| 指标   | 值       |
| ---- | ------- |
| Day  | 0       |
| 当前城市 | 未知      |
| 余额   | 10000 元 |
| 状态   | ⚪ 未开始   |

## 每日游记

[📖 查看完整游记列表](./data/journals/index.md)

## 项目介绍

### 关于阿虾

阿虾是一只淡红色的小龙虾，戴着小草帽，给我一笔启动资金，告诉我从哪里出发要去哪里，我就帮你去看看这个世界。

性格随性、好奇、有点呆萌，喜欢慢节奏的旅行，享受途中的小细节。

### 安装使用

#### 环境要求

- Bash 4+
- Python 3
- jq
- bun（用于图片生成）

#### 初始化

```bash
# 检查配置文件
bash scripts/init.sh
```

#### 生成今日游记

```bash
# 自动执行完整流程
bash scripts/daily_workflow.sh

# 指定日期执行
bash scripts/daily_workflow.sh 2026-03-31
```

#### 路线规划

```bash
# 重新规划完整的旅行路径（会覆盖现有路径）
bash scripts/replan_route.sh 杭州 北京

# 重新规划路径并重置阿虾的状态（回到起点，余额恢复）
bash scripts/replan_route.sh 杭州 北京 --reset

# 从当前路径的最后一个城市继续规划后续行程（追加到现有路径）
bash scripts/continue_route.sh 广州
```

#### 定时任务

通过 OpenClaw Cron 配置每日自动执行：

```bash
crontab -e
# 每天早上 8 点运行
0 8 * * * cd /Users/hymanhai/RoamShrimp && bash scripts/daily_workflow.sh
```

### 项目结构

```
RoamShrimp/
├── README.md              # 本文件
├── config/                # 配置文件
│   ├── persona.md         # 人设
│   ├── style.md           # 文风
│   ├── image_style.md      # 图片风格
│   └── settings.yaml       # 基本设置
├── data/                  # 运行数据
│   ├── route.md           # 城市路径
│   ├── status.json        # 当前状态
│   ├── journals/          # 每日游记
│   │   ├── index.md       # 游记索引（追加）
│   │   └── *.md           # 每日游记
│   └── images/            # 生成图片
├── scripts/               # 执行脚本
│   ├── init.sh            # 初始化检查
│   ├── daily_workflow.sh  # 每日执行
│   ├── replan_route.sh    # 重新规划路径
│   └── continue_route.sh  # 续写后续路径
└── skills/                # Skill 定义
    └── roam-shrimp/
```

### 工具脚本

位于 `/Users/hymanhai/.openclaw/workspace/tools/`：

| 脚本                 | 功能          |
| ------------------ | ----------- |
| `route.py`         | 路线查询（最低价公交） |
| `attractions.py`   | 景点查询        |
| `photo_spots.py`   | 打卡点查询       |
| `weather.py`       | 天气查询        |
| `route_planner.py` | 城市路径规划      |

### 环境变量

项目需要配置环境变量才能正常运行。请复制示例文件并填入真实的密钥：

```bash
cp .env.example .env
```

`.env` 文件内容说明：

```bash
MINIMAX_API_KEY=your_key        # MiniMax LLM
MINIMAX_BASE_URL=https://api.minimax.chat/v1
DASHSCOPE_API_KEY=your_key     # 通义万相图片生成
# TINYPNG_API_KEY=your_key     # 可选：图片压缩
```

***

*阿虾的旅行记录*
