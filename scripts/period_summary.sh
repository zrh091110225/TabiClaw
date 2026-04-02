#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
用法:
  bash scripts/period_summary.sh --start-date YYYY-MM-DD --end-date YYYY-MM-DD [--env-file path]
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=/dev/null
source "$PROJECT_ROOT/scripts/lib/config.sh"
load_runtime_config "$PROJECT_ROOT"

START_DATE=""
END_DATE=""
ENV_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-date)
      START_DATE="${2:-}"
      shift 2
      ;;
    --end-date)
      END_DATE="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
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

if [[ -z "$START_DATE" || -z "$END_DATE" ]]; then
  echo "必须同时提供 --start-date 和 --end-date" >&2
  usage
  exit 1
fi

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "指定的配置文件不存在: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
elif [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/.env"
  set +a
fi

mkdir -p "$PROJECT_ROOT/data/output/summaries"
mkdir -p "$PROJECT_ROOT/data/images/summaries"
mkdir -p "$PROJECT_ROOT/data/summaries"

python3 "$PROJECT_ROOT/scripts/generate_period_summary.py" \
  --project-root "$PROJECT_ROOT" \
  --start-date "$START_DATE" \
  --end-date "$END_DATE"
