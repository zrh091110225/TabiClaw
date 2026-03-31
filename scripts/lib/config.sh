#!/usr/bin/env bash

load_runtime_config() {
  local project_root="$1"
  local settings_file="$project_root/config/settings.yaml"

  tools_path="${tools_path:-$HOME/.openclaw/workspace/tools}"
  city_map_file="${city_map_file:-$tools_path/city_map.json}"
  image_gen_script="${image_gen_script:-$HOME/.openclaw/workspace/skills/baoyu-skills/skills/baoyu-image-gen/scripts/main.ts}"

  llm_provider_default="${llm_provider_default:-minimax}"
  llm_base_url_default="${llm_base_url_default:-https://api.minimax.chat/v1}"
  writer_model_default="${writer_model_default:-MiniMax-Text-01}"
  image_provider_default="${image_provider_default:-google}"
  image_model_default="${image_model_default:-gemini-3.1-flash-image-preview}"

  git_auto_push="${git_auto_push:-true}"

  if [[ -f "$settings_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$settings_file"
    set +a
  fi
}
