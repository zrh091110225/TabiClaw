#!/usr/bin/env bash
# 重新规划旅行路径
# 用法: bash scripts/replan_route.sh <起点城市> <终点城市>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=/dev/null
source "$PROJECT_ROOT/scripts/lib/config.sh"
load_runtime_config "$PROJECT_ROOT"
ROUTE_FILE="$PROJECT_ROOT/data/route.md"

# 解析参数
START_CITY="${1:-}"
END_CITY="${2:-}"

if [[ -z "$START_CITY" || -z "$END_CITY" ]]; then
  echo "用法: bash scripts/replan_route.sh <起点城市> <终点城市> [--reset]"
  echo "示例: bash scripts/replan_route.sh 杭州 北京"
  echo "示例: bash scripts/replan_route.sh 杭州 北京 --reset  # 同时重置状态"
  exit 1
fi

echo "=========================================="
echo "重新规划路径: $START_CITY → $END_CITY"
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
echo "规划结果:"
echo "  经过城市数: $CITY_COUNT"
echo "  总距离: ${TOTAL_DISTANCE}km"
echo "  预计时长: ${ESTIMATED_HOURS}小时"
echo ""
echo "城市路径:"
echo "---"

# 写入 route.md
echo "# 城市路径列表（自动生成）" > "$ROUTE_FILE"
echo "# 起点: $START_CITY" >> "$ROUTE_FILE"
echo "# 终点: $END_CITY" >> "$ROUTE_FILE"
echo "# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$ROUTE_FILE"
echo "# 总距离: ${TOTAL_DISTANCE}km | 预计时长: ${ESTIMATED_HOURS}小时" >> "$ROUTE_FILE"
echo "" >> "$ROUTE_FILE"

# 添加起始城市
echo "  - $START_CITY"
echo "$START_CITY" >> "$ROUTE_FILE"

# 添加中间城市列表（如果包含起始或终点城市则跳过，避免重复）
for city in $CITIES; do
  if [[ "$city" != "$START_CITY" && "$city" != "$END_CITY" ]]; then
    echo "  - $city"
    echo "$city" >> "$ROUTE_FILE"
  fi
done

# 添加终点城市（如果和起点不同）
if [[ "$START_CITY" != "$END_CITY" ]]; then
  echo "  - $END_CITY"
  echo "$END_CITY" >> "$ROUTE_FILE"
fi

echo ""
echo "=========================================="
echo "✅ 路径已保存到: $ROUTE_FILE"
echo "=========================================="

# 可选：重置当前状态（使用 --reset 标志）
RESET_STATUS=false
if [[ "$#" -ge 3 && "${3:-}" == "--reset" ]]; then
  RESET_STATUS=true
fi

if [[ "$RESET_STATUS" == "true" ]]; then
  cat > "$PROJECT_ROOT/data/status.json" << EOF
{
  "current_day": 1,
  "current_city": "$START_CITY",
  "current_wallet": 1000,
  "last_updated": "$(date +%Y-%m-%d)",
  "status": "ready"
}
EOF
  echo "✅ 状态已重置（Day=1, 余额=1000元）"

  update_journal_index_status "$PROJECT_ROOT" "1" "$START_CITY" "1000" "⚪ 未开始" "$(date +%Y-%m-%d)"
  echo "✅ index.md 状态已更新"
fi

# 自动提交到 Git
echo "开始自动 Git 提交与推送..."
bash "$SCRIPT_DIR/auto_commit.sh" "重新规划路径: $START_CITY → $END_CITY"
