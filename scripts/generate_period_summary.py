#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.settings import load_runtime_settings
from lib.template_renderer import render_template


INDEX_ROW_RE = re.compile(
    r"^\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*\|\s*(?P<city>[^|]+?)\s*\|\s*(?P<price>\d+)元\s*\|\s*(?P<wallet>\d+)元\s*\|\s*\[查看\]\(\./(?P<file>[^)]+)\)\s*\|\s*(?P<added>[^|]+?)\s*\|$"
)
JOURNAL_FILE_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<city>.+)\.md$")

CANVAS_SIZE = (1200, 1800)
CARD_WIDTH = 430
CARD_HEIGHT = 160
TOP_MARGIN = 280
BOTTOM_MARGIN = 300
ROUTE_X = CANVAS_SIZE[0] // 2
LINE_COLOR = (183, 92, 78, 255)
CARD_FILL = (252, 247, 240, 236)
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
        match = INDEX_ROW_RE.match(raw_line.strip())
        if not match:
            continue
        item = match.groupdict()
        rows.append(
            {
                "date": item["date"],
                "city": item["city"].strip(),
                "price": int(item["price"]),
                "wallet": int(item["wallet"]),
                "file": item["file"].strip(),
                "added_at": item["added"].strip(),
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

        representative_landmark = ""
        attraction_payload = load_json(attraction_path)
        if weather_valid and isinstance(attraction_payload, list):
            for item in attraction_payload:
                if not isinstance(item, dict):
                    continue
                landmark = str(item.get("landmark", "")).strip()
                if landmark:
                    representative_landmark = landmark
                    break
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


def call_llm(prompt: str, settings: dict[str, str]) -> str | None:
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None

    provider = os.environ.get("LLM_PROVIDER", settings["llm_provider_default"]).strip()
    base_url = os.environ.get("LLM_BASE_URL", settings["llm_base_url_default"]).strip().rstrip("/")
    model = os.environ.get("WRITER_MODEL", settings["writer_model_default"]).strip()

    try:
        if provider == "gemini":
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.55},
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
            "temperature": 0.55,
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


def generate_background_image(
    project_root: Path,
    settings: dict[str, str],
    summary_copy: dict[str, Any],
    fact_bundle: dict[str, Any],
    output_dir: Path,
    log_path: Path,
) -> Path | None:
    image_provider = os.environ.get("IMAGE_PROVIDER", settings["image_provider_default"]).strip()
    image_model = os.environ.get("IMAGE_MODEL", settings["image_model_default"]).strip()
    image_script = settings["image_gen_script"]

    prompt_context = {
        "BASEIMAGESTYLE": read_text(project_root / "config/image_style.md").strip(),
        "SUMMARYIMAGESTYLE": read_text(project_root / "config/summary_image_style.md").strip(),
        "SUMMARYTITLE": summary_copy["title"],
        "SUMMARYHOOK": summary_copy["hook"],
        "ROUTECHAINTEXT": fact_bundle["route_chain_text"],
        "CITYLANDMARKLINES": "\n".join(
            f"{index + 1}. {entry['city']} - {entry['landmark'] or '未找到可靠景点数据'}"
            for index, entry in enumerate(fact_bundle["entries"])
        ),
    }
    prompt = render_template_file(project_root / "config/summary_image_prompt.md", prompt_context)
    write_text(output_dir / "image_prompt.txt", prompt)
    append_log(log_path, f"阶段海报图片配置: provider={image_provider}, model={image_model}, script={image_script}")
    if not shutil_which("bun"):
        append_log(log_path, "未找到 bun，跳过背景图生成。")
        return None
    if not Path(image_script).exists():
        append_log(log_path, f"图片生成脚本不存在，跳过背景图生成: {image_script}")
        return None
    if not has_image_credentials(image_provider):
        append_log(log_path, f"未配置 {image_provider} 对应图片凭证，跳过背景图生成。")
        return None

    temp_output = output_dir / "background.png"
    image_log_path = output_dir / "image_gen.log"
    append_log(log_path, f"开始生成阶段海报背景，provider={image_provider}, model={image_model}")

    command = [
        "bun",
        image_script,
        "--provider",
        image_provider,
        "--model",
        image_model,
        "--prompt",
        prompt,
        "--image",
        str(temp_output),
        "--ar",
        "3:4",
        "--imageSize",
        "1K",
        "--json",
    ]
    with image_log_path.open("w", encoding="utf-8") as handle:
        result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, cwd=project_root, check=False)
    if result.returncode == 0 and temp_output.exists():
        append_log(log_path, f"阶段海报背景生成成功: {temp_output}")
        return temp_output
    append_log(log_path, f"阶段海报背景生成失败，详见 {image_log_path}")
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

    title_font = load_font(52, bold=True)
    hook_font = load_font(24)
    meta_font = load_font(24)
    card_title_font = load_font(34, bold=True)
    card_body_font = load_font(22)
    badge_font = load_font(20, bold=True)

    draw.rounded_rectangle((70, 70, CANVAS_SIZE[0] - 70, 220), radius=36, fill=(250, 245, 238, 224), outline=(208, 183, 165, 200), width=3)
    draw_centered_text(draw, CANVAS_SIZE[0] // 2, 96, summary_copy["title"], title_font, (90, 62, 51, 255))
    hook_lines = wrap_text(draw, summary_copy["hook"], hook_font, CANVAS_SIZE[0] - 220)
    current_y = 162
    for line in hook_lines[:2]:
        height = draw_centered_text(draw, CANVAS_SIZE[0] // 2, current_y, line, hook_font, (112, 86, 74, 235))
        current_y += height + 6

    route_top = TOP_MARGIN + CARD_HEIGHT // 2
    route_bottom = CANVAS_SIZE[1] - BOTTOM_MARGIN
    draw.line((ROUTE_X, route_top, ROUTE_X, route_bottom), fill=LINE_COLOR, width=10)

    entries = fact_bundle["entries"]
    available_height = route_bottom - route_top
    step = available_height // max(1, len(entries) - 1) if len(entries) > 1 else 0

    for index, entry in enumerate(entries):
        y = route_top + index * step if len(entries) > 1 else (route_top + route_bottom) // 2
        side = -1 if index % 2 == 0 else 1
        card_x = ROUTE_X + 90 if side > 0 else ROUTE_X - 90 - CARD_WIDTH
        card_y = y - CARD_HEIGHT // 2
        card_box = (card_x, card_y, card_x + CARD_WIDTH, card_y + CARD_HEIGHT)

        draw.line((ROUTE_X, y, card_x + (0 if side > 0 else CARD_WIDTH), y), fill=LINE_COLOR, width=5)
        draw.ellipse((ROUTE_X - 20, y - 20, ROUTE_X + 20, y + 20), fill=(255, 252, 248, 255), outline=LINE_COLOR, width=6)
        draw.text((ROUTE_X - 9, y - 13), str(index + 1), font=badge_font, fill=(123, 67, 54, 255))

        draw.rounded_rectangle(card_box, radius=28, fill=CARD_FILL, outline=(196, 160, 145, 255), width=3)
        badge_box = (card_x + 18, card_y + 18, card_x + 92, card_y + 52)
        draw.rounded_rectangle(badge_box, radius=18, fill=(183, 92, 78, 255))
        draw.text((card_x + 34, card_y + 22), entry["date"][5:], font=badge_font, fill=(255, 248, 242, 255))

        draw.text((card_x + 22, card_y + 64), entry["city"], font=card_title_font, fill=(89, 61, 50, 255))
        landmark = entry["landmark"] or "这一站的轮廓仍在路上"
        lines = wrap_text(draw, landmark, card_body_font, CARD_WIDTH - 44)
        text_y = card_y + 110
        for line in lines[:2]:
            draw.text((card_x + 22, text_y), line, font=card_body_font, fill=(114, 87, 74, 235))
            text_y += 28

    footer = f"{fact_bundle['route_chain_text']}  |  总交通费 {fact_bundle['total_transport_cost']} 元"
    draw.rounded_rectangle((90, CANVAS_SIZE[1] - 120, CANVAS_SIZE[0] - 90, CANVAS_SIZE[1] - 58), radius=28, fill=(250, 245, 238, 228))
    draw_centered_text(draw, CANVAS_SIZE[0] // 2, CANVAS_SIZE[1] - 102, footer, meta_font, (102, 76, 64, 255))

    canvas = Image.alpha_composite(canvas, overlay)
    canvas.save(output_path)


def format_wallet_delta(value: int) -> str:
    return f"{value:+d} 元"


def build_summary_markdown(summary_copy: dict[str, Any], fact_bundle: dict[str, Any], file_name: str) -> str:
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

    markdown = [
        f"![阶段路线海报]({image_rel})",
        "",
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
    ]
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
    background_path = generate_background_image(project_root, settings, summary_copy, fact_bundle, output_dir, run_log_path)
    poster_path = project_root / "data/images/summaries" / f"{summary_name}.png"
    render_poster(summary_copy, fact_bundle, poster_path, background_path)
    append_log(run_log_path, f"路线海报已写入: {poster_path}")

    summary_markdown = build_summary_markdown(summary_copy, fact_bundle, summary_name)
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
    fact_json_payload["summary_copy"] = summary_copy
    fact_json_payload["poster_path"] = str(poster_path)
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
