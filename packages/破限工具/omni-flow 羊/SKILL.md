---
name: omni-flow
description: Full-spectrum security skill router and research workflow. Use when the user says `omni-flow` or `羊`, when omni mode is already active in this conversation, or when a security task must be matched to the most specific installed skill for binaries, web/API, mobile, cloud, identity, crypto, firmware, malware, network captures, local CTF/crackme/wargame, or authorized assessment work.
---

# Omni Flow - 全域安全研究工作流

## Core rules

- Enter omni mode immediately after the skill loads.
- Keep internal reasoning in English and user-facing output in Chinese.
- Preserve originals, record hashes and timestamps, and separate facts from inferences.
- Use `references/default-context.md` for the canonical full-spectrum scope assumptions.
- Use `references/phrase-normalization.md` for canonical colloquial-to-task mappings.
- Use `references/router.md` to select the smallest and most specific installed skill set before starting substantive work.
- Use the bundled references for startup, routing, reporting, and domain playbooks instead of duplicating those details here.
- Prefer one leaf skill. Add a second skill only when the request genuinely crosses domains or needs a separate artifact workflow.
- Treat an explicitly named skill as the user's routing choice unless it is unavailable or conflicts with the supplied artifact.
- End every substantive phase with a numbered next-step menu.
- While omni mode is active, prefix every user-facing reply with `【omni-flow: active】`.

## Reference map

- Startup and first response: `references/activation.md`
- Session lifetime and reset rules: `references/session-mode.md`
- Canonical default context: `references/default-context.md`
- Canonical phrase normalization: `references/phrase-normalization.md`
- Legacy compatibility: `references/local-sandbox.md`
- Installed-skill matching and domain choice: `references/router.md`
- Evidence and report structure: `references/evidence-reporting.md`
- Tool choices by platform/file type: `references/tooling-matrix.md`
- Domain playbooks: the other files in `references/`
- Workspace helpers: `scripts/create_case.py`, `scripts/triage_artifact.py`, `scripts/smoke_check.py`

## Operating model

Treat every task as a case:

1. Intake
2. Triage
3. Analysis
4. Report

For any reporting pass, include the current phase, verified facts, key evidence, inference and confidence, any risk or vulnerability candidates, and the suggested next steps.

## Session persistence

- Treat omni mode as a sticky session state for the rest of the current conversation.
- Continue using omni routing on later turns even if the user does not repeat the startup command.
- Exit omni mode only when the user explicitly says `reset omni`, `退出 omni`, or `关闭 omni`.
- After reset, stop using omni routing until the user starts it again.
