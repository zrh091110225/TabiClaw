#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.settings import load_runtime_settings
from lib.template_renderer import render_template


JOURNAL_FILE_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<city>.+)\.md$")
LINK_RE = re.compile(r"\[查看\]\(\./(?P<file>[^)]+)\)")
ATTRACTIONS_LINE_RE = re.compile(r"经过的景点：(?P<attractions>.+?)。")
GENERIC_ATTRACTION_NAMES = {
    "周边小店",
    "路边小摊",
    "当地小店",
    "街边小店",
    "周边街景",
    "城市街景",
}
JOURNAL_ATTRACTION_CANDIDATES = [
    "西湖",
    "灵隐寺",
    "雷峰塔",
    "南京的城墙",
    "城墙",
    "青灰色的砖石",
    "石砖",
    "街角小店",
    "路边的长凳",
    "泉水",
    "湖水",
    "湖边的柳树",
    "湖边",
    "热茶",
    "石头",
    "石桥",
    "古桥",
    "运河",
    "古寺",
    "古街",
]

CANVAS_SIZE = (1200, 1800)
TOP_MARGIN = 270
BOTTOM_MARGIN = 230
LINE_COLOR = (183, 92, 78, 255)
SOFT_LINE_COLOR = (191, 108, 92, 180)
CARD_FILL = (251, 247, 241, 190)
PAPER_BG = (246, 238, 226, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate period travel summary")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    return parser.parse_args()


def normalize_city_name(name: str) -> str:
    value = name.strip()
    for suffix in ("市", "区", "县", "省"):
        if value.endswith(suffix) and len(value) > 2:
            value = value[: -len(suffix)]
    return value


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_dirs(path.parent)
    path.write_text(content, encoding="utf-8")


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def parse_journal_index(index_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in read_text(index_path).splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) not in {6, 7}:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]):
            continue
        if len(cells) == 7:
            date, city, attractions, price_text, wallet_text, link_text, added_at = cells
        else:
            date, city, price_text, wallet_text, link_text, added_at = cells
            attractions = ""
        link_match = LINK_RE.search(link_text)
        if not link_match:
            continue
        price_match = re.match(r"(\d+)元$", price_text)
        wallet_match = re.match(r"(\d+)元$", wallet_text)
        if not price_match or not wallet_match:
            continue
        rows.append(
            {
                "date": date,
                "city": city,
                "attractions": attractions,
                "price": int(price_match.group(1)),
                "wallet": int(wallet_match.group(1)),
                "file": link_match.group("file").strip(),
                "added_at": added_at,
            }
        )
    return rows


def clean_journal_content(raw_text: str) -> str:
    lines = raw_text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if stripped.startswith("![") and "](" in stripped:
            continue
        if re.match(r"^[\u4e00-\u9fffA-Za-z·\s（）()]+[（(]\d{4}-\d{2}-\d{2}[）)]$", stripped):
            continue
        if re.match(r"^交通费：\d+元$", stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def make_excerpt(text: str, limit: int = 88) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit] + ("…" if len(compact) > limit else "")


