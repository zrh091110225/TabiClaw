#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
用法:
  bash scripts/weekly_summary.sh [--env-file path]

说明:
  自动生成最近 7 个自然日（含今天）的时间范围，
  然后调用 scripts/period_summary.sh。
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PERIOD_SUMMARY_SCRIPT="$PROJECT_ROOT/scripts/period_summary.sh"
ENV_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:-}"
      if [[ -z "$ENV_FILE" ]]; then
        echo "--env-file 需要提供路径" >&2
        usage
        exit 1
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

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

CMD=(
  bash "$PERIOD_SUMMARY_SCRIPT"
  --start-date "$START_DATE"
  --end-date "$END_DATE"
)

if [[ -n "$ENV_FILE" ]]; then
  CMD+=(--env-file "$ENV_FILE")
fi

"${CMD[@]}"
