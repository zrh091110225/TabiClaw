#!/usr/bin/env bash

load_runtime_config() {
  local project_root="$1"
  local settings_file="$project_root/config/settings.yaml"

  tools_path="${tools_path:-$HOME/.openclaw/workspace/tools}"
  city_map_file="${city_map_file:-$project_root/config/city_map.json}"
  image_gen_script="${image_gen_script:-$HOME/.openclaw/workspace/skills/baoyu-skills/skills/baoyu-image-gen/scripts/main.ts}"

  llm_provider_default="${llm_provider_default:-minimax}"
  llm_base_url_default="${llm_base_url_default:-https://api.minimax.chat/v1}"
  writer_model_default="${writer_model_default:-MiniMax-Text-01}"
  image_provider_default="${image_provider_default:-google}"
  image_model_default="${image_model_default:-gemini-3.1-flash-image-preview}"
  summary_image_mode_default="${summary_image_mode_default:-single_pass}"

  git_auto_push="${git_auto_push:-true}"

  if [[ -f "$settings_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$settings_file"
    set +a
  fi

  if [[ "$city_map_file" == ./* ]]; then
    city_map_file="$project_root/${city_map_file#./}"
  fi
}

ensure_journal_index() {
  local project_root="$1"
  local day="$2"
  local city="$3"
  local wallet="$4"
  local status_label="$5"
  local last_updated="$6"
  local intro_text="${7:-阿虾的环游中国旅行记录。}"
  local index_file="$project_root/data/journals/index.md"

  mkdir -p "$(dirname "$index_file")"
  if [[ -f "$index_file" ]]; then
    return 0
  fi

  cat > "$index_file" <<EOF
# 每日游记索引

${intro_text}

## 当前状态

| 指标 | 值 |
| ---- | ---- |
| Day | $day |
| 当前城市 | $city |
| 余额 | ${wallet} 元 |
| 状态 | $status_label |

## 游记列表

| 日期     | 城市     | 景点信息 | 交通费    | 余额     | 链接     | 添加时间 |
| ------ | ------ | ------ | ------ | ------ | ------ | ------ |

***

_最后更新: ${last_updated}_
EOF
}

update_journal_index_status() {
  local project_root="$1"
  local day="$2"
  local city="$3"
  local wallet="$4"
  local status_label="$5"
  local last_updated="$6"
  local index_file="$project_root/data/journals/index.md"

  ensure_journal_index "$project_root" "$day" "$city" "$wallet" "$status_label" "$last_updated"

  if ! grep -q '^## 当前状态$' "$index_file" 2>/dev/null; then
    awk -v day="$day" -v city="$city" -v wallet="$wallet" -v status_label="$status_label" '
      /^## 游记列表$/ {
        print "## 当前状态"
        print ""
        print "| 指标 | 值 |"
        print "| ---- | ---- |"
        print "| Day | " day " |"
        print "| 当前城市 | " city " |"
        print "| 余额 | " wallet " 元 |"
        print "| 状态 | " status_label " |"
        print ""
        print
        next
      }
      { print }
    ' "$index_file" > "${index_file}.tmp" && mv "${index_file}.tmp" "$index_file"
  fi

  sed -i '' -E "s#^\\| Day \\| [^|]* \\|\$#| Day | ${day} |#" "$index_file" 2>/dev/null || true
  sed -i '' -E "s#^\\| 当前城市 \\| [^|]* \\|\$#| 当前城市 | ${city} |#" "$index_file" 2>/dev/null || true
  sed -i '' -E "s#^\\| 余额 \\| [^|]* \\|\$#| 余额 | ${wallet} 元 |#" "$index_file" 2>/dev/null || true
  sed -i '' -E "s#^\\| 状态 \\| [^|]* \\|\$#| 状态 | ${status_label} |#" "$index_file" 2>/dev/null || true
  sed -i '' -E "s/_最后更新: [0-9-]+/_最后更新: ${last_updated}/" "$index_file" 2>/dev/null || true
}
