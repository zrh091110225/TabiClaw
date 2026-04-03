#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
用法:
  bash scripts/weekly_summary.sh

说明:
  自动生成最近 7 个自然日（含今天）的时间范围，
  然后调用 scripts/period_summary.sh。
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PERIOD_SUMMARY_SCRIPT="$PROJECT_ROOT/scripts/period_summary.sh"

if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "weekly_summary.sh 不接受参数" >&2
      usage
      exit 1
      ;;
  esac
fi

if [[ ! -f "$PERIOD_SUMMARY_SCRIPT" ]]; then
  echo "缺少底层脚本: $PERIOD_SUMMARY_SCRIPT" >&2
  exit 1
fi

read -r START_DATE END_DATE <<EOF
$(python3 - <<'PY'
import datetime as dt

end_date = dt.date.today()
start_date = end_date - dt.timedelta(days=6)
print(start_date.isoformat(), end_date.isoformat())
PY
)
EOF

echo "生成周总结时间范围: ${START_DATE} -> ${END_DATE}"

bash "$PERIOD_SUMMARY_SCRIPT" \
  --start-date "$START_DATE" \
  --end-date "$END_DATE"
