# 本地运行手册

用于初始化、检查依赖和排查 TabiClaw 本地工作流。

## 环境要求

- Bash 4+
- Python 3
- `jq`
- `bc`
- `curl`
- `bun`
- 可用的 LLM API Key
- 可用的图片生成 API Key
- `config/settings.yaml` 中 `tools_path` 指向的外部工具

## 初始化

```bash
cp .env.example .env
bash scripts/init.sh
```

`.env` 至少需要配置：

```bash
LLM_PROVIDER=minimax
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.minimax.chat/v1
WRITER_MODEL=MiniMax-Text-01
```

图片生成常见配置：

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

## 配置检查

重点检查 `config/settings.yaml`：

- `tools_path` 是否存在。
- `city_map_file` 是否指向 `./config/city_map.json`。
- `image_gen_script` 是否存在。
- `git_auto_push` 是否符合当前操作预期。

## 常见问题

### 缺少命令

如果 `jq`、`bc`、`curl` 或 `bun` 缺失，先安装依赖，再运行工作流。

### 外部工具不存在

每日工作流依赖 `tools_path` 下的路线、天气、景点工具。缺失时不要手动补造结果，应修复工具路径或安装外部工具。

### API Key 缺失

文案生成和图片生成依赖 `.env`。不要把真实密钥写入仓库。

### 自动提交或 push 不符合预期

检查 `config/settings.yaml` 的 `git_auto_push`。执行会生成内容的脚本前，先用 `git status --short` 看工作区是否已有未提交变更。

## 低风险验证

```bash
bash scripts/init.sh
```

这是最适合作为配置和依赖检查的入口。不要用每日工作流代替初始化检查，因为每日工作流会改写旅行状态。

