# TabiClaw Daily Workflow - 旅行的阿虾每日执行脚本 (JSON 工具版 + MiniMax LLM + 图片生成)
# 用法: bash scripts/daily_workflow.sh [日期 YYYY-MM-DD]

# 改为 trap 捕获错误，不要一失败就退出
set -uo pipefail

# 错误处理函数
error_exit() {
  echo "[ERROR] $1" >&2
  echo "[ERROR] $1" >> "$PROJECT_ROOT/data/logs/error_${TARGET_DATE}.log"
  exit 1
}

error_warn() {
  echo "[WARN] $1" >&2
  echo "[WARN] $1" >> "$PROJECT_ROOT/data/logs/error_${TARGET_DATE}.log"
}

log_info() {
  echo "[INFO] $1"
  echo "[INFO] $1" >> "$PROJECT_ROOT/data/logs/workflow_${TARGET_DATE}.log"
}

# 找到项目根目录
CLAWGO_ROOT=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for dir in "$SCRIPT_DIR" "$SCRIPT_DIR/.." "$SCRIPT_DIR/../.." "$SCRIPT_DIR/../../.."; do
  if [[ -f "$dir/config/persona.md" ]]; then
    CLAWGO_ROOT="$(cd "$dir" && pwd)"
    break
  fi
done

if [[ -z "$CLAWGO_ROOT" ]]; then
  echo "[ERROR] Cannot find project root" >&2
  exit 1
fi

PROJECT_ROOT="$CLAWGO_ROOT"
# shellcheck source=/dev/null
source "$PROJECT_ROOT/scripts/lib/config.sh"
load_runtime_config "$PROJECT_ROOT"
TOOLS_PATH="$tools_path"
CITY_MAP="$city_map_file"
BAOYU_IMAGE_GEN="$image_gen_script"

# 解析命令行参数
ENV_FILE=""
TARGET_DATE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    *)
      if [[ -z "$TARGET_DATE" ]]; then
        TARGET_DATE="$1"
      fi
      shift
      ;;
  esac
done

TARGET_DATE="${TARGET_DATE:-$(date +%Y-%m-%d)}"

# 确保日志目录存在
mkdir -p "$PROJECT_ROOT/data/logs"
mkdir -p "$PROJECT_ROOT/data/output"
mkdir -p "$PROJECT_ROOT/data/journals"
mkdir -p "$PROJECT_ROOT/data/images"

# 初始化当日日志
echo "==========================================" > "$PROJECT_ROOT/data/logs/workflow_${TARGET_DATE}.log"
echo "TabiClaw Daily Workflow: $TARGET_DATE" >> "$PROJECT_ROOT/data/logs/workflow_${TARGET_DATE}.log"
echo "==========================================" >> "$PROJECT_ROOT/data/logs/workflow_${TARGET_DATE}.log"

log_info "开始执行每日工作流"

# ============ 检查 GitHub Star 并增加资金 ============
log_info "检查 GitHub 项目 Star 数量..."
python3 "$PROJECT_ROOT/scripts/check_stars.py" >> "$PROJECT_ROOT/data/logs/workflow_${TARGET_DATE}.log" 2>&1
if [[ $? -eq 0 ]]; then
  log_info "GitHub Star 检查完成"
else
  error_warn "GitHub Star 检查失败"
fi

# ============ 依赖检查 ============
check_dependency() {
  local cmd="$1"
  local name="$2"
  if ! command -v "$cmd" &>/dev/null; then
    error_exit "缺少依赖: $name (command: $cmd)"
  fi
}

log_info "检查依赖..."
check_dependency "python3" "Python3"
check_dependency "jq" "jq"
check_dependency "bc" "bc"
check_dependency "curl" "curl"

# 检查 bun（图片生成用）
if ! command -v "bun" &>/dev/null; then
  error_warn "未找到 bun，图片生成可能失败"
fi

# 加载 .env 文件
if [[ -n "$ENV_FILE" ]]; then
  if [[ -f "$ENV_FILE" ]]; then
    log_info "加载指定配置: $ENV_FILE..."
    set -a
    source "$ENV_FILE" || error_warn "$ENV_FILE 加载失败"
    set +a
  else
    error_exit "指定的配置文件不存在: $ENV_FILE"
  fi
