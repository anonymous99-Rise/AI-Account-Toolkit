# Changelog

## Unreleased

- Supervise headless batches and automatically resume remaining task slots after a Playwright/Camoufox driver crash or stall.
- Persist batch slot progress atomically so completed accounts are not repeated during recovery.
- Make panel process management and batch launch platform-aware: `psutil` discovery, Linux auto-Xvfb, macOS direct launch, Windows virtualenv paths, and actionable missing-procfs errors.

## 0.2.0 - 2026-07-30

- Redesign the live panel with responsive light and dark themes.
- Add a dedicated usage and troubleshooting view.
- Add pending SSO and account-file recovery with success dequeue.
- Move learned ASN rules from Python source into locked JSON state.
- Scope process discovery and termination to one project root.
- Require monitor authentication for operational read and write APIs.
- Add security headers, bounded request bodies, and redacted log output.
- Create runtime credentials, account data, logs, state, and PID files owner-only.
- Add release tests, CI, a systemd service template, and deployment checks.