def parse_attractions_text(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[、,，/]", text) if item.strip()]


def parse_attraction_payload(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    names: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        landmark = str(item.get("landmark", "")).strip()
        if landmark and landmark not in names:
            names.append(landmark)
    return names


def extract_attractions_from_content_prompt(project_root: Path, date: str) -> str:
    prompt_path = project_root / f"data/output/content_prompt_{date}.txt"
    if not prompt_path.exists():
        return ""
    match = ATTRACTIONS_LINE_RE.search(read_text(prompt_path))
    if not match:
        return ""
    return match.group("attractions").strip()


def derive_landmark_from_journal(city: str, journal_text: str) -> str:
    candidates = [
        "城墙",
        "泉水",
        "西湖",
        "雷峰塔",
        "灵隐寺",
        "大明湖",
        "石桥",
        "古桥",
        "运河",
        "古寺",
        "古街",
        "塔",
        "桥",
        "楼",
        "宫",
        "门",
        "园",
        "山",
        "河",
        "湖",
        "街",
    ]
    compact = re.sub(r"\s+", "", journal_text)
    for candidate in candidates:
        if candidate in compact:
            match = re.search(rf"([\u4e00-\u9fff]{{0,6}}{re.escape(candidate)})", compact)
            if match:
                phrase = match.group(1)
                return phrase[-8:]
    return city


def is_generic_attraction(name: str, city: str) -> bool:
    value = name.strip()
    normalized_city = normalize_city_name(city)
    return value in GENERIC_ATTRACTION_NAMES or value in {f"{city}景点", f"{normalized_city}景点"}


def derive_attractions_from_journal(city: str, journal_text: str) -> list[str]:
    compact = re.sub(r"\s+", "", journal_text)
    found: list[str] = []
    for candidate in JOURNAL_ATTRACTION_CANDIDATES:
        if candidate in compact and candidate not in found:
            found.append(candidate)
        if len(found) >= 3:
            break
    if found:
        return found
    landmark = derive_landmark_from_journal(city, journal_text)
    return [landmark] if landmark else []


def attraction_names_are_reliable(
    names: list[str],
    city: str,
    journal_text: str,
    trusted_landmarks: list[str],
) -> bool:
    if not names:
        return False
    compact = re.sub(r"\s+", "", journal_text)
    trusted = set(trusted_landmarks)
    for name in names:
        if is_generic_attraction(name, city):
            continue
        if name in compact or name in trusted:
            return True
    return False


def resolve_attractions(
    project_root: Path,
    row: dict[str, Any],
    journal_text: str,
    trusted_landmarks: list[str],
) -> dict[str, Any]:
    index_text = row.get("attractions", "").strip()
    prompt_text = extract_attractions_from_content_prompt(project_root, row["date"])
    candidates: list[tuple[str, list[str], str]] = []
    if index_text:
        candidates.append(("index", parse_attractions_text(index_text), index_text))
    if prompt_text and prompt_text != index_text:
        candidates.append(("content_prompt", parse_attractions_text(prompt_text), prompt_text))
    if trusted_landmarks:
        candidates.append(("attractions_json", trusted_landmarks, "、".join(trusted_landmarks)))

    for source, names, text in candidates:
        if attraction_names_are_reliable(names, row["city"], journal_text, trusted_landmarks):
            return {
                "names": names,
                "text": text,
                "source": source,
                "raw_index_text": index_text,
            }

    journal_names = derive_attractions_from_journal(row["city"], journal_text)
    if journal_names:
        return {
            "names": journal_names,
            "text": "、".join(journal_names),
            "source": "journal",
            "raw_index_text": index_text,
        }

    fallback_name = derive_landmark_from_journal(row["city"], journal_text)
    fallback_names = [fallback_name] if fallback_name else [row["city"]]
    return {
        "names": fallback_names,
        "text": "、".join(fallback_names),
        "source": "city_fallback",
        "raw_index_text": index_text,
    }


def pick_focus_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(entries) <= 4:
        return entries
    indices = sorted({0, len(entries) - 1, len(entries) // 3, (len(entries) * 2) // 3})
    return [entries[i] for i in indices]


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def append_log(path: Path, message: str) -> None:
    ensure_dirs(path.parent)
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def print_console_block(title: str, content: str) -> None:
    print(f"\n[{title}]")
    print("=" * 72)
    print(content.rstrip())
    print("=" * 72)


def print_console_llm_request(label: str, llm_config: dict[str, str], temperature: float, prompt: str) -> None:
    print(f"  {label} LLM 参数: provider={llm_config['provider']}, model={llm_config['model']}, base_url={llm_config['base_url']}, temperature={temperature}")
    print_console_block(f"{label} LLM Prompt", prompt)


def print_console_image_request(label: str, provider: str, model: str, size: str, prompt: str) -> None:
    print(f"  {label} 图片模型参数: provider={provider}, model={model}, size={size}")
    print_console_block(f"{label} 图片 Prompt", prompt)


def tail_nonempty_line(path: Path) -> str:
    if not path.exists():
        return ""
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    for line in reversed(lines):
        if line and not line.startswith("=== attempt"):
            return line
    return ""


def load_fact_bundle(project_root: Path, start_date: dt.date, end_date: dt.date) -> dict[str, Any]:
    rows = parse_journal_index(project_root / "data/journals/index.md")
    selected = [
        row
        for row in rows
        if start_date <= parse_date(row["date"]) <= end_date
    ]
    selected.sort(key=lambda item: item["date"])
    if not selected:
        raise ValueError("指定时间范围内没有找到游记记录")

    entries: list[dict[str, Any]] = []
    landmarks_by_city: list[dict[str, str]] = []
    weather_by_city: list[dict[str, str]] = []
    journal_excerpts: list[dict[str, str]] = []

    for row in selected:
        journal_path = project_root / "data/journals" / row["file"]
        if not journal_path.exists():
            continue

        file_match = JOURNAL_FILE_RE.match(journal_path.name)
        if not file_match:
            continue

        journal_text = clean_journal_content(read_text(journal_path))
        normalized_city = normalize_city_name(row["city"])
        weather_path = project_root / f"data/output/weather_{row['date']}.json"
        attraction_path = project_root / f"data/output/attractions_{row['date']}.json"

        weather_payload = load_json(weather_path)
        weather_valid = False
        weather_desc = ""
        if isinstance(weather_payload, dict):
            weather_city = normalize_city_name(str(weather_payload.get("city_cn", "")).strip())
            if weather_city and weather_city == normalized_city:
                weather_valid = True
                weather_desc = str(weather_payload.get("weather_desc", "")).strip()
                weather_by_city.append(
                    {
                        "date": row["date"],
                        "city": row["city"],
                        "weather": weather_desc,
                    }
                )

        attraction_payload = load_json(attraction_path)
        trusted_landmarks = parse_attraction_payload(attraction_payload) if weather_valid else []
        resolved_attractions = resolve_attractions(project_root, row, journal_text, trusted_landmarks)
        attractions_text = resolved_attractions["text"]
        attraction_names = resolved_attractions["names"]
        representative_landmark = attraction_names[0] if attraction_names else ""
        if not representative_landmark:
            representative_landmark = derive_landmark_from_journal(row["city"], journal_text)
        if representative_landmark and representative_landmark != row["city"]:
            landmarks_by_city.append(
                {
                    "date": row["date"],
                    "city": row["city"],
                    "landmark": representative_landmark,
                }
            )

        entry = {
            "date": row["date"],
            "city": row["city"],
            "transport_cost": row["price"],
            "wallet": row["wallet"],
            "attractions": attraction_names,
            "attractions_text": attractions_text,
            "attractions_source": resolved_attractions["source"],
            "raw_attractions_text": resolved_attractions["raw_index_text"],
            "journal_file": f"./{row['file']}",
            "journal_path": str(journal_path),
            "summary_path": str(project_root / "data/summaries"),
            "landmark": representative_landmark,
            "weather": weather_desc,
            "excerpt": make_excerpt(journal_text),
            "body": journal_text,
        }
        entries.append(entry)
        journal_excerpts.append(
            {
                "date": row["date"],
                "city": row["city"],
                "excerpt": entry["excerpt"],
            }
        )

    if not entries:
        raise ValueError("时间窗内没有可读取的游记正文")

    ordered_cities = [entry["city"] for entry in entries]
    focus_entries = pick_focus_entries(entries)
    total_transport_cost = sum(entry["transport_cost"] for entry in entries)
    start_wallet = entries[0]["wallet"] + entries[0]["transport_cost"]
    end_wallet = entries[-1]["wallet"]
    wallet_delta = end_wallet - start_wallet
    route_chain_text = " → ".join(ordered_cities)

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days_covered": len(entries),
        "entries": entries,
        "ordered_cities": ordered_cities,
        "city_count": len(ordered_cities),
        "landmarks_by_city": landmarks_by_city,
        "weather_by_city": weather_by_city,
        "total_transport_cost": total_transport_cost,
        "start_wallet": start_wallet,
        "end_wallet": end_wallet,
        "wallet_delta": wallet_delta,
        "journal_excerpts": journal_excerpts,
        "route_chain_text": route_chain_text,
        "focus_entries": focus_entries,
        "representative_landmark_count": len(
            [entry for entry in entries if entry["landmark"] and entry["landmark"] != entry["city"]]
        ),
    }


def strip_code_fences(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", value)
        value = re.sub(r"\n?```$", "", value)
    return value.strip()


def resolve_text_llm_config(settings: dict[str, str]) -> dict[str, str]:
    return {
        "api_key": os.environ.get("LLM_API_KEY", "").strip(),
        "provider": os.environ.get("LLM_PROVIDER", settings["llm_provider_default"]).strip(),
        "base_url": os.environ.get("LLM_BASE_URL", settings["llm_base_url_default"]).strip().rstrip("/"),
        "model": os.environ.get("WRITER_MODEL", settings["writer_model_default"]).strip(),
    }


def call_llm(prompt: str, settings: dict[str, str], temperature: float = 0.55) -> str | None:
    llm_config = resolve_text_llm_config(settings)
    api_key = llm_config["api_key"]
    if not api_key:
        return None

    provider = llm_config["provider"]
    base_url = llm_config["base_url"]
    model = llm_config["model"]

    try:
        if provider == "gemini":
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature},
            }
            request = urllib.request.Request(
                f"{base_url}/models/{model}:generateContent?key={api_key}",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, urllib.error.URLError, json.JSONDecodeError):
        return None


def render_summary_prompt(project_root: Path, fact_bundle: dict[str, Any]) -> str:
    template = read_text(project_root / "config/summary_prompt.md")
    context = {
        "PERSONA": read_text(project_root / "config/persona.md").strip(),
        "STYLE": read_text(project_root / "config/style.md").strip(),
        "FACTSJSON": json.dumps(
            {
                key: value
                for key, value in fact_bundle.items()
                if key not in {"entries", "focus_entries"}
            }
            | {
                "entries": [
                    {
                        "date": entry["date"],
                        "city": entry["city"],
                        "transport_cost": entry["transport_cost"],
                        "wallet": entry["wallet"],
                        "attractions": entry["attractions"],
                        "attractions_text": entry["attractions_text"],
                        "attractions_source": entry["attractions_source"],
                        "landmark": entry["landmark"],
                        "weather": entry["weather"],
                        "excerpt": entry["excerpt"],
                    }
                    for entry in fact_bundle["entries"]
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        "FOCUSFACTSJSON": json.dumps(
            [
                {
                    "date": entry["date"],
                    "city": entry["city"],
                    "attractions": entry["attractions"],
                    "attractions_text": entry["attractions_text"],
                    "attractions_source": entry["attractions_source"],
                    "landmark": entry["landmark"] or "未找到可靠景点数据",
                    "transport_cost": entry["transport_cost"],
                    "route_position": index + 1,
                    "route_total": len(fact_bundle["focus_entries"]),
                    "excerpt": entry["excerpt"],
                }
                for index, entry in enumerate(fact_bundle["focus_entries"])
            ],
            ensure_ascii=False,
            indent=2,
        ),
    }
    return render_template(template, context)


def validate_summary_payload(payload: dict[str, Any], fact_bundle: dict[str, Any]) -> bool:
    required = ["title", "hook", "overview", "city_sections", "cost_observation", "closing", "next_teaser"]
    if any(not str(payload.get(key, "")).strip() for key in required if key != "city_sections"):
        return False
    if not isinstance(payload.get("city_sections"), list):
        return False

    focus_entries = fact_bundle["focus_entries"]
    sections = payload["city_sections"]
    if len(sections) != len(focus_entries):
        return False

    for section, focus_entry in zip(sections, focus_entries):
        if not isinstance(section, dict):
            return False
        if section.get("city") != focus_entry["city"]:
            return False
        if not str(section.get("body", "")).strip():
            return False
    return True


def build_fallback_summary(fact_bundle: dict[str, Any]) -> dict[str, Any]:
    first_city = fact_bundle["entries"][0]["city"]
    last_city = fact_bundle["entries"][-1]["city"]
    route_count = fact_bundle["city_count"]
    total_cost = fact_bundle["total_transport_cost"]
    wallet_delta = fact_bundle["wallet_delta"]
    title = f"从{first_city}到{last_city}，这段路慢慢有了形状"
    hook = f"{fact_bundle['start_date']} 到 {fact_bundle['end_date']}，阿虾一共走过 {route_count} 座城，路费花掉 {total_cost} 元，脚步更轻，心也更慢了一点。"
    overview = (
        f"这不是某一天的停留，而是一段连续移动留下来的余温。"
        f"从 {first_city} 出发，到 {last_city} 收尾，城市一个接着一个往前排开，"
        f"风景没有被喊得很响，却把节奏慢慢改了。"
    )

    city_sections = []
    for index, entry in enumerate(fact_bundle["focus_entries"], start=1):
        landmark = entry["landmark"] or "这座城市留下的轮廓"
        if index == 1:
            intro = f"走到第 {index} 个重点节点时，阿虾从 {entry['city']} 开始把这一段路慢慢铺开。"
        else:
            prev_city = fact_bundle["focus_entries"][index - 2]["city"]
            intro = f"走到第 {index} 个重点节点时，阿虾从 {prev_city} 接着落到 {entry['city']}。"
        body = (
            f"{intro}"
            f"{landmark} 把这座城市的轮廓压得很低，像是终于有了一个能停下来看的理由。"
            f"{entry['excerpt'] or '这一站没有喧哗，只有一些适合慢慢记住的细节。'}"
        )
        city_sections.append({"city": entry["city"], "body": body})

    cost_observation = (
        f"这一段真正花钱的地方，不在热闹的景点里，而在城市之间的移动。"
        f"总交通费是 {total_cost} 元，余额从 {fact_bundle['start_wallet']} 元走到 {fact_bundle['end_wallet']} 元。"
        f"钱像是在替这段旅程丈量距离，每少一点，脚下的路也更具体一点。"
    )
    closing = "回头看这一段，记住的不是打卡数量，而是风、石阶、水面、车程和停顿慢慢叠在一起的质感。"
    next_teaser = f"路线还没有停下。再往后走，阿虾会继续把下一段路写成更长一点的回声。"
    return {
        "title": title,
        "hook": hook,
        "overview": overview,
        "city_sections": city_sections,
        "cost_observation": cost_observation,
        "closing": closing,
        "next_teaser": next_teaser,
    }


def generate_summary_copy(project_root: Path, fact_bundle: dict[str, Any], settings: dict[str, str]) -> dict[str, Any]:
    prompt = render_summary_prompt(project_root, fact_bundle)
    raw_response = ""
    llm_config = resolve_text_llm_config(settings)
    print_console_llm_request("阶段总结文案", llm_config, 0.55, prompt)
    response = call_llm(prompt, settings)
    if response:
        raw_response = response
        cleaned = strip_code_fences(response)
        try:
            payload = json.loads(cleaned)
            if validate_summary_payload(payload, fact_bundle):
                return {
                    "copy": payload,
                    "prompt": prompt,
                    "raw_response": raw_response,
                    "source": "llm",
                }
        except json.JSONDecodeError:
            pass
    return {
        "copy": build_fallback_summary(fact_bundle),
        "prompt": prompt,
        "raw_response": raw_response,
        "source": "fallback",
    }


def has_image_credentials(provider: str) -> bool:
    if provider == "google":
        return bool(os.environ.get("GEMINI_API_KEY"))
    if provider == "dashscope":
        return bool(os.environ.get("DASHSCOPE_API_KEY"))
    return False


def render_template_file(path: Path, context: dict[str, Any]) -> str:
    text = read_text(path)
    env = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value) for key, value in context.items()}
    return render_template(text, env)


def clean_generated_prompt(text: str) -> str:
    value = strip_code_fences(text or "")
    value = value.replace("\\_", "_")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def resolve_summary_image_config(settings: dict[str, str]) -> dict[str, str]:
    return {
        "mode": os.environ.get("SUMMARY_IMAGE_MODE", settings.get("summary_image_mode_default", "single_pass")).strip() or "single_pass",
        "provider": os.environ.get("IMAGE_PROVIDER", settings.get("image_provider_default", "google")).strip() or "google",
        "model": os.environ.get("IMAGE_MODEL", settings.get("image_model_default", "gemini-3.1-flash-image-preview")).strip() or "gemini-3.1-flash-image-preview",
    }


def describe_scene_zone(index: int, total: int) -> str:
    if total <= 1:
        return "画面中下部"
    progress = index / (total - 1)
    if progress <= 0.18:
        return "画面下部偏左"
    if progress <= 0.4:
        return "画面下部偏中"
    if progress <= 0.62:
        return "画面中段偏右"
    if progress <= 0.82:
        return "画面上部偏左"
    return "画面上部偏右"


def describe_scene_mood(entry: dict[str, Any]) -> str:
    landmark = entry["landmark"] or entry["city"]
    if any(token in landmark for token in ("西湖", "泉", "水", "湖", "河", "桥")):
        return "更湿润、柔和、带雾气与流动水纹"
    if any(token in landmark for token in ("城墙", "石", "砖", "塔", "寺")):
        return "更沉稳、克制、带砖石与历史质感"
    return "安静、缓慢、像路上停下来的一次回望"


def build_scene_anchor_lines(fact_bundle: dict[str, Any]) -> str:
    lines: list[str] = []
    entries = fact_bundle["entries"]
    for index, entry in enumerate(entries):
        zone = describe_scene_zone(index, len(entries))
        landmark = entry["landmark"] or entry["city"]
        mood = describe_scene_mood(entry)
        if index == 0:
            transition = "作为旅程起点，气息最轻，适合让画面先从柔和处展开。"
        else:
            prev_city = entries[index - 1]["city"]
            transition = f"要从上一段 {prev_city} 的质感自然过渡过来，不要像拼贴切块。"
        lines.append(f"{index + 1}. {entry['city']}：放在{zone}，核心意象是{landmark}，整体氛围{mood}。{transition}")
    return "\n".join(lines)


def build_transition_lines(fact_bundle: dict[str, Any]) -> str:
    entries = fact_bundle["entries"]
    if len(entries) <= 1:
        return "整张图只有一个场景段，仍要保留旅程未停下的缓慢流动感。"
    lines: list[str] = []
    for prev, current in zip(entries, entries[1:]):
        lines.append(f"{prev['city']} → {current['city']}：通过溪流、小路、风向、石阶或云气自然连接，不要出现断裂切换。")
    return "\n".join(lines)


def build_image_constraint_summary(summary_copy: dict[str, Any], fact_bundle: dict[str, Any]) -> str:
    lines = [
        f"标题气质：{summary_copy['title']}",
        f"事实链路：{fact_bundle['start_date']} 至 {fact_bundle['end_date']}，{fact_bundle['route_chain_text']}，总交通费 {fact_bundle['total_transport_cost']} 元。",
        "控制重点：构图骨架、路线流动感、城市顺序的空间分布、各城市代表意象。",
        "硬性约束：不是地图、不是 UI、不是旅游宣传页、不要中轴时间线、不要硬卡片、不要整齐标签、不要明显文字。",
        "文字策略：允许极少量装饰性文字，但不能依赖图中文字承载事实，出现大段文字或乱码视为失败倾向。",
        "视觉目标：做成阶段旅程主视觉海报，而不是精确信息图。",
    ]
    return "\n".join(lines) + "\n"


def build_fallback_image_prompt(summary_copy: dict[str, Any], fact_bundle: dict[str, Any]) -> str:
    city_lines = "；".join(
        f"{entry['city']}放在{describe_scene_zone(index, len(fact_bundle['entries']))}，核心意象是{entry['landmark'] or entry['city']}"
        for index, entry in enumerate(fact_bundle["entries"][:6])
    )
    return (
        f"一张纵向阶段旅程主视觉海报，主题是“{summary_copy['title']}”，不是地图，不是UI，不是旅游宣传页。"
        f"画面表现从{fact_bundle['entries'][0]['city']}到{fact_bundle['entries'][-1]['city']}的连续旅程，整体沿左下到右上缓慢推进，"
        f"路线只通过溪流、小路、风向、水汽、石阶等隐性元素表达，不要时间轴，不要硬直线，不要明显文字。"
        f"{city_lines}。各场景必须自然过渡，不要像三张拼贴。"
        f"吉卜力绘本风格，旅行的青蛙审美，治愈系日式手绘水彩，低饱和莫兰迪色，细铅笔线稿，明显粗糙纸纹，2D扁平极简。"
    )


def generate_image_prompt(
    project_root: Path,
    settings: dict[str, str],
    summary_copy: dict[str, Any],
    fact_bundle: dict[str, Any],
    output_dir: Path,
    log_path: Path,
) -> str:
    prompt_context = {
        "BASEIMAGESTYLE": read_text(project_root / "config/image_style.md").strip(),
        "SUMMARYIMAGESTYLE": read_text(project_root / "config/summary_image_style.md").strip(),
        "SUMMARYTITLE": summary_copy["title"],
        "SUMMARYHOOK": summary_copy["hook"],
        "ROUTECHAINTEXT": fact_bundle["route_chain_text"],
        "CITYLANDMARKLINES": "\n".join(f"{index + 1}. {entry['city']} - {entry['landmark'] or entry['city']}" for index, entry in enumerate(fact_bundle["entries"])),
        "SCENEANCHORLINES": build_scene_anchor_lines(fact_bundle),
        "TRANSITIONLINES": build_transition_lines(fact_bundle),
        "FACTLINE": f"{fact_bundle['start_date']} 至 {fact_bundle['end_date']}，{fact_bundle['route_chain_text']}，总交通费 {fact_bundle['total_transport_cost']} 元。",
    }
    request_prompt = render_template_file(project_root / "config/summary_image_prompt.md", prompt_context)
    write_text(output_dir / "image_prompt_request.txt", request_prompt)
    append_log(log_path, "已写入阶段海报单次生成提示词请求。")

    llm_config = resolve_text_llm_config(settings)
    print_console_llm_request("阶段海报提示词", llm_config, 0.7, request_prompt)
    generated_prompt = call_llm(request_prompt, settings, temperature=0.7)
    if generated_prompt:
        write_text(output_dir / "image_prompt_response.txt", generated_prompt)
        cleaned = clean_generated_prompt(generated_prompt)
        if cleaned:
            write_text(output_dir / "image_prompt.txt", cleaned)
            append_log(log_path, "阶段海报最终单次生成提示词由文本 LLM 生成。")
            return cleaned

    fallback = build_fallback_image_prompt(summary_copy, fact_bundle)
    write_text(output_dir / "image_prompt_response.txt", "[fallback] 未获得有效图片提示词响应，已使用脚本回退提示词。\n")
    write_text(output_dir / "image_prompt.txt", fallback)
    append_log(log_path, "阶段海报最终单次生成提示词使用脚本回退。")
    return fallback


def validate_generated_poster(image_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"passed": True, "issues": [], "warnings": [], "metrics": {}}
    if not image_path.exists():
        report["passed"] = False
        report["issues"].append("图片文件不存在")
        return report
    try:
        with Image.open(image_path) as image:
            width, height = image.size
            report["metrics"]["width"] = width
            report["metrics"]["height"] = height
            report["metrics"]["file_size"] = image_path.stat().st_size
            if width < 900 or height < 1200:
                report["issues"].append("图片尺寸过小")
            if image_path.stat().st_size < 80_000:
                report["issues"].append("图片文件体积异常偏小")
            gray = image.convert("L")
            full_std = ImageStat.Stat(gray).stddev[0]
            center_box = (
                int(width * 0.28),
                int(height * 0.22),
                int(width * 0.72),
                int(height * 0.78),
            )
            center_std = ImageStat.Stat(gray.crop(center_box)).stddev[0]
            report["metrics"]["full_stddev"] = round(full_std, 2)
            report["metrics"]["center_stddev"] = round(center_std, 2)
            if center_std > max(68.0, full_std * 1.22):
                report["issues"].append("画面中心区域过满")
            elif center_std > max(58.0, full_std * 1.12):
                report["warnings"].append("画面中心区域偏满")
    except OSError as exc:
        report["passed"] = False
        report["issues"].append(f"图片无法读取: {exc}")
        return report
    report["passed"] = len(report["issues"]) == 0
    return report


def generate_single_pass_poster(
    project_root: Path,
    settings: dict[str, str],
    summary_copy: dict[str, Any],
    fact_bundle: dict[str, Any],
    output_dir: Path,
    poster_path: Path,
    log_path: Path,
) -> Path | None:
    image_config = resolve_summary_image_config(settings)
    mode = image_config["mode"]
    image_provider = image_config["provider"]
    image_model = image_config["model"]
    image_script = settings["image_gen_script"]
    if mode != "single_pass":
        append_log(log_path, f"SUMMARY_IMAGE_MODE={mode} 当前未实现，回退为 single_pass。")
    generate_image_prompt(project_root, settings, summary_copy, fact_bundle, output_dir, log_path)
    prompt_file = output_dir / "image_prompt.txt"
    constraints = build_image_constraint_summary(summary_copy, fact_bundle)
    write_text(output_dir / "image_constraints.txt", constraints)
    append_log(log_path, f"阶段海报模式: single_pass")
    append_log(log_path, f"阶段海报图片配置: provider={image_provider}, model={image_model}, script={image_script}")
    append_log(log_path, f"单次生成约束摘要: {constraints.replace(chr(10), ' | ').strip()}")
    print_console_image_request("阶段海报单次生成", image_provider, image_model, "1200x1800", read_text(prompt_file))
    if not shutil_which("bun"):
        append_log(log_path, "未找到 bun，跳过阶段海报单次生成。")
        if poster_path.exists():
            append_log(log_path, f"沿用已有阶段海报: {poster_path}")
            return poster_path
        return None
    if not Path(image_script).exists():
        append_log(log_path, f"图片生成脚本不存在，跳过阶段海报单次生成: {image_script}")
        if poster_path.exists():
            append_log(log_path, f"沿用已有阶段海报: {poster_path}")
            return poster_path
        return None
    if not has_image_credentials(image_provider):
        append_log(log_path, f"未配置 {image_provider} 对应图片凭证，跳过阶段海报单次生成。")
        if poster_path.exists():
            append_log(log_path, f"沿用已有阶段海报: {poster_path}")
            return poster_path
        return None

    image_log_path = output_dir / "image_gen.log"
    write_text(image_log_path, "")
    append_log(log_path, f"开始单次生成阶段海报，provider={image_provider}, model={image_model}")
    for attempt in range(1, 4):
        temp_output = output_dir / f"poster_attempt_{attempt}.png"
        command = [
            "bun",
            image_script,
            "--provider",
            image_provider,
            "--model",
            image_model,
            "--promptfiles",
            str(prompt_file),
            "--image",
            str(temp_output),
            "--size",
            "1200x1800",
            "--json",
        ]
        with image_log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"=== attempt {attempt} ===\n")
            result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, cwd=project_root, check=False)
            handle.write("\n")
        if result.returncode != 0 or not temp_output.exists():
            failure_reason = tail_nonempty_line(image_log_path) or f"exit_code={result.returncode}"
            append_log(log_path, f"阶段海报单次生成失败，第 {attempt} 次尝试未产出可用图片，原因: {failure_reason}")
            continue

        validation = validate_generated_poster(temp_output)
        write_json(output_dir / f"image_validation_attempt_{attempt}.json", validation)
        if validation["passed"]:
            temp_output.replace(poster_path)
            append_log(log_path, f"阶段海报单次生成成功: {poster_path}")
            if validation["warnings"]:
                append_log(log_path, f"阶段海报校验警告: {'；'.join(validation['warnings'])}")
            return poster_path

        append_log(log_path, f"阶段海报校验未通过，第 {attempt} 次尝试存在问题: {'；'.join(validation['issues'])}")

    failure_reason = tail_nonempty_line(image_log_path) or "single_pass_generation_failed"
    write_text(output_dir / "image_failure.txt", failure_reason + "\n")
    append_log(log_path, f"阶段海报单次生成最终失败，详见 {image_log_path}")
    if poster_path.exists():
        append_log(log_path, f"保留已有成功海报: {poster_path}")
        return poster_path
    append_log(log_path, "未生成新的阶段海报，将仅输出文字总结。")
    return None


def shutil_which(binary: str) -> str | None:
    for path_part in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_part) / binary
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size, index=0)
            except OSError:
                continue
    return ImageFont.load_default()


