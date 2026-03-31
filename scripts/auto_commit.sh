#!/usr/bin/env bash
# 自动检查文件变更、Git 提交和推送脚本
# 用法: bash scripts/auto_commit.sh [提交信息]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=/dev/null
source "$PROJECT_ROOT/scripts/lib/config.sh"
load_runtime_config "$PROJECT_ROOT"

# 日志输出函数
log_info() {
  echo "[INFO] $1"
}

error_warn() {
  echo "[WARN] $1" >&2
}

# 解析参数
COMMIT_MSG="${1:-Auto commit: update project files}"

cd "$PROJECT_ROOT"

# 添加所有变更（包括新增、修改和删除的文件）
git add -A

# 检查是否有暂存的变更需要提交
if git diff --staged --quiet; then
  log_info "没有变更需要提交"
  exit 0
fi

log_info "发现文件变更，开始 Git 提交..."

# 提交变更
if git commit -m "$COMMIT_MSG"; then
  log_info "Git 提交成功: $COMMIT_MSG"
else
  error_warn "Git 提交失败"
  exit 1
fi

if [[ "$git_auto_push" == "true" ]]; then
  log_info "开始推送到远程仓库..."
  if git push; then
    log_info "✅ 已成功推送到远程仓库"
  else
    error_warn "❌ Git 推送失败"
    exit 1
  fi
else
  log_info "已通过 config/settings.yaml 关闭自动推送，跳过 git push"
fi