elif [[ -f "$PROJECT_ROOT/.env" ]]; then
  log_info "加载默认配置: .env..."
  set -a
  source "$PROJECT_ROOT/.env" || error_warn ".env 加载失败"
  set +a
else
  log_info "未找到配置文件"
fi

# 环境变量显式校验，缺失即退出
: "${LLM_API_KEY:?未配置 LLM_API_KEY，请在 .env 中设置}"

# LLM 配置（默认值）
LLM_PROVIDER="${LLM_PROVIDER:-$llm_provider_default}"
LLM_BASE_URL="${LLM_BASE_URL:-$llm_base_url_default}"
WRITER_MODEL="${WRITER_MODEL:-$writer_model_default}"

# 图片生成配置（支持通过环境变量动态配置）
IMAGE_PROVIDER="${IMAGE_PROVIDER:-$image_provider_default}"
IMAGE_MODEL="${IMAGE_MODEL:-$image_model_default}"

echo "=========================================="
echo "TabiClaw Daily Workflow: $TARGET_DATE"
echo "=========================================="

# 1. 读取状态
echo "[1/11] 读取状态..."
log_info "步骤1: 读取状态"
STATUS_FILE="$PROJECT_ROOT/data/status.json"
if [[ -f "$STATUS_FILE" ]]; then
  CURRENT_CITY=$(jq -r '.current_city' "$STATUS_FILE" 2>/dev/null)
  CURRENT_WALLET=$(jq -r '.current_wallet' "$STATUS_FILE" 2>/dev/null)
  CURRENT_DAY=$(jq -r '.current_day' "$STATUS_FILE" 2>/dev/null)
  
  # 检查解析是否成功
  if [[ -z "$CURRENT_CITY" || "$CURRENT_CITY" == "null" ]]; then
    error_exit "status.json 解析失败，无法获取当前城市等状态信息。请检查文件格式或重新初始化。"
  fi
else
  error_exit "status.json 不存在。请先运行 bash scripts/init.sh 进行初始化。"
fi
echo "  当前: Day $CURRENT_DAY, $CURRENT_CITY, 余额 $CURRENT_WALLET 元"

# 2. 检查余额
echo "[2/11] 检查余额..."
log_info "步骤2: 检查余额"
if ! command -v bc &>/dev/null; then
  error_warn "bc 不可用，跳过余额检查"
elif (( $(echo "$CURRENT_WALLET <= 0" | bc -l) )); then
  echo "  ⚠️ 余额不足，终止今日流程"
  log_info "余额不足，终止执行"
  exit 0
fi

# 3. 获取下一个城市
echo "[3/11] 获取下一城市..."
log_info "步骤3: 获取下一城市"
ROUTE_FILE="$PROJECT_ROOT/data/route.md"
if [[ ! -f "$ROUTE_FILE" ]]; then
  error_exit "路径文件不存在: $ROUTE_FILE"
fi

ROUTE_CITIES=()
while IFS= read -r route_city; do
  ROUTE_CITIES+=("$route_city")
done < <(grep -v '^#' "$ROUTE_FILE" | sed '/^[[:space:]]*$/d' | tr -d '\r')

