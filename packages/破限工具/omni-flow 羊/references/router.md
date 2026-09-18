# Skill Router

## Routing algorithm

1. Parse the request into target artifact, platform, action, technique, tool, and expected output.
2. Read the installed skill catalog metadata already exposed to Codex. Compare both `name` and `description`; do not load every `SKILL.md` body. For legacy entries without a description, use the leaf folder name and first Markdown heading as a lower-confidence fallback.
3. Rank candidates in this order:
   - an exact skill name explicitly requested by the user;
   - an exact artifact or technique match;
   - an exact platform or tool match;
   - a specialized leaf skill whose description covers the requested action;
   - a category chain skill;
   - `omni-flow` as the fallback coordinator.
4. Select one primary leaf skill. Select at most one supporting skill when the task has a real second domain, such as APK plus network capture or web upload plus cloud storage.
5. Load only the chosen skill bodies and the references needed for the current phase. State the selected skill names briefly, then execute the task.

## Tie breaking

- Prefer the skill whose description contains the artifact and requested action, not merely a broad domain word.
- Prefer a leaf skill over `full-*`, `*-chain`, framework, or generic workflow skills.
- Prefer a canonical ASCII slug whose folder matches its frontmatter `name` over a legacy alias or duplicate name.
- Prefer a skill with complete frontmatter and a concrete workflow.
- Treat missing `description` as metadata debt: it may be a fallback candidate, but it must lose to a complete exact match.
- If two candidates remain equally strong, inspect only those two `SKILL.md` files and choose the narrower one.
- Ask one short clarification only when choosing the wrong branch could cause a state-changing action. Otherwise start passive triage and refine from evidence.

## Domain hints

| User input suggests | Primary domain | Coordinator reference |
|---|---|---|
| exe, dll, sys, pe, so, elf, binary, crackme, unpack, decompile | Reverse Engineering | `references/reverse-engineering.md` |
| website, api, url, login, auth, session, upload, xss, sqli, idor, webhook | Web Assessment | `references/web-assessment.md` |
| apk, ipa, android, ios, frida, mobile storage, certificate pinning | Mobile Security | `references/mobile-security.md` |
| encrypt, decrypt, hash, cipher, key, signature, token | Cryptography | `references/cryptography.md` |
| crash, exploitability, shellcode, rop, overflow, pwn | Vulnerability Development | `references/vuln-dev.md` |
| malware, virus, trojan, ransomware, suspicious sample | Malware Analysis | `references/malware-analysis.md` |
| firmware, router image, iot, embedded, binwalk | Firmware Analysis | `references/firmware-analysis.md` |
| pcap, packet, protocol, traffic, mitm, dns, tls | Network Analysis | `references/network-analysis.md` |
| domain, ldap, kerberos, active directory, gpo, ticket | Identity / AD | Use the most specific installed AD skill |
| aws, azure, gcp, iam, bucket, metadata, kubernetes | Cloud | Use the most specific installed cloud skill |

## Examples

- `分析这个 APK 的本地敏感数据` -> `apk-static-analysis` plus `mobile-data-storage-leak` only if both are needed.
- `审计登录 Cookie 和会话固定` -> `auth-&-session-attacks`, not the broad Web Attack Chain.
- `判断这个 ELF 是否加壳` -> `elf-file-analysis` or the narrower unpacking skill when its description matches.
- `分析 pcap 里的 DNS 隧道` -> the DNS tunneling skill, with packet analysis only as supporting context.
- `做一次完整 Web 评估` -> a Web chain skill is appropriate because the user explicitly requested broad coverage.

## Duplicate handling

If multiple installed folders declare the same `name`, treat them as one logical skill. Prefer the canonical folder whose basename equals the declared name. Do not load both copies.
