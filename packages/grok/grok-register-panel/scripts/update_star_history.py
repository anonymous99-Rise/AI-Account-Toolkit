#!/usr/bin/env python3
"""Generate deterministic light/dark GitHub star-history SVGs."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


API_ROOT = "https://api.github.com"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WIDTH = 900
HEIGHT = 360
PLOT_LEFT = 66
PLOT_RIGHT = 866
PLOT_TOP = 72
PLOT_BOTTOM = 306

THEMES = {
    "light": {
        "background": "#f7f8f5",
        "plot": "#ffffff",
        "text": "#151613",
        "muted": "#656761",
        "grid": "#d9dad5",
        "border": "#c7c9c3",
        "line": "#b93b28",
        "area": "#b93b28",
    },
    "dark": {
        "background": "#171815",
        "plot": "#20211e",
        "text": "#f0f1ed",
        "muted": "#a9aca4",
        "grid": "#383a35",
        "border": "#4a4c46",
        "line": "#f06449",
        "area": "#f06449",
    },
}


def parse_github_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def github_json(path: str, token: str = ""):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "grok-register-star-history",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{API_ROOT}{path}", headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"GitHub API HTTP {exc.code}: {detail}") from exc


def fetch_repository(repo: str, token: str = "") -> dict:
    if not REPO_PATTERN.fullmatch(repo):
        raise ValueError("repo must use owner/name format")
    data = github_json(f"/repos/{repo}", token)
    if not isinstance(data, dict):
        raise RuntimeError("GitHub repository response is not an object")
    return data


def fetch_stars(repo: str, token: str = "") -> list[datetime]:
    if not REPO_PATTERN.fullmatch(repo):
        raise ValueError("repo must use owner/name format")
    stars_by_user = {}
    for page in range(1, 1001):
        path = f"/repos/{repo}/stargazers?per_page=100&page={page}"
        headers = {
            "Accept": "application/vnd.github.star+json",
            "User-Agent": "grok-register-star-history",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(f"{API_ROOT}{path}", headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"GitHub stargazers API HTTP {exc.code}: {detail}") from exc
        if not isinstance(payload, list):
            raise RuntimeError("GitHub stargazers response is not an array")
        for index, item in enumerate(payload):
            if isinstance(item, dict) and item.get("starred_at"):
                user = item.get("user") if isinstance(item.get("user"), dict) else {}
                identity = str(user.get("login") or f"{page}:{index}")
                stars_by_user[identity] = parse_github_datetime(str(item["starred_at"]))
        if len(payload) < 100:
            return sorted(stars_by_user.values())
    raise RuntimeError("GitHub stargazers pagination exceeded 1000 pages")


def nice_step(maximum: int, target_ticks: int = 5) -> int:
    if maximum <= 0:
        return 1
    rough = maximum / max(1, target_ticks)
    magnitude = 10 ** math.floor(math.log10(rough))
    fraction = rough / magnitude
    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10
    return max(1, int(nice_fraction * magnitude))


def format_tick(value: datetime, span: timedelta) -> str:
    if span <= timedelta(days=3):
        return value.strftime("%m-%d %H:%M")
    if span <= timedelta(days=180):
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m")


def _point_time_range(created_at: datetime, stars: list[datetime]) -> tuple[datetime, datetime]:
    start = created_at
    if stars and stars[0] < start:
        start = stars[0]
    if stars:
        end = stars[-1]
    else:
        end = start + timedelta(days=1)
    if end <= start:
        end = start + timedelta(hours=1)
    return start, end


def render_svg(repo: str, created_at: datetime, stars: list[datetime], theme: str) -> str:
    palette = THEMES[theme]
    stars = sorted(stars)
    start, end = _point_time_range(created_at, stars)
    span_seconds = max(1.0, (end - start).total_seconds())
    star_total = len(stars)
    step = nice_step(star_total)
    y_max = max(step, math.ceil(max(1, star_total) / step) * step)

    def x_for(value: datetime) -> float:
        ratio = (value - start).total_seconds() / span_seconds
        return PLOT_LEFT + max(0.0, min(1.0, ratio)) * (PLOT_RIGHT - PLOT_LEFT)

    def y_for(value: int) -> float:
        return PLOT_BOTTOM - (value / y_max) * (PLOT_BOTTOM - PLOT_TOP)

    points = [(x_for(start), y_for(0))]
    points.extend((x_for(value), y_for(index)) for index, value in enumerate(stars, 1))
    line_path = " ".join(
        ("M" if index == 0 else "L") + f" {x:.2f} {y:.2f}"
        for index, (x, y) in enumerate(points)
    )
    area_path = (
        line_path
        + f" L {points[-1][0]:.2f} {PLOT_BOTTOM}"
        + f" L {points[0][0]:.2f} {PLOT_BOTTOM} Z"
    )

    y_ticks = list(range(0, y_max + step, step))
    x_tick_count = 5
    x_ticks = [
        start + (end - start) * (index / (x_tick_count - 1))
        for index in range(x_tick_count)
    ]
    grid_lines = []
    labels = []
    for value in y_ticks:
        y = y_for(value)
        grid_lines.append(
            f'<line class="grid" x1="{PLOT_LEFT}" y1="{y:.2f}" x2="{PLOT_RIGHT}" y2="{y:.2f}" />'
        )
        labels.append(
            f'<text class="axis" x="{PLOT_LEFT - 12}" y="{y + 4:.2f}" text-anchor="end">{value}</text>'
        )
    for index, value in enumerate(x_ticks):
        x = x_for(value)
        anchor = "start" if index == 0 else ("end" if index == x_tick_count - 1 else "middle")
        labels.append(
            f'<text class="axis" x="{x:.2f}" y="{PLOT_BOTTOM + 27}" text-anchor="{anchor}">{escape(format_tick(value, end - start))}</text>'
        )

    final_x, final_y = points[-1]
    final_label_y = max(PLOT_TOP + 16, final_y - 12)
    star_label = f"{star_total} star" if star_total == 1 else f"{star_total} stars"
    empty_note = ""
    if not stars:
        empty_note = (
            f'<text class="empty" x="{(PLOT_LEFT + PLOT_RIGHT) / 2:.2f}" '
            f'y="{(PLOT_TOP + PLOT_BOTTOM) / 2:.2f}" text-anchor="middle">No stars yet</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">GitHub star history for {escape(repo)}</title>
  <desc id="desc">Cumulative GitHub stars from {start.date().isoformat()} to {end.date().isoformat()}; current total {star_total}.</desc>
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: 0; }}
    .title {{ fill: {palette['text']}; font-size: 18px; font-weight: 600; }}
    .repo {{ fill: {palette['muted']}; font-size: 12px; }}
    .axis {{ fill: {palette['muted']}; font-size: 11px; }}
    .grid {{ stroke: {palette['grid']}; stroke-width: 1; }}
    .line {{ fill: none; stroke: {palette['line']}; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
    .area {{ fill: {palette['area']}; fill-opacity: 0.12; }}
    .dot {{ fill: {palette['line']}; stroke: {palette['plot']}; stroke-width: 3; }}
    .value {{ fill: {palette['text']}; font-size: 12px; font-weight: 600; }}
    .empty {{ fill: {palette['muted']}; font-size: 13px; }}
  </style>
  <rect width="{WIDTH}" height="{HEIGHT}" rx="6" fill="{palette['background']}" />
  <rect x="18" y="18" width="{WIDTH - 36}" height="{HEIGHT - 36}" rx="4" fill="{palette['plot']}" stroke="{palette['border']}" />
  <text class="title" x="{PLOT_LEFT}" y="45">GitHub star history</text>
  <text class="repo" x="{PLOT_RIGHT}" y="44" text-anchor="end">{escape(repo)}</text>
  {''.join(grid_lines)}
  {''.join(labels)}
  <path class="area" d="{area_path}" />
  <path class="line" d="{line_path}" />
  <circle class="dot" cx="{final_x:.2f}" cy="{final_y:.2f}" r="5" />
  <text class="value" x="{PLOT_RIGHT - 12}" y="{final_label_y:.2f}" text-anchor="end">{star_label}</text>
{empty_note}
</svg>
'''


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY is required")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    repository = fetch_repository(args.repo, token)
    stars = fetch_stars(args.repo, token)
    expected = int(repository.get("stargazers_count") or 0)
    if len(stars) != expected:
        print(
            f"warning: fetched {len(stars)} timestamped stars while repository reports {expected}; "
            "rendering the timestamped snapshot"
        )
    created_at = parse_github_datetime(str(repository["created_at"]))
    changed = []
    for theme in THEMES:
        path = args.output_dir / f"star-history-{theme}.svg"
        if write_if_changed(path, render_svg(args.repo, created_at, stars, theme)):
            changed.append(str(path))
    print(f"star history: {len(stars)} stars; updated {len(changed)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
