---
name: "tabi-claw"
description: "旅行的阿虾：模拟旅行青蛙，每天自动生成游记内容。包含初始化配置、单次执行Workflow、工具脚本调用。当用户提到旅行的阿虾、TabiClaw、阿虾游记、自动生成游记时使用。"
---

# TabiClaw / 旅行的阿虾

模拟旅行青蛙的自动内容生成系统：设定初始金额和城市路径，每天自动生成一篇游记并发布到 GitHub。

## When to use this skill

- 用户提到"旅行的阿虾"、"TabiClaw"、"阿虾"、"生成游记"、"开始今天的旅行"
- 需要初始化项目配置时
- 需要执行单次旅行 Workflow 时
- 需要检查余额或旅行状态时

## 项目结构

```
TabiClaw/
├── config/                    # 配置文件目录
│   ├── persona.md           # 人设配置
│   ├── style.md             # 文风配置
│   ├── image_style.md       # 图片风格配置
│   └── settings.yaml        # 基本配置（钱包金额等）
├── data/                     # 运行时数据
│   ├── route.md             # 城市路径列表
│   ├── status.json          # 当前状态（Day/城市/余额）
│   ├── journals/            # 每日游记
│   └── output/              # 工具输出（JSON）
├── tools/                    # 工具脚本（从外部调用）
│   └── （位于 /Users/hymanhai/.openclaw/workspace/tools/）
│       ├── route.py         # 路线查询（JSON输出，最低公交价）
│       ├── attractions.py   # 景点查询（JSON输出）
│       ├── photo_spots.py   # 打卡点查询（JSON输出）
│       ├── weather.py       # 天气查询（JSON输出）
│       ├── route_planner.py # 路径规划（JSON输出）
│       └── city_map.json    # 中英文城市映射
└── scripts/                  # Workflow 执行脚本
    ├── init.sh              # 初始化检查
    └── daily_workflow.sh    # 单次执行（LLM + 图片）
```

## 工具脚本 JSON 输出格式

所有工具脚本已改造为 JSON 输出：

### route.py
```json
{
  "success": true,
  "tool": "route",
  "city_from": "杭州",
  "city_to": "南京",
  "transit_routes": [
    {"type": "transit", "duration_min": 69, "price_yuan": 141, "distance_km": 0},
    {"type": "transit", "duration_min": 64, "price_yuan": 128, "distance_km": 0}
  ],
  "best_price": 128,
  "best_route": {"type": "transit", "duration_min": 64, "price_yuan": 128}
}
```

### attractions.py
```json
{
  "success": true,
  "tool": "attractions",
  "city": "南京",
  "attractions": [
    {"name": "中山陵景区", "address": "南京市玄武区...", "tag": "景点", "rating": ""}
  ]
}
```

### photo_spots.py
```json
{
  "success": true,
  "tool": "photo_spots",
  "spot_name": "中山陵景区",
  "photo_spots": [
    {"name": "头陀岭景区-观景台", "address": ""}
  ]
}
```

### weather.py
```json
{
  "success": true,
  "tool": "weather",
  "city_cn": "南京",
  "city_en": "Nanjing",
  "temp_c": "19",
  "weather_desc": "Overcast",
  "temp_range": "12-16"
}
```

## 核心 Workflow

### 1. 初始化检查 (init)
```bash
bash scripts/init.sh
```

### 2. 单次执行 Workflow (daily_run)
```bash
# 手动执行
bash scripts/daily_workflow.sh

# 指定日期
bash scripts/daily_workflow.sh 2026-03-30
```

### 3. LLM 生成内容
使用 MiniMax 生成游记内容，支持：
- 人设风格保持
- 景点描述
- 心境总结

### 4. 图片提示词生成
基于打卡点和天气生成 AI 图片提示词，风格：
- 日系水彩
- 低饱和度
- 绘本感

## 环境变量要求

项目使用 `.env` 文件管理密钥。请复制 `.env.example` 到根目录的 `.env` 中并填写真实密钥。

```bash
# MiniMax LLM（必需）
MINIMAX_API_KEY=your_key_here
LLM_PROVIDER=minimax
MINIMAX_BASE_URL=https://api.minimax.chat/v1
WRITER_MODEL=MiniMax-M2.5

# 图片生成（可选）
DASHSCOPE_API_KEY=your_key_here
IMAGE_PROVIDER=dashscope
IMAGE_MODEL=qwen-image-2.0-pro

# 路径
TABICLAW_ROOT=/Users/hymanhai/TabiClaw
TOOLS_PATH=/Users/hymanhai/.openclaw/workspace/tools
```

## 使用示例

**初始化项目**:
```
用户: 帮我初始化旅行的阿虾
助手: 调用 init.sh，检查配置，引导用户补充
```

**生成今日游记**:
```
用户: 今天阿虾的游记
助手: 调用 daily_workflow.sh，执行完整流程
```

**检查状态**:
```
用户: 阿虾现在到哪了
助手: 读取 status.json，汇报当前状态
```

**配置路径**:
```
用户: 规划阿虾从杭州到北京的路线
助手: 调用 route_planner.py，更新 route.md
```

## 状态文件格式 (status.json)

```json
{
  "current_day": 2,
  "current_city": "南京",
  "current_wallet": 872,
  "last_updated": "2026-03-30",
  "status": "traveling"
}
```

## 游记文件格式

`data/journals/YYYY-MM-DD-{城市}.md`：
- 基本信息（日期/Day/出发地/目的地/交通费/天气）
- 今日发现
- 打卡地点
- 心境