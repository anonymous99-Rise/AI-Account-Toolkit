# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_star_history


def test_render_star_history_light_and_dark():
    created = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)
    stars = [created + timedelta(hours=value) for value in (1, 3, 8, 26, 44)]
    light = update_star_history.render_svg("owner/repo", created, stars, "light")
    dark = update_star_history.render_svg("owner/repo", created, stars, "dark")
    for rendered in (light, dark):
        assert '<title id="title">GitHub star history for owner/repo</title>' in rendered
        assert "current total 5" in rendered
        assert ">5 stars</text>" in rendered
        assert 'class="line"' in rendered
        assert "nan" not in rendered.lower()
        assert "inf" not in rendered.lower()
    assert light != dark
    assert update_star_history.THEMES["light"]["background"] in light
    assert update_star_history.THEMES["dark"]["background"] in dark


def test_render_empty_and_single_star_are_not_blank():
    created = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)
    empty = update_star_history.render_svg("owner/repo", created, [], "light")
    single = update_star_history.render_svg(
        "owner/repo", created, [created + timedelta(minutes=5)], "light"
    )
    assert "No stars yet" in empty
    assert ">0 stars</text>" in empty
    assert "No stars yet" not in single
    assert ">1 star</text>" in single
    assert 'd="M ' in single


def test_nice_step_scales_for_small_and_large_repositories():
    assert update_star_history.nice_step(0) == 1
    assert update_star_history.nice_step(5) == 1
    assert update_star_history.nice_step(278) == 100
    assert update_star_history.nice_step(1250) == 500


if __name__ == "__main__":
    test_render_star_history_light_and_dark()
    test_render_empty_and_single_star_are_not_blank()
    test_nice_step_scales_for_small_and_large_repositories()
    print("OK star history")
