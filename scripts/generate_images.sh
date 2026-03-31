#!/usr/bin/env bash

# 生成图片的独立脚本，只生成图片，不修改状态、不上传、不压缩
# 用法: bash scripts/generate_images.sh <城市1> [城市2] ...

if [[ $# -eq 0 ]]; then
  echo "用法: $0 <城市1> [城市2] ..."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=/dev/null
source "$PROJECT_ROOT/scripts/lib/config.sh"
load_runtime_config "$PROJECT_ROOT"

# 检查依赖
if ! command -v "jq" &>/dev/null; then
  echo "[ERROR] 缺少依赖: jq"
  exit 1
fi
if ! command -v "python3" &>/dev/null; then
  echo "[ERROR] 缺少依赖: python3"
  exit 1
fi

# 加载环境变量
if [[ -f "$HOME/.env" ]]; then
  set -a
  source "$HOME/.env"
  set +a
fi

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  # 注意：由于我们在同一终端中多次加载，
  # 我们需要确保优先使用 ~/.env 或者明确哪些变量覆盖哪些。
  # 按照你的要求“复用这个配置文件的里面的配置信息：~/.env”
  # 这里为了保证 ~/.env 优先级最高，我们先加载 .env，再加载 ~/.env
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

  # 再次加载 ~/.env 确保优先级最高
  if [[ -f "$HOME/.env" ]]; then
    set -a
    source "$HOME/.env"
    set +a
  fi
  
  if [[ -z "$LLM_API_KEY" ]]; then
    echo "[ERROR] 未配置 LLM_API_KEY"
    exit 1
  fi

# 默认配置
LLM_PROVIDER="${LLM_PROVIDER:-$llm_provider_default}"
LLM_BASE_URL="${LLM_BASE_URL:-$llm_base_url_default}"
WRITER_MODEL="${WRITER_MODEL:-$writer_model_default}"
IMAGE_PROVIDER="${IMAGE_PROVIDER:-$image_provider_default}"
IMAGE_MODEL="${IMAGE_MODEL:-$image_model_default}"

BAOYU_IMAGE_GEN="$image_gen_script"
OUTPUT_DIR="$HOME/Desktop/图片"
mkdir -p "$OUTPUT_DIR"

IMAGE_STYLE_CONTENT=$(cat "$PROJECT_ROOT/config/image_style.md" 2>/dev/null || echo "")
IMAGE_PROMPT_TEMPLATE_FILE="$PROJECT_ROOT/config/image_prompt.md"

for NEXT_CITY in "$@"; do
  echo "========================================="
  echo "开始为城市 [$NEXT_CITY] 生成图片..."
  
  # 获取景点信息
  echo "  1. 获取地标信息..."
  ATTRACTION_JSON=$(python3 "$PROJECT_ROOT/scripts/generate_landmarks.py" "$NEXT_CITY" 1) || ATTRACTION_JSON='[]'
  
  # DEBUG
  if [[ "$ATTRACTION_JSON" == '[]' || -z "$ATTRACTION_JSON" ]]; then
    echo "    [DEBUG] python3 generate_landmarks.py 执行结果为空或失败"
  else
    echo "    [DEBUG] 获取到的地标信息: $ATTRACTION_JSON"
  fi
  
  ATTRACTION_1=$(echo "$ATTRACTION_JSON" | jq -r '.[0].landmark // empty' 2>/dev/null | tr -d '\r')
  ATTRACTION_1_DESC=$(echo "$ATTRACTION_JSON" | jq -r '.[0].desc // empty' 2>/dev/null | tr -d '\r')
  
  ATTRACTION_1="${ATTRACTION_1:-}"
  ATTRACTION_1_DESC="${ATTRACTION_1_DESC:-}"
  
  if [[ -z "$ATTRACTION_1" || -z "$ATTRACTION_1_DESC" ]]; then
    echo "    [ERROR] 获取地标信息失败或返回为空"
    exit 1
  fi
  
  echo "    选用景点: $ATTRACTION_1"
  
  # 构造生成提示词的 Prompt
  echo "  2. 生成图片提示词..."
  WEATHER_DESC="晴"
  WEATHER_DESC_VAL="${WEATHER_DESC:-afternoon}"
  
  export IMAGE_STYLE_CONTENT NEXT_CITY ATTRACTION_1 ATTRACTION_1_DESC WEATHER_DESC_VAL
  IMAGE_PROMPT_PROMPT=$(python3 -c "
import os, sys
text = sys.stdin.read()
keys = {
    'IMAGE_STYLE_CONTENT': os.environ.get('IMAGE_STYLE_CONTENT', ''),
    'NEXT_CITY': os.environ.get('NEXT_CITY', ''),
    'CITY': os.environ.get('NEXT_CITY', ''),
    'ATTRACTION_1': os.environ.get('ATTRACTION_1', ''),
    'ATTRACTION_1_DESC': os.environ.get('ATTRACTION_1_DESC', ''),
    'WEATHER_DESC': os.environ.get('WEATHER_DESC_VAL', '')
}
for k, v in keys.items():
    text = text.replace('{{' + k + '}}', v)
print(text)
" < "$IMAGE_PROMPT_TEMPLATE_FILE")

  # 调试：打印替换后的 PROMPT
  # echo "    [DEBUG] IMAGE_PROMPT_PROMPT:"
  # echo "$IMAGE_PROMPT_PROMPT"

  IMAGE_PROMPT=""
  if [[ "$LLM_PROVIDER" == "gemini" ]]; then
    # 确保 gemini 的 URL 格式正确
    if [[ "$LLM_BASE_URL" != */v1beta* && "$LLM_BASE_URL" != */v1* ]]; then
      LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta"
    fi
    
    # 打印 LLM_BASE_URL 和 LLM_API_KEY （隐藏部分字符）供调试
    # echo "    [DEBUG] LLM_BASE_URL: $LLM_BASE_URL"
    # echo "    [DEBUG] LLM_API_KEY: ${LLM_API_KEY:0:4}...${LLM_API_KEY: -4}"
    
    IMAGE_PROMPT_CONTENT=$(curl -sS --max-time 60 -X POST "$LLM_BASE_URL/models/${WRITER_MODEL}:generateContent?key=$LLM_API_KEY" \
      -H "Content-Type: application/json" \
      -d "{
        \"contents\": [{
          \"parts\":[{\"text\": $(echo "$IMAGE_PROMPT_PROMPT" | jq -sRs .)}]
        }],
        \"generationConfig\": {
          \"temperature\": 0.7
        }
      }" 2>/dev/null)
    # Gemini 返回的结构，如果生成被过滤或出错，可能没有 text 字段
    IMAGE_PROMPT=$(echo "$IMAGE_PROMPT_CONTENT" | jq -r '.candidates[0].content.parts[0].text // empty' 2>/dev/null)
    # DEBUG
    if [[ -z "$IMAGE_PROMPT" || "$IMAGE_PROMPT" == "null" ]]; then
        echo "    [DEBUG] Gemini 提示词生成失败返回: $IMAGE_PROMPT_CONTENT"
    fi
  else
    # OpenAI 兼容格式
    if [[ "$LLM_BASE_URL" == */ ]]; then
        API_URL="${LLM_BASE_URL}chat/completions"
    else
        API_URL="${LLM_BASE_URL}/chat/completions"
    fi
    
    IMAGE_PROMPT_CONTENT=$(curl -sS --max-time 60 -X POST "$API_URL" \
      -H "Authorization: Bearer $LLM_API_KEY" \
      -H "Content-Type: application/json" \
      -d "{
        \"model\": \"$WRITER_MODEL\",
        \"temperature\": 0.7,
        \"messages\": [
          {\"role\": \"user\", \"content\": $(echo "$IMAGE_PROMPT_PROMPT" | jq -sRs .)}
        ]
      }" 2>/dev/null)
    IMAGE_PROMPT=$(echo "$IMAGE_PROMPT_CONTENT" | jq -r '.choices[0].message.content // empty' 2>/dev/null)
  fi

  # 如果大模型返回空，直接退出报错
  if [[ -z "$IMAGE_PROMPT" || "$IMAGE_PROMPT" == "null" ]]; then
    echo "    [ERROR] 提示词生成失败，终止执行。"
    exit 1
  fi

  
  # 清理可能存在的 Markdown 代码块标记、换行符等
  IMAGE_PROMPT=$(echo "$IMAGE_PROMPT" | sed 's/```[a-zA-Z]*//g' | sed 's/```//g' | tr -d '\n' | sed 's/^ *//;s/ *$//')
  
  # 兜底：如果模型没有替换变量，或者直接输出了带变量的文本，我们再次在 bash 层级强制替换一次
  # 模型有时候会转义下划线变成 \{\{NEXT\_CITY\}\}，所以我们需要处理这种情况
  IMAGE_PROMPT=$(echo "$IMAGE_PROMPT" | sed 's/\\_/_/g')
  
  IMAGE_PROMPT="${IMAGE_PROMPT//\{\{NEXT_CITY\}\}/$NEXT_CITY}"
  IMAGE_PROMPT="${IMAGE_PROMPT//\{\{CITY\}\}/$NEXT_CITY}"
  IMAGE_PROMPT="${IMAGE_PROMPT//\{\{ATTRACTION_1\}\}/$ATTRACTION_1}"
  IMAGE_PROMPT="${IMAGE_PROMPT//\{\{ATTRACTION_1_DESC\}\}/$ATTRACTION_1_DESC}"
  IMAGE_PROMPT="${IMAGE_PROMPT//\{\{WEATHER_DESC\}\}/$WEATHER_DESC_VAL}"
  
  echo "    提示词: $IMAGE_PROMPT"
  
  # 调用图片生成服务
  echo "  3. 生成图片..."
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  IMAGE_OUTPUT="$OUTPUT_DIR/${NEXT_CITY}_${TIMESTAMP}.png"
  
  if ! command -v bun &>/dev/null; then
    echo "    [ERROR] bun 未安装"
    exit 1
  fi
  
  # 检查图片生成 API 密钥
  HAS_IMAGE_API_KEY="false"
  if [[ "$IMAGE_PROVIDER" == "google" && -n "$GEMINI_API_KEY" ]]; then
    export GEMINI_API_KEY
    HAS_IMAGE_API_KEY="true"
  elif [[ "$IMAGE_PROVIDER" == "dashscope" && -n "$DASHSCOPE_API_KEY" ]]; then
    export DASHSCOPE_API_KEY
    HAS_IMAGE_API_KEY="true"
  elif [[ -n "$OPENAI_API_KEY" || -n "$OPENROUTER_API_KEY" || -n "$REPLICATE_API_TOKEN" ]]; then
    HAS_IMAGE_API_KEY="true"
  fi
  
  if [[ "$HAS_IMAGE_API_KEY" == "false" ]]; then
    echo "    [ERROR] 未配置对应的图片生成 API_KEY ($IMAGE_PROVIDER)"
    exit 1
  fi
  
  if bun "$BAOYU_IMAGE_GEN" \
    --provider "$IMAGE_PROVIDER" \
    --model "$IMAGE_MODEL" \
    --prompt "$IMAGE_PROMPT" \
    --image "$IMAGE_OUTPUT" \
    --ar 3:4 \
    --imageSize 1K \
    --json; then
    echo "    ✅ 图片已成功生成并保存在: $IMAGE_OUTPUT"
  else
    echo "    [ERROR] 图片生成失败"
    exit 1
  fi

done

echo "========================================="
echo "执行完毕！"
