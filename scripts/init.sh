#!/usr/bin/env bash
# TabiClaw 初始化检查脚本
# 检查所有配置文件是否完整

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=/dev/null
source "$PROJECT_ROOT/scripts/lib/config.sh"
load_runtime_config "$PROJECT_ROOT"

echo "=========================================="
echo "TabiClaw 初始化检查"
echo "=========================================="

CONFIG_DIR="$PROJECT_ROOT/config"
DATA_DIR="$PROJECT_ROOT/data"

# 检查配置文件
echo ""
echo "检查配置文件..."

check_file() {
  local file="$1"
  local name="$2"
  if [[ -f "$file" ]]; then
    echo "  ✅ $name"
    return 0
  else
    echo "  ❌ $name (缺失)"
    return 1
  fi
}

MISSING=0
check_file "$CONFIG_DIR/persona.md" "人设配置 (persona.md)" || MISSING=1
check_file "$CONFIG_DIR/style.md" "文风配置 (style.md)" || MISSING=1
check_file "$CONFIG_DIR/image_style.md" "图片风格配置 (image_style.md)" || MISSING=1
check_file "$CONFIG_DIR/settings.yaml" "基本配置 (settings.yaml)" || MISSING=1

echo ""
echo "检查运行时数据..."

check_file "$DATA_DIR/route.md" "城市路径 (route.md)" || MISSING=1

# 检查工具脚本
echo ""
echo "检查工具脚本..."

check_file "$tools_path/route.py" "路线查询工具 (route.py)" || MISSING=1
check_file "$tools_path/attractions.py" "景点查询工具 (attractions.py)" || MISSING=1
check_file "$tools_path/photo_spots.py" "打卡点查询工具 (photo_spots.py)" || MISSING=1
check_file "$tools_path/weather.py" "天气查询工具 (weather.py)" || MISSING=1
check_file "$city_map_file" "城市映射 (city_map.json)" || MISSING=1

echo ""
if [[ $MISSING -eq 1 ]]; then
  echo "⚠️  有配置文件缺失，请补充后再运行"
  exit 1
else
  echo "✅ 所有配置文件完整!"
  
  # 显示当前状态
  echo ""
  echo "当前状态:"
  if [[ -f "$DATA_DIR/status.json" ]]; then
    cat "$DATA_DIR/status.json"
  else
    echo "  (首次运行，正在从 settings.yaml 初始化 status.json ...)"
    
    # 从 settings.yaml 读取初始配置
    INIT_WALLET=$(grep -E "^wallet_initial=" "$CONFIG_DIR/settings.yaml" | cut -d'=' -f2 || echo "10000")
    INIT_DAY=$(grep -E "^current_day=" "$CONFIG_DIR/settings.yaml" | cut -d'=' -f2 || echo "1")
    INIT_CITY=$(grep -E "^start_city=" "$CONFIG_DIR/settings.yaml" | cut -d'=' -f2 || echo "杭州")
    
    # 确保 data 目录存在
    mkdir -p "$DATA_DIR"
    
    # 生成 status.json
    cat > "$DATA_DIR/status.json" << EOF
{
  "current_day": $INIT_DAY,
  "current_city": "$INIT_CITY",
  "current_wallet": $INIT_WALLET,
  "last_updated": "$(date +%Y-%m-%d)",
  "status": "ready"
}
EOF
    echo "  ✅ status.json 初始化完成:"
    cat "$DATA_DIR/status.json"
  fi
  
  echo ""
  echo "城市路径:"
  if [[ -f "$DATA_DIR/route.md" ]]; then
    cat "$DATA_DIR/route.md"
  fi
fi