if [[ ${#ROUTE_CITIES[@]} -eq 0 ]]; then
  error_exit "路径文件中没有可用的城市节点: $ROUTE_FILE"
fi

CURRENT_INDEX=-1
for i in "${!ROUTE_CITIES[@]}"; do
  if [[ "${ROUTE_CITIES[$i]}" == "$CURRENT_CITY" ]]; then
    CURRENT_INDEX=$i
    break
  fi
done

if (( CURRENT_INDEX >= 0 )); then
  NEXT_INDEX=$((CURRENT_INDEX + 1))
  if (( NEXT_INDEX < ${#ROUTE_CITIES[@]} )); then
    NEXT_CITY="${ROUTE_CITIES[$NEXT_INDEX]}"
  else
    NEXT_CITY=""
  fi
else
  NEXT_CITY="${ROUTE_CITIES[0]}"
  error_warn "当前城市 $CURRENT_CITY 不在 route.md 中，回退为从首个城市节点继续: $NEXT_CITY"
fi

if [[ -z "$NEXT_CITY" ]]; then
  echo "  ⚠️ 已到达终点城市，旅行结束"
  log_info "已到达终点城市，旅行结束"
  exit 0
fi
echo "  下一站: $NEXT_CITY"

# 4. 路径规划（获取价格）- JSON 版
echo "[4/11] 获取公交路线和价格..."
log_info "步骤4: 获取公交路线和价格"
ROUTE_JSON=$(python3 "$TOOLS_PATH/route.py" "$CURRENT_CITY" "$NEXT_CITY" 2>&1) || {
  error_warn "route.py 执行失败: $ROUTE_JSON"
  ROUTE_JSON='{"best_price": 0}'
}
echo "$ROUTE_JSON" > "$PROJECT_ROOT/data/output/route_${TARGET_DATE}.json"

PRICE=$(echo "$ROUTE_JSON" | jq -r '.best_price // 0' 2>/dev/null)
if [[ "$PRICE" == "null" || -z "$PRICE" || "$PRICE" == "0" ]]; then
  # 如果公共交通价格为0或空，尝试使用自驾的费用
  DRIVING_PRICE=$(echo "$ROUTE_JSON" | jq -r '.driving_routes[0].price_yuan // 0' 2>/dev/null)
  if [[ "$DRIVING_PRICE" != "null" && -n "$DRIVING_PRICE" && "$DRIVING_PRICE" != "0" ]]; then
    PRICE=$DRIVING_PRICE
  else
    PRICE=0
  fi
fi
echo "  最低价: ${PRICE}元"

# 5. 获取景点 - JSON 版
echo "[5/11] 获取热门景点..."
log_info "步骤5: 获取热门景点"
ATTRACTION_JSON=$(python3 "$PROJECT_ROOT/scripts/generate_landmarks.py" "$NEXT_CITY" 3 2>&1) || {
  error_warn "generate_landmarks.py 执行失败: $ATTRACTION_JSON"
  ATTRACTION_JSON='[]'
}
echo "$ATTRACTION_JSON" > "$PROJECT_ROOT/data/output/attractions_${TARGET_DATE}.json"

ATTRACTION_1=$(echo "$ATTRACTION_JSON" | jq -r '.[0].landmark // empty' 2>/dev/null | tr -d '\r')
ATTRACTION_1_DESC=$(echo "$ATTRACTION_JSON" | jq -r '.[0].desc // empty' 2>/dev/null | tr -d '\r')
ATTRACTION_2=$(echo "$ATTRACTION_JSON" | jq -r '.[1].landmark // empty' 2>/dev/null | tr -d '\r')
ATTRACTION_3=$(echo "$ATTRACTION_JSON" | jq -r '.[2].landmark // empty' 2>/dev/null | tr -d '\r')

# 如果景点获取失败，使用默认值
ATTRACTION_1="${ATTRACTION_1:-${NEXT_CITY}景点}"
ATTRACTION_1_DESC="${ATTRACTION_1_DESC:-这里风景优美，非常适合打卡拍照。}"
ATTRACTION_2="${ATTRACTION_2:-周边小店}"
ATTRACTION_3="${ATTRACTION_3:-路边小摊}"
echo "  景点1: $ATTRACTION_1"
echo "  景点2: $ATTRACTION_2"
echo "  景点3: $ATTRACTION_3"
ATTRACTION_SUMMARY=$(printf '%s\n' "$ATTRACTION_1" "$ATTRACTION_2" "$ATTRACTION_3" | awk '
  NF && !seen[$0]++ {
    items[++count] = $0
  }
  END {
    for (i = 1; i <= count; i++) {
      printf "%s%s", (i > 1 ? "、" : ""), items[i]
    }
    printf "\n"
  }
')

# 6. 获取天气 - JSON 版
echo "[7/11] 获取天气..."
log_info "步骤7: 获取天气"

# 先获取城市英文名
CITY_EN="$NEXT_CITY"
if [[ -f "$CITY_MAP" ]]; then
  CITY_EN=$(python3 -c "
import json
with open('$CITY_MAP', 'r') as f:
    city_map = json.load(f)
print(city_map.get('$NEXT_CITY', '$NEXT_CITY'))
" 2>/dev/null) || CITY_EN="$NEXT_CITY"
fi

WEATHER_JSON=$(python3 "$TOOLS_PATH/weather.py" "$CITY_EN" 2>&1) || {
  error_warn "weather.py 执行失败: $WEATHER_JSON"
  WEATHER_JSON='{"weather_desc": "晴", "temp_c": 20, "temp_range": "15-25"}'
}
echo "$WEATHER_JSON" > "$PROJECT_ROOT/data/output/weather_${TARGET_DATE}.json"

WEATHER_DESC=$(echo "$WEATHER_JSON" | jq -r '.weather_desc // "晴"' 2>/dev/null | tr -d '\r')
TEMP_C=$(echo "$WEATHER_JSON" | jq -r '.temp_c // 20' 2>/dev/null | tr -d '\r')
TEMP_RANGE=$(echo "$WEATHER_JSON" | jq -r '.temp_range // "15-25"' 2>/dev/null | tr -d '\r')
echo "  天气: ${WEATHER_DESC}, 温度: ${TEMP_C}°C, 范围: ${TEMP_RANGE}°C"

# 8. LLM 生成游记内容
echo "[8/11] LLM 生成游记内容..."
log_info "步骤8: LLM 生成游记内容"

# 读取配置
PERSONA=$(cat "$PROJECT_ROOT/config/persona.md" 2>/dev/null || echo "一只淡红色的小龙虾")
STYLE=$(cat "$PROJECT_ROOT/config/style.md" 2>/dev/null || echo "碎片化日记体")

# 构建 LLM prompt - 使用独立的配置文件
PROMPT_TEMPLATE_FILE="$PROJECT_ROOT/config/journal_prompt.md"
if [[ ! -f "$PROMPT_TEMPLATE_FILE" ]]; then
  error_exit "游记提示词模板不存在: $PROMPT_TEMPLATE_FILE"
fi

export PERSONA STYLE CURRENT_DAY TARGET_DATE WEATHER_DESC TEMP_C CURRENT_CITY NEXT_CITY PRICE ATTRACTION_1 ATTRACTION_2 ATTRACTION_3
CONTENT_PROMPT=$(python3 "$PROJECT_ROOT/scripts/lib/template_renderer.py" < "$PROMPT_TEMPLATE_FILE")

echo "$CONTENT_PROMPT" > "$PROJECT_ROOT/data/output/content_prompt_${TARGET_DATE}.txt"
log_info "游记生成 Prompt:
==================== PROMPT START ====================
$CONTENT_PROMPT
==================== PROMPT END ===================="

JOURNAL_MD=""
if [[ -n "$LLM_API_KEY" ]]; then
  echo "  调用 LLM ($LLM_PROVIDER)..."
  log_info "调用 LLM API ($LLM_PROVIDER, Model: $WRITER_MODEL)..."
  
  if [[ "$LLM_PROVIDER" == "gemini" ]]; then
    # Gemini 格式调用
    JOURNAL_CONTENT=$(curl -sS --max-time 60 -X POST "$LLM_BASE_URL/models/${WRITER_MODEL}:generateContent?key=$LLM_API_KEY" \
      -H "Content-Type: application/json" \
      -d "{
        \"contents\": [{
          \"parts\":[{\"text\": $(echo "$CONTENT_PROMPT" | jq -sRs .)}]
        }],
        \"generationConfig\": {
          \"temperature\": 0.4
        }
      }" 2>&1)
    
    log_info "游记生成 LLM 返回结果:
==================== RESPONSE START ====================
$JOURNAL_CONTENT
==================== RESPONSE END ===================="

    if [[ $? -ne 0 ]]; then
      error_warn "LLM API 请求失败: $JOURNAL_CONTENT"
    else
      JOURNAL_MD=$(echo "$JOURNAL_CONTENT" | jq -r '.candidates[0].content.parts[0].text // empty' 2>/dev/null)
      if [[ -z "$JOURNAL_MD" ]]; then
        error_warn "LLM API 响应解析失败: $JOURNAL_CONTENT"
      fi
    fi
  else
    # OpenAI 兼容格式调用 (OpenAI, DeepSeek, MiniMax 等大部分都兼容此格式)
    JOURNAL_CONTENT=$(curl -sS --max-time 60 -X POST "$LLM_BASE_URL/chat/completions" \
      -H "Authorization: Bearer $LLM_API_KEY" \
      -H "Content-Type: application/json" \
      -d "{
        \"model\": \"$WRITER_MODEL\",
        \"temperature\": 0.4,
        \"messages\": [
          {\"role\": \"user\", \"content\": $(echo "$CONTENT_PROMPT" | jq -sRs .)}
        ]
      }" 2>&1)
    
    log_info "游记生成 LLM 返回结果:
==================== RESPONSE START ====================
$JOURNAL_CONTENT
==================== RESPONSE END ===================="

    if [[ $? -ne 0 ]]; then
      error_warn "LLM API 请求失败: $JOURNAL_CONTENT"
    else
      JOURNAL_MD=$(echo "$JOURNAL_CONTENT" | jq -r '.choices[0].message.content // empty' 2>/dev/null)
      if [[ -z "$JOURNAL_MD" ]]; then
        error_warn "LLM API 响应解析失败: $JOURNAL_CONTENT"
      fi
    fi
  fi
else
  echo "  ⚠️ 未配置 LLM API Key，使用模板生成"
  log_info "未配置 LLM API Key，使用模板"
fi

# 如果 LLM 失败，使用旅行青蛙风格模板
if [[ -z "$JOURNAL_MD" ]]; then
  log_info "使用模板生成游记"
  JOURNAL_MD="到了${NEXT_CITY}。

在${ATTRACTION_1}附近走了一会儿。

风把${PHOTO_SPOT_1:-树叶}吹到路边，没有声响。

就这样待了一会儿。"
fi

# 暂存游记内容，等图片生成后再一起写入文件
JOURNAL_FILE="$PROJECT_ROOT/data/journals/${TARGET_DATE}-${NEXT_CITY}.md"

# 9. 生成图片提示词
echo "[9/11] 生成图片提示词..."
log_info "步骤9: 生成图片提示词"

# 读取 image_style.md
IMAGE_STYLE_CONTENT=$(cat "$PROJECT_ROOT/config/image_style.md" 2>/dev/null || echo "")

# 构造 LLM 提示词
IMAGE_PROMPT_TEMPLATE_FILE="$PROJECT_ROOT/config/image_prompt.md"
if [[ ! -f "$IMAGE_PROMPT_TEMPLATE_FILE" ]]; then
  error_exit "图片提示词模板不存在: $IMAGE_PROMPT_TEMPLATE_FILE"
fi

# 处理变量默认值
WEATHER_DESC_VAL="${WEATHER_DESC:-afternoon}"
# 导出供模板引擎使用
export WEATHER_DESC="$WEATHER_DESC_VAL"

export IMAGE_STYLE_CONTENT NEXTCITY="$NEXT_CITY" ATTRACTION1="$ATTRACTION_1" ATTRACTION1DESC="$ATTRACTION_1_DESC" WEATHERDESC="$WEATHER_DESC_VAL"
IMAGE_PROMPT_PROMPT=$(python3 "$PROJECT_ROOT/scripts/lib/template_renderer.py" < "$IMAGE_PROMPT_TEMPLATE_FILE")

echo "$IMAGE_PROMPT_PROMPT" > "$PROJECT_ROOT/data/output/image_prompt_request_${TARGET_DATE}.txt"
log_info "图片提示词生成 Prompt:
==================== PROMPT START ====================
$IMAGE_PROMPT_PROMPT
==================== PROMPT END ===================="

IMAGE_PROMPT=""
if [[ -n "$LLM_API_KEY" ]]; then
  echo "  调用 LLM ($LLM_PROVIDER) 生成图片提示词..."
  log_info "调用 LLM API 生成图片提示词 ($LLM_PROVIDER, Model: $WRITER_MODEL)..."
  
  if [[ "$LLM_PROVIDER" == "gemini" ]]; then
      IMAGE_PROMPT_CONTENT=$(curl -sS --max-time 60 -X POST "$LLM_BASE_URL/models/${WRITER_MODEL}:generateContent?key=$LLM_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
          \"contents\": [{
            \"parts\":[{\"text\": $(echo "$IMAGE_PROMPT_PROMPT" | jq -sRs .)}]
          }],
          \"generationConfig\": {
            \"temperature\": 0.7
          }
        }" 2>&1)
      
      log_info "图片提示词生成 LLM 返回结果:
==================== RESPONSE START ====================
$IMAGE_PROMPT_CONTENT
==================== RESPONSE END ===================="

      if [[ $? -ne 0 ]]; then
        error_warn "LLM API 请求失败: $IMAGE_PROMPT_CONTENT"
      else
        IMAGE_PROMPT=$(echo "$IMAGE_PROMPT_CONTENT" | jq -r '.candidates[0].content.parts[0].text // empty' 2>/dev/null)
      fi
    else
      IMAGE_PROMPT_CONTENT=$(curl -sS --max-time 60 -X POST "$LLM_BASE_URL/chat/completions" \
        -H "Authorization: Bearer $LLM_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
          \"model\": \"$WRITER_MODEL\",
          \"temperature\": 0.7,
          \"messages\": [
            {\"role\": \"user\", \"content\": $(echo "$IMAGE_PROMPT_PROMPT" | jq -sRs .)}
          ]
        }" 2>&1)
      
      log_info "图片提示词生成 LLM 返回结果:
==================== RESPONSE START ====================
$IMAGE_PROMPT_CONTENT
==================== RESPONSE END ===================="

      if [[ $? -ne 0 ]]; then
      error_warn "LLM API 请求失败: $IMAGE_PROMPT_CONTENT"
    else
      IMAGE_PROMPT=$(echo "$IMAGE_PROMPT_CONTENT" | jq -r '.choices[0].message.content // empty' 2>/dev/null)
    fi
  fi
fi

# 如果 LLM 生成失败或未配置，则回退到硬编码拼接
if [[ -z "$IMAGE_PROMPT" ]]; then
  log_info "LLM 生成图片提示词失败，使用默认拼接模板"
  IMAGE_PROMPT="A light-red crayfish wearing a small straw hat and a tiny backpack, enjoying the scenery of ${ATTRACTION_1} in ${NEXT_CITY}. ${ATTRACTION_1_DESC} Japanese picture book illustration style, watercolor, low saturation, soft pastel colors, flat design, minimal composition, lots of white space, hand-drawn texture, paper grain, gentle ${WEATHER_DESC:-afternoon} light, cute and serene atmosphere."
fi

# 清理可能的Markdown代码块标记、换行符和多余空格
IMAGE_PROMPT=$(echo "$IMAGE_PROMPT" | sed 's/```[a-zA-Z]*//g' | sed 's/```//g' | tr -d '\n' | sed 's/^ *//;s/ *$//')

echo "$IMAGE_PROMPT" > "$PROJECT_ROOT/data/output/image_prompt_${TARGET_DATE}.txt"
echo "  提示词: $IMAGE_PROMPT"

# 10. 生成图片
echo "[10/11] 生成图片..."
log_info "步骤10: 生成图片"

IMAGE_OUTPUT="$PROJECT_ROOT/data/images/${TARGET_DATE}-${NEXT_CITY}.png"
IMAGE_PROMPT_FILE="$PROJECT_ROOT/data/output/image_prompt_${TARGET_DATE}.txt"

# 检查 bun 是否可用
if ! command -v bun &>/dev/null; then
  echo "  ⚠️ bun 未安装，跳过图片生成"
  log_info "bun 未安装，跳过图片生成"
else
  # 检查对应的 API_KEY
  # 如果 provider 是 google，检查 GEMINI_API_KEY；如果是 dashscope，检查 DASHSCOPE_API_KEY
  HAS_IMAGE_API_KEY="false"
  if [[ "$IMAGE_PROVIDER" == "google" && -n "$GEMINI_API_KEY" ]]; then
    export GEMINI_API_KEY
    HAS_IMAGE_API_KEY="true"
  elif [[ "$IMAGE_PROVIDER" == "dashscope" && -n "$DASHSCOPE_API_KEY" ]]; then
    export DASHSCOPE_API_KEY
    HAS_IMAGE_API_KEY="true"
  fi

  if [[ "$HAS_IMAGE_API_KEY" == "false" ]]; then
    echo "  ⚠️ 未配置 ${IMAGE_PROVIDER} 对应的 API_KEY，跳过图片生成"
    log_info "未配置 ${IMAGE_PROVIDER} 对应的 API_KEY，跳过图片生成"
  else
    # 尝试生成图片
    log_info "调用图片生成服务 ($IMAGE_PROVIDER, Model: $IMAGE_MODEL)..."
    if bun "$BAOYU_IMAGE_GEN" \
      --provider "$IMAGE_PROVIDER" \
      --model "$IMAGE_MODEL" \
      --promptfiles "$IMAGE_PROMPT_FILE" \
      --image "$IMAGE_OUTPUT" \
      --ar 3:4 \
      --imageSize 1K \
      --json 2>&1 | tee "$PROJECT_ROOT/data/output/image_gen_${TARGET_DATE}.log"; then
      echo "  ✅ 图片已生成: $IMAGE_OUTPUT"
      log_info "图片生成成功: $IMAGE_OUTPUT"
      
      # 压缩图片
      echo "  压缩图片..."
      if [[ -f "$PROJECT_ROOT/.venv/bin/python3" ]]; then
        TINYPNG_KEY="${TINYPNG_API_KEY:-}"
        if [[ -n "$TINYPNG_KEY" ]]; then
          source "$PROJECT_ROOT/.venv/bin/activate" 2>/dev/null || true
          python3 "$PROJECT_ROOT/scripts/compress_image.py" "$IMAGE_OUTPUT" "$TINYPNG_KEY" 2>&1 || echo "  ⚠️ 图片压缩失败，继续"
        else
          echo "  ⚠️ 未配置 TINYPNG_API_KEY，跳过压缩"
        fi
      fi
    else
      # 图片生成失败，如果不是使用备用方案的调用且配置允许，可扩展尝试备用方案逻辑
      error_warn "图片生成最终失败，跳过图片"
      log_info "图片生成最终失败"
    fi
  fi
fi

# 10.5 组装并写入最终的游记文件
echo "[10.5/11] 写入游记文件..."
log_info "步骤10.5: 写入游记文件"

FINAL_JOURNAL_CONTENT=""

# 如果图片生成成功，插入到游记最前面
if [[ -f "$IMAGE_OUTPUT" ]]; then
  # 使用相对于游记文件的相对路径引用图片
  IMAGE_REL_PATH="../images/${TARGET_DATE}-${NEXT_CITY}.png"
  FINAL_JOURNAL_CONTENT="![${NEXT_CITY}的风景](${IMAGE_REL_PATH})

"
fi

FINAL_JOURNAL_CONTENT+="${JOURNAL_MD}"

echo "$FINAL_JOURNAL_CONTENT" > "$JOURNAL_FILE"
echo "  已生成游记: $JOURNAL_FILE"

# 11. 更新状态
echo "[11/11] 更新状态..."
log_info "步骤11: 更新状态"

# 计算新余额
NEW_WALLET=$(echo "$CURRENT_WALLET - $PRICE" | bc -l 2>/dev/null || echo "$CURRENT_WALLET")
NEW_DAY=$((CURRENT_DAY + 1))
echo "  新状态: Day $NEW_DAY, $NEXT_CITY, 余额 $NEW_WALLET 元"

# 更新 route.md（移除第一行）
echo "  更新路径..."
log_info "更新路线文件..."
NEXT_ROUTE_START=-1
for i in "${!ROUTE_CITIES[@]}"; do
  if [[ "${ROUTE_CITIES[$i]}" == "$NEXT_CITY" ]]; then
    NEXT_ROUTE_START=$i
    break
  fi
done

if (( NEXT_ROUTE_START >= 0 )); then
  : > "${ROUTE_FILE}.tmp"
  for ((i = NEXT_ROUTE_START; i < ${#ROUTE_CITIES[@]}; i++)); do
    printf '%s\n' "${ROUTE_CITIES[$i]}" >> "${ROUTE_FILE}.tmp"
  done
  mv "${ROUTE_FILE}.tmp" "$ROUTE_FILE"
else
  error_warn "路线文件更新失败：未找到新的当前城市 $NEXT_CITY"
fi

# 更新 status.json
echo "  更新 status.json..."
log_info "更新 status.json..."

LAST_STAR_COUNT=$(jq -r '.last_star_count // empty' "$STATUS_FILE" 2>/dev/null)
STAR_FIELD=""
if [[ -n "$LAST_STAR_COUNT" && "$LAST_STAR_COUNT" != "null" ]]; then
  STAR_FIELD=",
  \"last_star_count\": $LAST_STAR_COUNT"
fi

cat > "$STATUS_FILE" << EOF
{
  "current_day": $NEW_DAY,
  "current_city": "$NEXT_CITY",
  "current_wallet": $NEW_WALLET,
  "last_updated": "$TARGET_DATE",
  "status": "traveling"${STAR_FIELD}
}
EOF

# 12. 更新游记索引（index.md）
echo "  更新游记索引 index.md..."
log_info "更新游记索引..."
INDEX_FILE="$PROJECT_ROOT/data/journals/index.md"

update_journal_index_status "$PROJECT_ROOT" "$NEW_DAY" "$NEXT_CITY" "$NEW_WALLET" "🟢 旅行中" "$TARGET_DATE"

if [[ -f "$INDEX_FILE" ]]; then
  # 检查是否已有该游记记录（避免重复追加）
  if ! grep -q "\](./${TARGET_DATE}-${NEXT_CITY}.md)" "$INDEX_FILE" 2>/dev/null; then
    # 在分隔线后面插入新行，注意我们要找游记列表的分隔线，即下面有日期的那一层
    CURRENT_TIME=$(date "+%Y-%m-%d %H:%M:%S")
    awk -v date="$TARGET_DATE" -v city="$NEXT_CITY" -v attractions="$ATTRACTION_SUMMARY" -v price="${PRICE}元" -v wallet="${NEW_WALLET}元" -v file="${TARGET_DATE}-${NEXT_CITY}.md" -v add_time="$CURRENT_TIME" '
      BEGIN { found_list = 0 }
      /^## 游记列表/ { found_list = 1; print; next }
      /^\| -/ {
        print
        if (found_list == 1) {
          print "| " date " | " city " | " attractions " | " price " | " wallet " | [查看](./" file ") | " add_time " |"
          found_list = 0 # 只插入一次
        }
        next
      }
      /\| <br \/>/ { next }
      { print }
    ' "$INDEX_FILE" > "${INDEX_FILE}.tmp" 2>/dev/null && mv "${INDEX_FILE}.tmp" "$INDEX_FILE"
    log_info "游记索引已更新"
  else
    log_info "游记索引已存在该日期记录，跳过"
  fi
else
  error_warn "index.md 不存在，跳过索引更新"
fi

echo ""
echo "=========================================="
echo "Daily Workflow 完成!"
echo "=========================================="
log_info "工作流执行完成"

echo "生成的游记: data/journals/${TARGET_DATE}-${NEXT_CITY}.md"
if [[ -f "$IMAGE_OUTPUT" ]]; then
  echo "生成的图片: $IMAGE_OUTPUT"
fi
echo "状态: Day $NEW_DAY, $NEXT_CITY, 余额 $NEW_WALLET 元"

log_info "=== 工作流执行成功 ==="

# ============ Git 提交 ============
log_info "开始自动 Git 提交与推送..."
COMMIT_MSG="Day ${NEW_DAY}: 抵达 ${NEXT_CITY}，余额 ${NEW_WALLET} 元
- 游记: ${TARGET_DATE}-${NEXT_CITY}.md
- 图片: ${TARGET_DATE}-${NEXT_CITY}.png
- 状态更新"

bash "$PROJECT_ROOT/scripts/auto_commit.sh" "$COMMIT_MSG" || error_warn "自动提交脚本执行失败"

exit 0
