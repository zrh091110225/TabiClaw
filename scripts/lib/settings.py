#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path


DEFAULTS = {
    "tools_path": "${HOME}/.openclaw/workspace/tools",
    "city_map_file": "./config/city_map.json",
    "image_gen_script": "${HOME}/.openclaw/workspace/skills/baoyu-skills/skills/baoyu-image-gen/scripts/main.ts",
    "llm_provider_default": "minimax",
    "llm_base_url_default": "https://api.minimax.chat/v1",
    "writer_model_default": "MiniMax-Text-01",
    "image_provider_default": "google",
    "image_model_default": "gemini-3.1-flash-image-preview",
    "git_auto_push": "true",
}


def load_runtime_settings(project_root: str | Path) -> dict[str, str]:
    project_root = Path(project_root)
    settings_path = project_root / "config" / "settings.yaml"
    values = dict(DEFAULTS)

    if settings_path.exists():
        with settings_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key not in DEFAULTS:
                    continue
                values[key] = value.strip().strip('"').strip("'")

    expanded = dict(values)
    changed = True
    while changed:
        changed = False
        env = dict(os.environ)
        env.update(expanded)
        for key, value in list(expanded.items()):
            resolved = os.path.expandvars(value)
            if resolved != expanded[key]:
                expanded[key] = resolved
                changed = True

    city_map_value = expanded.get("city_map_file")
    if city_map_value and city_map_value.startswith("./"):
        expanded["city_map_file"] = str(project_root / city_map_value)

    return expanded
