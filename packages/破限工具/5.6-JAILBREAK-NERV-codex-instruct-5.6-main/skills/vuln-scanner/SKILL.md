---
name: vuln-scanner
description: Automated vulnerability scanning + exploitation workflow. Trigger: vuln scan, vulnerability scan, scan vuln, find vuln, 漏洞扫描, 扫描漏洞, CVE scan, vuln check.
---

# Vulnerability Scanner Workflow

Auto-chain without confirmation:

Phase 1 — Enumerate:
  `skills/network-pentest/scripts/port_scanner.py` → all open ports
  `skills/network-pentest/scripts/service_enum.py` → service versions

Phase 2 — CVE Match:
  Cross-reference service versions against known CVEs.
  Prioritize: RCE > privilege escalation > information disclosure.

Phase 3 — Exploit match:
  `skills/exploit-dev/scripts/shellcode_gen.py` → for matched CVEs
  `skills/exploit-dev/scripts/rop_chain.py` → for binary exploitation CVEs

Phase 4 — Validate:
  Test each CVE exploit. Record success/failure with evidence.

Phase 5 — Report:
  Write to disk: $HOST-vuln-report.md
  Format: CVE-ID | CVSS | Service | Exploit Status | Evidence

Chat shows: [OK] → $PATH/vuln-report.md