def create_paper_background(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGBA", size, PAPER_BG)
    pixels = image.load()
    random.seed(42)
    for x in range(size[0]):
        for y in range(size[1]):
            offset = random.randint(-7, 7)
            base = PAPER_BG[0] + offset
            pixels[x, y] = (
                max(224, min(255, base)),
                max(216, min(250, PAPER_BG[1] + offset)),
                max(205, min(245, PAPER_BG[2] + offset)),
                255,
            )
    image = image.filter(ImageFilter.GaussianBlur(0.45))
    return image


def fit_image(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = list(text)
    lines: list[str] = []
    current = ""
    for char in words:
        trial = current + char
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_centered_text(draw: ImageDraw.ImageDraw, center_x: int, y: int, text: str, font: ImageFont.ImageFont, fill: tuple[int, int, int, int]) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    draw.text((center_x - width / 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def compute_route_anchors(count: int) -> list[tuple[float, float]]:
    if count <= 0:
        return []
    if count == 1:
        return [(CANVAS_SIZE[0] * 0.48, CANVAS_SIZE[1] * 0.58)]

    left_margin = 250
    right_margin = CANVAS_SIZE[0] - 250
    bottom = CANVAS_SIZE[1] - BOTTOM_MARGIN - 90
    top = TOP_MARGIN + 210
    anchors: list[tuple[float, float]] = []
    for index in range(count):
        progress = index / (count - 1)
        x_base = left_margin + (right_margin - left_margin) * progress
        x_wave = math.sin(progress * math.pi * 1.4) * 78
        x = x_base + x_wave
        y = bottom - (bottom - top) * progress
        y += math.sin(progress * math.pi * 2.2) * 24
        anchors.append((x, y))
    return anchors


def sample_catmull_rom(points: list[tuple[float, float]], samples_per_segment: int = 28) -> list[tuple[float, float]]:
    if len(points) <= 1:
        return points
    extended = [points[0], *points, points[-1]]
    sampled: list[tuple[float, float]] = []
    for index in range(1, len(extended) - 2):
        p0 = extended[index - 1]
        p1 = extended[index]
        p2 = extended[index + 1]
        p3 = extended[index + 2]
        for step in range(samples_per_segment):
            t = step / samples_per_segment
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            sampled.append((x, y))
    sampled.append(points[-1])
    return sampled


def measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fit_landmark_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines = wrap_text(draw, text, font, max_width)
    if len(lines) <= 2:
        return lines
    merged = lines[:1] + ["".join(lines[1:])]
    while merged and len(merged) > 1:
        width, _ = measure_text(draw, merged[1], font)
        if width <= max_width:
            return merged
        merged[1] = merged[1][:-1] + "…"
        if measure_text(draw, merged[1], font)[0] <= max_width:
            return merged
    return [lines[0][: max(1, len(lines[0]) - 1)] + "…"]


def draw_route_path(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]]) -> None:
    if len(points) < 2:
        return
    path = sample_catmull_rom(points)
    draw.line(path, fill=(255, 247, 242, 100), width=18)
    draw.line(path, fill=SOFT_LINE_COLOR, width=11)
    draw.line(path, fill=LINE_COLOR, width=5)


def label_side_for_anchor(anchor_x: float) -> int:
    return 1 if anchor_x < CANVAS_SIZE[0] * 0.52 else -1


def compute_label_box(
    draw: ImageDraw.ImageDraw,
    anchor: tuple[float, float],
    entry: dict[str, Any],
    side: int,
    date_font: ImageFont.ImageFont,
    city_font: ImageFont.ImageFont,
    landmark_font: ImageFont.ImageFont,
) -> tuple[tuple[float, float, float, float], list[str]]:
    landmark = entry["landmark"] or "这一站的轮廓仍在路上"
    landmark_lines = fit_landmark_lines(draw, landmark, landmark_font, 220)
    city_width, city_height = measure_text(draw, entry["city"], city_font)
    landmark_width = max((measure_text(draw, line, landmark_font)[0] for line in landmark_lines), default=0)
    content_width = max(city_width, landmark_width, 150)
    box_width = min(320, max(210, content_width + 56))
    box_height = 98 + max(0, len(landmark_lines) - 1) * 22
    offset_x = 46 if side > 0 else -(box_width + 46)
    offset_y = -32 if side > 0 else -22
    x1 = anchor[0] + offset_x
    y1 = anchor[1] + offset_y
    x1 = max(58, min(CANVAS_SIZE[0] - box_width - 58, x1))
    y1 = max(TOP_MARGIN + 10, min(CANVAS_SIZE[1] - BOTTOM_MARGIN - box_height - 10, y1))
    return (x1, y1, x1 + box_width, y1 + box_height), landmark_lines


def draw_city_label(
    draw: ImageDraw.ImageDraw,
    anchor: tuple[float, float],
    entry: dict[str, Any],
    index: int,
    total_count: int,
    date_font: ImageFont.ImageFont,
    city_font: ImageFont.ImageFont,
    landmark_font: ImageFont.ImageFont,
    badge_font: ImageFont.ImageFont,
) -> None:
    side = label_side_for_anchor(anchor[0])
    box, landmark_lines = compute_label_box(draw, anchor, entry, side, date_font, city_font, landmark_font)
    x1, y1, x2, y2 = box

    guide_target_x = x1 if side > 0 else x2
    guide_mid_x = anchor[0] + (guide_target_x - anchor[0]) * 0.45
    guide_mid_y = anchor[1] - 18
    draw.line([anchor, (guide_mid_x, guide_mid_y), (guide_target_x, y1 + 58)], fill=(175, 114, 98, 185), width=2)

    draw.rounded_rectangle(box, radius=28, fill=CARD_FILL, outline=(205, 180, 166, 180), width=2)
    badge_box = (x1 + 18, y1 + 16, x1 + 92, y1 + 46)
    draw.rounded_rectangle(badge_box, radius=16, fill=(183, 92, 78, 214))
    draw.text((x1 + 31, y1 + 19), entry["date"][5:], font=date_font, fill=(255, 248, 242, 255))

    draw.text((x1 + 20, y1 + 54), entry["city"], font=city_font, fill=(92, 63, 52, 245))
    text_y = y1 + 94
    for line in landmark_lines[:2]:
        draw.text((x1 + 20, text_y), line, font=landmark_font, fill=(122, 96, 84, 220))
        text_y += 24

    is_edge = index in {0, total_count - 1}
    halo = 28 if is_edge else 22
    draw.ellipse((anchor[0] - halo, anchor[1] - halo, anchor[0] + halo, anchor[1] + halo), fill=(255, 251, 247, 190))
    node_radius = 14 if is_edge else 12
    draw.ellipse((anchor[0] - node_radius, anchor[1] - node_radius, anchor[0] + node_radius, anchor[1] + node_radius), fill=(252, 247, 241, 255), outline=LINE_COLOR, width=4)
    num = str(index + 1)
    num_w, num_h = measure_text(draw, num, badge_font)
    draw.text((anchor[0] - num_w / 2, anchor[1] - num_h / 2 - 1), num, font=badge_font, fill=(123, 67, 54, 255))


def render_poster(
    summary_copy: dict[str, Any],
    fact_bundle: dict[str, Any],
    output_path: Path,
    background_path: Path | None,
) -> None:
    ensure_dirs(output_path.parent)
    canvas = create_paper_background(CANVAS_SIZE)
    if background_path and background_path.exists():
        bg = fit_image(background_path, CANVAS_SIZE)
        bg = Image.blend(bg, Image.new("RGBA", CANVAS_SIZE, (255, 250, 244, 255)), 0.35)
        canvas = Image.alpha_composite(canvas, bg)

    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    title_font = load_font(48, bold=True)
    hook_font = load_font(23)
    meta_font = load_font(22)
    city_font = load_font(34, bold=True)
    landmark_font = load_font(21)
    date_font = load_font(18, bold=True)
    badge_font = load_font(18, bold=True)

    draw.rounded_rectangle((96, 74, CANVAS_SIZE[0] - 96, 198), radius=34, fill=(250, 245, 238, 196), outline=(215, 194, 178, 128), width=2)
    draw_centered_text(draw, CANVAS_SIZE[0] // 2, 96, summary_copy["title"], title_font, (90, 62, 51, 245))
    hook_lines = wrap_text(draw, summary_copy["hook"], hook_font, CANVAS_SIZE[0] - 280)
    current_y = 149
    for line in hook_lines[:2]:
        height = draw_centered_text(draw, CANVAS_SIZE[0] // 2, current_y, line, hook_font, (112, 86, 74, 220))
        current_y += height + 4

    entries = fact_bundle["entries"]
    anchors = compute_route_anchors(len(entries))
    draw_route_path(draw, anchors)

    for index, (entry, anchor) in enumerate(zip(entries, anchors)):
        draw_city_label(draw, anchor, entry, index, len(entries), date_font, city_font, landmark_font, badge_font)

    footer = f"{fact_bundle['route_chain_text']}  |  总交通费 {fact_bundle['total_transport_cost']} 元"
    draw.rounded_rectangle((146, CANVAS_SIZE[1] - 112, CANVAS_SIZE[0] - 146, CANVAS_SIZE[1] - 60), radius=24, fill=(250, 245, 238, 186), outline=(214, 196, 183, 86), width=1)
    draw_centered_text(draw, CANVAS_SIZE[0] // 2, CANVAS_SIZE[1] - 96, footer, meta_font, (102, 76, 64, 240))

    canvas = Image.alpha_composite(canvas, overlay)
    canvas.save(output_path)


def format_wallet_delta(value: int) -> str:
    return f"{value:+d} 元"


def build_summary_markdown(summary_copy: dict[str, Any], fact_bundle: dict[str, Any], file_name: str, include_image: bool) -> str:
    image_rel = f"../images/summaries/{file_name}.png"
    snapshot = [
        ("经过城市数", f"{fact_bundle['city_count']} 座"),
        ("代表景点数", f"{fact_bundle['representative_landmark_count']} 个"),
        ("总交通费", f"{fact_bundle['total_transport_cost']} 元"),
        ("余额变化", format_wallet_delta(fact_bundle["wallet_delta"])),
    ]
    snapshot_lines = ["| 指标 | 数值 |", "| ---- | ---- |"]
    snapshot_lines.extend(f"| {label} | {value} |" for label, value in snapshot)

    cost_lines = ["| 日期 | 城市 | 交通费 | 当日余额 |", "| ---- | ---- | ---- | ---- |"]
    cost_lines.extend(
        f"| {entry['date']} | {entry['city']} | {entry['transport_cost']} 元 | {entry['wallet']} 元 |"
        for entry in fact_bundle["entries"]
    )

    city_sections = []
    for section, focus_entry in zip(summary_copy["city_sections"], fact_bundle["focus_entries"]):
        heading = f"### {focus_entry['city']} · {focus_entry['landmark'] or focus_entry['city']}"
        city_sections.append(f"{heading}\n\n{section['body'].strip()}")

    markdown: list[str] = []
    if include_image:
        markdown.extend(
            [
                f"![阶段路线海报]({image_rel})",
                "",
                f"_这张海报是阶段旅程主视觉，准确事实以本文内容为准。{fact_bundle['start_date']} 至 {fact_bundle['end_date']} · {fact_bundle['route_chain_text']} · 总交通费 {fact_bundle['total_transport_cost']} 元。_",
                "",
            ]
        )
    else:
        markdown.extend(
            [
                f"_本次未生成新的阶段海报，准确事实如下：{fact_bundle['start_date']} 至 {fact_bundle['end_date']} · {fact_bundle['route_chain_text']} · 总交通费 {fact_bundle['total_transport_cost']} 元。_",
                "",
            ]
        )

    markdown.extend([
        f"## {summary_copy['title'].strip()}",
        "",
        f"> {summary_copy['hook'].strip()}",
        "",
        "### 事实快照",
        "",
        *snapshot_lines,
        "",
        "### 城市顺序链路",
        "",
        f"`{fact_bundle['route_chain_text']}`",
        "",
        "### 这一段发生了什么",
        "",
        summary_copy["overview"].strip(),
        "",
        "### 城市切片",
        "",
        "\n\n".join(city_sections),
        "",
        "### 花费观察",
        "",
        summary_copy["cost_observation"].strip(),
        "",
        "### 费用明细",
        "",
        *cost_lines,
        "",
        "### 阶段回声",
        "",
        summary_copy["closing"].strip(),
        "",
        "### 下一段",
        "",
        summary_copy["next_teaser"].strip(),
        "",
    ])
    return "\n".join(markdown)


def update_summary_index(project_root: Path, fact_bundle: dict[str, Any], summary_path: Path) -> None:
    index_path = project_root / "data/journals/index.md"
    content = read_text(index_path)
    if not content:
        return

    section_header = "## 阶段总结"
    table_header = "\n".join(
        [
            section_header,
            "",
            "| 时间范围 | 覆盖天数 | 经过城市 | 总交通费 | 链接 | 生成时间 |",
            "| ------ | ------ | ------ | ------ | ------ | ------ |",
        ]
    )
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    label = f"{fact_bundle['start_date']} ~ {fact_bundle['end_date']}"
    route_short = fact_bundle["route_chain_text"]
    row = (
        f"| {label} | {fact_bundle['days_covered']}天 | {route_short} | "
        f"{fact_bundle['total_transport_cost']}元 | [查看](../summaries/{summary_path.name}) | {generated_at} |"
    )
    existing_row_pattern = re.compile(
        rf"^\|\s*{re.escape(label)}\s*\|.*\(\.\./summaries/{re.escape(summary_path.name)}\).*$",
        re.MULTILINE,
    )
    content = re.sub(existing_row_pattern, "", content).replace("\n\n\n", "\n\n")

    if section_header not in content:
        marker = "\n***\n"
        if marker in content:
            content = content.replace(marker, f"\n\n{table_header}\n{row}\n{marker}", 1)
        else:
            content = content.rstrip() + f"\n\n{table_header}\n{row}\n"
    else:
        lines = content.splitlines()
        start_index = lines.index(section_header)
        insert_index = start_index + 4
        while insert_index < len(lines) and lines[insert_index].startswith("|"):
            insert_index += 1
        lines.insert(insert_index, row)
        content = "\n".join(line for line in lines if line is not None)

    content = re.sub(r"\n{3,}", "\n\n", content).strip() + "\n"
    index_path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dirs(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    if start_date > end_date:
        print("开始日期不能晚于结束日期", file=sys.stderr)
        return 1

    settings = load_runtime_settings(project_root)
    summary_name = f"{start_date.isoformat()}_{end_date.isoformat()}"
    output_root = project_root / "data/output/summaries"
    output_dir = output_root / summary_name
    logs_root = project_root / "data/logs"
    ensure_dirs(output_root, output_dir, logs_root, project_root / "data/summaries", project_root / "data/images/summaries")
    run_log_path = logs_root / f"summary_{summary_name}.log"
    write_text(run_log_path, "")
    append_log(run_log_path, f"开始生成阶段总结: {summary_name}")
    append_log(run_log_path, f"时间范围: {start_date.isoformat()} -> {end_date.isoformat()}")
    llm_config = resolve_text_llm_config(settings)
    append_log(
        run_log_path,
        f"文字模型配置: provider={llm_config['provider']}, model={llm_config['model']}, base_url={llm_config['base_url']}",
    )

    try:
        fact_bundle = load_fact_bundle(project_root, start_date, end_date)
    except ValueError as exc:
        append_log(run_log_path, f"生成失败: {exc}")
        print(str(exc), file=sys.stderr)
        return 1
    append_log(run_log_path, f"命中游记 {fact_bundle['days_covered']} 篇，城市链路: {fact_bundle['route_chain_text']}")
    append_log(run_log_path, f"总交通费 {fact_bundle['total_transport_cost']} 元，余额变化 {fact_bundle['wallet_delta']} 元")

    summary_result = generate_summary_copy(project_root, fact_bundle, settings)
    summary_copy = summary_result["copy"]
    write_text(output_dir / "summary_prompt.txt", summary_result["prompt"])
    write_text(
        output_dir / "summary_llm_response.txt",
        summary_result["raw_response"] if summary_result["raw_response"] else "[fallback] 本次未获得有效 LLM 原始响应，已使用脚本回退内容。\n",
    )
    append_log(run_log_path, f"总结文案来源: {summary_result['source']}")
    poster_path = project_root / "data/images/summaries" / f"{summary_name}.png"
    generated_poster_path = generate_single_pass_poster(project_root, settings, summary_copy, fact_bundle, output_dir, poster_path, run_log_path)
    if generated_poster_path and generated_poster_path.exists():
        append_log(run_log_path, f"阶段海报已写入: {generated_poster_path}")
    else:
        append_log(run_log_path, "阶段海报本次未生成成功。")

    summary_markdown = build_summary_markdown(summary_copy, fact_bundle, summary_name, include_image=bool(generated_poster_path and generated_poster_path.exists()))
    summary_path = project_root / "data/summaries" / f"{summary_name}.md"
    write_text(summary_path, summary_markdown)
    append_log(run_log_path, f"阶段总结 Markdown 已写入: {summary_path}")

    fact_json_payload = {
        "start_date": fact_bundle["start_date"],
        "end_date": fact_bundle["end_date"],
        "days_covered": fact_bundle["days_covered"],
        "entries": [
            {
                "date": entry["date"],
                "city": entry["city"],
                "transport_cost": entry["transport_cost"],
                "wallet": entry["wallet"],
                "journal_file": entry["journal_file"],
                "attractions": entry["attractions"],
                "attractions_text": entry["attractions_text"],
                "attractions_source": entry["attractions_source"],
                "raw_attractions_text": entry["raw_attractions_text"],
                "landmark": entry["landmark"],
                "weather": entry["weather"],
            }
            for entry in fact_bundle["entries"]
        ],
        "ordered_cities": fact_bundle["ordered_cities"],
        "city_count": fact_bundle["city_count"],
        "landmarks_by_city": fact_bundle["landmarks_by_city"],
        "weather_by_city": fact_bundle["weather_by_city"],
        "total_transport_cost": fact_bundle["total_transport_cost"],
        "start_wallet": fact_bundle["start_wallet"],
        "end_wallet": fact_bundle["end_wallet"],
        "wallet_delta": fact_bundle["wallet_delta"],
        "journal_excerpts": fact_bundle["journal_excerpts"],
        "route_chain_text": fact_bundle["route_chain_text"],
        "representative_landmark_count": fact_bundle["representative_landmark_count"],
    }
    fact_json_payload["summary_image_mode"] = resolve_summary_image_config(settings)["mode"]
    fact_json_payload["summary_image_provider"] = resolve_summary_image_config(settings)["provider"]
    fact_json_payload["summary_image_model"] = resolve_summary_image_config(settings)["model"]
    fact_json_payload["summary_copy"] = summary_copy
    fact_json_payload["poster_path"] = str(generated_poster_path) if generated_poster_path and generated_poster_path.exists() else ""
    fact_json_payload["summary_markdown_path"] = str(summary_path)
    fact_json_path = output_root / f"{summary_name}.json"
    write_json(fact_json_path, fact_json_payload)
    append_log(run_log_path, f"事实 JSON 已写入: {fact_json_path}")

    update_summary_index(project_root, fact_bundle, summary_path)
    append_log(run_log_path, f"索引已更新: {project_root / 'data/journals/index.md'}")
    append_log(run_log_path, "阶段总结生成完成。")

    print(f"阶段总结已生成: {summary_path}")
    print(f"路线海报已生成: {poster_path}")
    print(f"事实 JSON 已生成: {fact_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
