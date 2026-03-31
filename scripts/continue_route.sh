#!/usr/bin/env bash
# 继续规划旅行路径，追加到 route.md
# 用法: bash scripts/continue_route.sh <终点城市>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=/dev/null
source "$PROJECT_ROOT/scripts/lib/config.sh"
load_runtime_config "$PROJECT_ROOT"
ROUTE_FILE="$PROJECT_ROOT/data/route.md"

if [ ! -f "$ROUTE_FILE" ]; then
    echo "❌ 找不到路径文件 $ROUTE_FILE，请先使用 replan_route.sh 进行初始规划"
    exit 1
fi

# 获取起点城市：读取 route.md 中最后一个非空、非注释行
START_CITY=$(grep -v "^#" "$ROUTE_FILE" | grep -v "^[[:space:]]*$" | tail -n 1 | awk '{$1=$1;print}')

if [ -z "$START_CITY" ]; then
    echo "❌ 无法从 $ROUTE_FILE 获取最后一个城市，请检查文件格式"
    exit 1
fi

# 获取终点城市
END_CITY="${1:-}"

if [[ -z "$END_CITY" ]]; then
  echo "当前所在城市（起点）: $START_CITY"
  read -p "请输入目的地城市: " END_CITY
fi

if [[ -z "$END_CITY" ]]; then
  echo "❌ 目的地不能为空！"
  echo "用法: bash scripts/continue_route.sh [终点城市]"
  exit 1
fi

echo "=========================================="
echo "继续规划路径: $START_CITY → $END_CITY"
echo "=========================================="

# 调用 route_planner.py 获取 JSON 输出
ROUTE_JSON=$(python3 "$tools_path/route_planner.py" "$START_CITY" "$END_CITY")

# 检查是否成功
SUCCESS=$(echo "$ROUTE_JSON" | jq -r '.success // false')
if [[ "$SUCCESS" != "true" ]]; then
  echo "❌ 路径规划失败: $(echo "$ROUTE_JSON" | jq -r '.error // "未知错误"')"
  exit 1
fi

# 提取城市列表并过滤掉非中文字符（保留中文字符和点号），同时去重
CITIES=$(echo "$ROUTE_JSON" | jq -r '.cities[]' | sed 's/[^一-龥·]//g' | awk 'NF && !seen[$0]++')

if [ -z "$CITIES" ]; then
  CITY_COUNT=0
else
  CITY_COUNT=$(echo "$CITIES" | wc -l | tr -d ' ')
fi
TOTAL_DISTANCE=$(echo "$ROUTE_JSON" | jq -r '.total_distance_km')
ESTIMATED_HOURS=$(echo "$ROUTE_JSON" | jq -r '.estimated_hours')

echo ""
echo "新增规划结果:"
echo "  经过城市数: $CITY_COUNT"
echo "  新增距离: ${TOTAL_DISTANCE}km"
echo "  新增时长: ${ESTIMATED_HOURS}小时"
echo ""
echo "新增城市路径:"
echo "---"

# 追加写入 route.md
echo "" >> "$ROUTE_FILE"
echo "# --- 继续规划 ---" >> "$ROUTE_FILE"
echo "# 起点: $START_CITY" >> "$ROUTE_FILE"
echo "# 终点: $END_CITY" >> "$ROUTE_FILE"
echo "# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$ROUTE_FILE"
echo "# 新增距离: ${TOTAL_DISTANCE}km | 新增预计时长: ${ESTIMATED_HOURS}小时" >> "$ROUTE_FILE"
echo "" >> "$ROUTE_FILE"

# 添加城市列表，跳过第一个（如果与当前最后城市相同）
FIRST_CITY=true
for city in $CITIES; do
  if [ "$FIRST_CITY" = true ]; then
    FIRST_CITY=false
    if [ "$city" = "$START_CITY" ]; then
      echo "  - $city (起点，已存在，跳过写入)"
      continue
    fi
  fi
  echo "$city" >> "$ROUTE_FILE"
  echo "  - $city"
done

echo ""
echo "=========================================="
echo "✅ 新增路径已追加到: $ROUTE_FILE"
echo "=========================================="

# 自动提交到 Git
echo "开始自动 Git 提交与推送..."
bash "$SCRIPT_DIR/auto_commit.sh" "继续规划路径: $START_CITY → $END_CITY"
