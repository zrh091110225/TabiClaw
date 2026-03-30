#!/usr/bin/env bash
# 清理 RoamShrimp 数据脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"

echo "=========================================="
echo "清理 RoamShrimp 数据"
echo "=========================================="

# 1. 删除 images 和 journals 目录下的文件
echo "正在清理 images 目录..."
rm -rf "$DATA_DIR/images"/*

echo "正在清理 journals 目录..."
rm -rf "$DATA_DIR/journals"/*

# 重新创建 index.md，保持表头
cat > "$DATA_DIR/journals/index.md" << EOF
# 每日游记索引

阿虾的10000元环游中国旅行记录。

## 游记列表

| 日期 | 城市 | 交通费 | 余额 | 链接 |
|------|------|--------|------|------|

---

_最后更新: $(date +%Y-%m-%d)_
EOF
echo "✅ images 和 journals 目录下的文件已删除，并重建了 journals/index.md"

# 2. 清空 route.md
echo "正在清空 route.md..."
> "$DATA_DIR/route.md"
echo "✅ route.md 已清空"

# 3. 重置 README.md 状态部分
echo "正在重置 README.md 状态部分..."
if [[ -f "$PROJECT_ROOT/README.md" ]]; then
  sed -i '' "s/| Day | [0-9]*/| Day | 0/" "$PROJECT_ROOT/README.md" 2>/dev/null || true
  sed -i '' "s/| 当前城市 | [^|]*/| 当前城市 | 未知 /" "$PROJECT_ROOT/README.md" 2>/dev/null || true
  sed -i '' "s/| 余额 | [-0-9.]* 元/| 余额 | 10000 元/" "$PROJECT_ROOT/README.md" 2>/dev/null || true
  sed -i '' "s/| 状态 | .*/| 状态 | ⚪ 未开始 |/" "$PROJECT_ROOT/README.md" 2>/dev/null || true
  echo "✅ README.md 状态部分已重置"
fi

# 4. 重置 status.json
echo "正在重置 status.json..."
cat > "$DATA_DIR/status.json" << EOF
{
  "current_day": 0,
  "current_city": "未知",
  "current_wallet": 10000,
  "last_updated": "$(date +%Y-%m-%d)",
  "status": "ready"
}
EOF
echo "✅ status.json 已重置"

echo "=========================================="
echo "清理完成！"
echo "=========================================="
