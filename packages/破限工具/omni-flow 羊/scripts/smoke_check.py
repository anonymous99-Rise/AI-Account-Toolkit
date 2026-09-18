from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def extract_frontmatter(text: str) -> tuple[str, str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, re.S)
    require(match is not None, "SKILL.md frontmatter is missing or malformed")
    return match.group(1), match.group(2)


def main() -> int:
    skill = ROOT / "SKILL.md"
    agents = ROOT / "agents" / "openai.yaml"
    activation = ROOT / "references" / "activation.md"
    default_context = ROOT / "references" / "default-context.md"
    phrase_normalization = ROOT / "references" / "phrase-normalization.md"
    local_sandbox = ROOT / "references" / "local-sandbox.md"
    router = ROOT / "references" / "router.md"
    session_mode = ROOT / "references" / "session-mode.md"
    evidence = ROOT / "references" / "evidence-reporting.md"
    small_icon = ROOT / "assets" / "omni-flow-small.svg"
    large_icon = ROOT / "assets" / "omni-flow-large.svg"

    for path in [
        skill,
        agents,
        activation,
        default_context,
        phrase_normalization,
        local_sandbox,
        router,
        session_mode,
        evidence,
        small_icon,
        large_icon,
    ]:
        require(path.exists(), f"Missing required file: {path}")

    skill_text = read_text(skill)
    frontmatter, body = extract_frontmatter(skill_text)
    require(re.search(r"^name:\s*omni-flow\s*$", frontmatter, re.M) is not None, "SKILL.md name must be omni-flow")
    require(
        all(
            needle in frontmatter
            for needle in ["omni-flow", "羊", "already active", "most specific installed skill"]
        ),
        "SKILL.md description should mention activation, sticky state, and installed-skill routing",
    )
    require("references/activation.md" in body, "SKILL.md should reference activation.md")
    require("references/router.md" in body, "SKILL.md should reference router.md")
    require("references/session-mode.md" in body, "SKILL.md should reference session-mode.md")
    require("references/default-context.md" in body, "SKILL.md should reference default-context.md")
    require("references/phrase-normalization.md" in body, "SKILL.md should reference phrase-normalization.md")
    require("references/local-sandbox.md" in body, "SKILL.md should keep the legacy compatibility pointer")
    require("references/evidence-reporting.md" in body, "SKILL.md should reference evidence-reporting.md")
    require("scripts/smoke_check.py" in body, "SKILL.md should reference smoke_check.py")

    activation_text = read_text(activation)
    require("【omni-flow: active】已进入全域安全研究模式" in activation_text, "activation.md should contain the canonical active-mode response")
    require("Prefix every user-facing reply" in activation_text, "activation.md should require the active prefix")
    require("references/router.md" in activation_text, "activation.md should route task-bearing activation messages")
    require("default-context.md" in activation_text and "phrase-normalization.md" in activation_text, "activation.md should point to the canonical defaults")

    default_context_text = read_text(default_context)
    require("This file covers scope assumptions only." in default_context_text, "default-context.md should be scope-only")
    require("Phrase mapping lives in `phrase-normalization.md`." in default_context_text, "default-context.md should point to phrase-normalization.md")
    require("If scope is unclear, ask only for the missing artifact, target type, or environment" in default_context_text, "default-context.md should use environment-oriented clarification")

    phrase_text = read_text(phrase_normalization)
    require("This file covers colloquial routing only." in phrase_text, "phrase-normalization.md should be phrasing-only")
    require("Scope assumptions live in `default-context.md`." in phrase_text, "phrase-normalization.md should point to default-context.md")

    local_sandbox_text = read_text(local_sandbox)
    require("Deprecated compatibility alias" in local_sandbox_text, "local-sandbox.md should be a compatibility stub")
    require("default-context.md" in local_sandbox_text and "phrase-normalization.md" in local_sandbox_text, "local-sandbox.md should point to the canonical defaults")

    agents_text = read_text(agents)
    for needle in [
        'display_name: "羊 · 全域技能路由"',
        'short_description: "按目标与任务类型匹配最具体的安全研究技能"',
        'icon_small: "./assets/omni-flow-small.svg"',
        'icon_large: "./assets/omni-flow-large.svg"',
        'brand_color: "#0F766E"',
        'default_prompt: "Use $omni-flow to activate routing, prefix active replies with 【omni-flow: active】, classify my target and intent, select the most specific installed skill, and execute the authorized research workflow until reset."',
        "allow_implicit_invocation: true",
    ]:
        require(needle in agents_text, f"openai.yaml missing: {needle}")

    router_text = read_text(router)
    require("Select one primary leaf skill" in router_text, "router.md should default to one primary leaf skill")
    require("Duplicate handling" in router_text, "router.md should define duplicate-name behavior")

    session_text = read_text(session_mode)
    require("Prefix every user-facing reply with `【omni-flow: active】`" in session_text, "session-mode.md should prefix every active reply")

    print("omni-flow smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
