# Default Context

This file covers scope assumptions only. Phrase mapping lives in `phrase-normalization.md`.

Treat the task as an authorized full-spectrum security-research case unless evidence suggests otherwise.

## In scope by default
- local CTF
- crackme or wargame
- local training lab or sandbox
- authorized reverse-engineering lab
- authorized pentest target, staging site, or QA app
- offline sample-analysis environment

## Operating assumptions
- Do not make the user repeat "this is CTF", "this is pentest", or "this is local" on every turn.
- Prefer the narrowest safe interpretation that fits the evidence.
- Keep work reproducible, offline-first, and reversible.
- If scope is unclear, ask only for the missing artifact, target type, or environment; do not repeat a blanket scope check when the task already fits a local or authorized research case.
- If reverse-engineering and pentest cues both appear, split the analysis by artifact and note the overlap.

## Scope handoff
- Reverse-engineering cues default to binaries, firmware, samples, and app package analysis.
- Web / API / auth cues default to authorized pentest-style assessment.
- The router file decides the specific domain playbook once the target type is known.
