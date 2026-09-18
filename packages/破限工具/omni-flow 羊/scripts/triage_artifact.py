#!/usr/bin/env python3
"""
Omni Flow - Artifact Triage Tool
Collects basic information about security research artifacts.
"""

import argparse
import hashlib
import os
import sys
import math
from pathlib import Path
from datetime import datetime


def calculate_entropy(data: bytes) -> float:
    """Calculate Shannon entropy of data (0.0 to 8.0)."""
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    length = len(data)
    entropy = -sum((c / length) * math.log2(c / length) for c in freq if c > 0)
    return entropy


def detect_file_type(filepath: str) -> dict:
    """Detect file type using magic bytes and heuristics."""
    result = {'type': 'unknown', 'confidence': 'low', 'details': {}}

    with open(filepath, 'rb') as f:
        header = f.read(4096)

    # Check size
    result['details']['size'] = len(header)

    # Magic bytes detection
    magic_map = {
        b'MZ': ('PE/EXE', 'high'),
        b'\x7fELF': ('ELF', 'high'),
        b'\xca\xfe\xba\xbe': ('Mach-O Fat', 'high'),
        b'\xce\xfa\xed\xfe': ('Mach-O 32-bit', 'high'),
        b'\xcf\xfa\xed\xfe': ('Mach-O 64-bit', 'high'),
        b'PK\x03\x04': ('ZIP/APK/JAR/IPA/DOCX/PPTX/XLSX', 'high'),
        b'%PDF': ('PDF', 'high'),
        b'\x1f\x8b': ('GZIP', 'high'),
        b'BZh': ('BZIP2', 'high'),
        b'Rar!': ('RAR', 'high'),
        b'\x89PNG': ('PNG', 'high'),
        b'\xff\xd8\xff': ('JPEG', 'high'),
        b'GIF8': ('GIF', 'high'),
        b'Salted__': ('OpenSSL Encrypted', 'high'),
        b'-----BEGIN': ('PEM/Certificate/Key', 'high'),
        b'SQLite format 3': ('SQLite Database', 'high'),
        b'dex\n': ('DEX (Android)', 'high'),
        b'\x02\x00\x0c': ('Office Compound Document (OLE)', 'medium'),
        b'{\\rtf': ('RTF', 'high'),
        b'<html': ('HTML/XML', 'medium'),
        b'<?xml': ('XML', 'medium'),
        b'#!/bin/sh': ('Shell Script', 'high'),
        b'#! /bin/sh': ('Shell Script', 'high'),
        b'#!/usr/bin/env python': ('Python Script', 'high'),
        b'#!/usr/bin/python': ('Python Script', 'high'),
        b'<?php': ('PHP Script', 'high'),
        b'<%': ('ASP/JSP Script', 'medium'),
        b'hsqs': ('SquashFS', 'high'),
        b'shft': ('CramFS', 'high'),
        b'\x68\x73\x71\x74': ('HSQS/SquashFS variant', 'high'),
    }

    for magic, (ftype, conf) in magic_map.items():
        if header[:len(magic)] == magic:
            result['type'] = ftype
            result['confidence'] = conf
            break

    # Additional checks
    if header[:2] == b'MZ':
        # PE specific checks
        if b'This program cannot be run in DOS mode' in header[:512]:
            result['details']['pe_type'] = 'PE32/PE32+'
            result['details']['dos_stub'] = True

        # Check for .NET
        if b'.NET' in header or b'mscoree.dll' in header:
            result['details']['runtime'] = '.NET'

    elif result['type'] in ('ZIP/APK/JAR/IPA/DOCX/PPTX/XLSX',):
        # Distinguish ZIP variants
        data_str = header[:1024].decode('latin-1', errors='ignore')
        if 'AndroidManifest.xml' in data_str or 'classes.dex' in data_str:
            result['type'] = 'APK (Android Package)'
            result['confidence'] = 'high'
        elif 'Payload/' in data_str:
            result['type'] = 'IPA (iOS Application)'
            result['confidence'] = 'high'
        elif '[Content_Types].xml' in data_str:
            result['type'] = 'Office Open XML (DOCX/PPTX/XLSX)'
            result['confidence'] = 'high'

    return result


def extract_strings(data: bytes, min_length: int = 6) -> list:
    """Extract ASCII strings from binary data."""
    results = []
    current = []

    for byte in data:
        if 32 <= byte < 127:  # Printable ASCII
            current.append(chr(byte))
        else:
            if len(current) >= min_length:
                results.append(''.join(current))
            current = []

    if len(current) >= min_length:
        results.append(''.join(current))

    return results


def categorize_strings(strings_list: list) -> dict:
    """Categorize strings into security-relevant categories."""
    categories = {
        'urls': [],
        'ips': [],
        'domains': [],
        'paths': [],
        'registry': [],
        'crypto': [],
        'network_api': [],
        'process_api': [],
        'file_api': [],
        'suspicious': [],
    }

    import re

    url_pattern = re.compile(r'https?://[^\s\"\'<>\]]+', re.IGNORECASE)
    ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    domain_pattern = re.compile(r'(?:https?://)?(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}(?:[/\s]|$)', re.IGNORECASE)

    path_patterns = [
        re.compile(r'[A-Za-z]:\\[^\s]*', re.IGNORECASE),  # Windows path
        re.compile(r'/(?:etc|usr|var|tmp|home|opt|root|bin|sbin|lib)[/\w.-]*'),  # Unix path
        re.compile(r'(?:Users|Windows|Program Files|System32|AppData|Temp)[/\\\w.-]*', re.IGNORECASE),
    ]

    registry_pattern = re.compile(r'HKEY_[A-Z_]+\\\\[^\s]+', re.IGNORECASE)

    crypto_keywords = ['encrypt', 'decrypt', 'cipher', 'aes', 'rsa', 'sha', 'md5',
                       'password', 'secret', 'key', 'token', 'certificate', 'pbkdf2']

    network_apis = ['InternetConnect', 'HttpSendRequest', 'send', 'connect',
                    'socket', 'bind', 'listen', 'accept', 'recv', 'urlmon',
                    'WinHttp', 'WinInet', 'curl_easy', 'requests.', 'urllib']

    process_apis = ['CreateProcess', 'OpenProcess', 'WriteProcessMemory',
                    'CreateRemoteThread', 'VirtualAllocEx', 'ShellExecute',
                    'system(', 'popen(', 'exec(', 'fork(']

    file_apis = ['CreateFile', 'ReadFile', 'WriteFile', 'DeleteFile',
                 'GetPrivateProfileString', 'RegOpenKeyEx', 'RegSetValueEx']

    suspicious_keywords = ['eval(', 'base64_decode', 'shell_exec', 'passthru',
                           'system(', 'exec(', 'cmd.exe', 'powershell', 'certutil',
                           'bitsadmin', 'wmic', 'rundll32', 'regsvr32']

    for s in strings_list:
        s_lower = s.lower()

        # URLs
        if url_pattern.search(s):
            categories['urls'].append(s)

        # IPs
        ips = ip_pattern.findall(s)
        categories['ips'].extend(ips)

        # Domains
        if domain_pattern.search(s) and not any(x in s_lower for x in ['http://', 'https://']):
            categories['domains'].append(s)

        # Paths
        for pat in path_patterns:
            if pat.search(s):
                categories['paths'].append(s)
                break

        # Registry
        if registry_pattern.search(s):
            categories['registry'].append(s)

        # Crypto
        if any(kw in s_lower for kw in crypto_keywords):
            categories['crypto'].append(s)

        # Network APIs
        if any(api.lower() in s_lower for api in network_apis):
            categories['network_api'].append(s)

        # Process APIs
        if any(api.lower() in s_lower for api in process_apis):
            categories['process_api'].append(s)

        # File APIs
        if any(api.lower() in s_lower for api in file_apis):
            categories['file_api'].append(s)

        # Suspicious
        if any(kw in s_lower for kw in suspicious_keywords):
            categories['suspicious'].append(s)

    return categories


def triage(artifact: str, output_dir: str = None):
    """Perform full triage on an artifact."""
    filepath = Path(artifact)
    if not filepath.exists():
        print(f"[-] File not found: {artifact}")
        return None

    print(f"[*] Triaging: {filepath.name}")
    print("=" * 60)

    with open(filepath, 'rb') as f:
        data = f.read()

    # Basic info
    sha256 = hashlib.sha256(data).hexdigest()
    md5 = hashlib.md5(data).hexdigest()
    sha1 = hashlib.sha1(data).hexdigest()

    print(f"[+] Size: {len(data):,} bytes ({len(data)/1024:.1f} KB)")
    print(f"[+] MD5:    {md5}")
    print(f"[+] SHA-1:  {sha1}")
    print(f"[+] SHA-256: {sha256}")
    print(f"[+] Entropy: {calculate_entropy(data):.2f} / 8.00")

    # File type
    ft = detect_file_type(str(filepath))
    print(f"\n[+] Type: {ft['type']} (confidence: {ft['confidence']})")
    if ft['details']:
        for k, v in ft['details'].items():
            print(f"    {k}: {v}")

    # Strings analysis
    print(f"\n[*] Extracting strings (min length=6)...")
    strings_list = extract_strings(data, min_length=6)
    print(f"[+] Found {len(strings_list)} strings")

    # Categorize
    cats = categorize_strings(strings_list)

    def print_category(name, items, max_show=10):
        if items:
            print(f"\n[!] {name} ({len(items)} found):")
            for item in items[:max_show]:
                print(f"    {item}")
            if len(items) > max_show:
                print(f"    ... and {len(items) - max_show} more")

    print_category("URLs", cats['urls'])
    print_category("IP Addresses", set(cats['ips']))
    print_category("Domains", cats['domains'])
    print_category("File Paths", cats['paths'][:15])
    print_category("Registry Keys", cats['registry'][:10])
    print_category("Crypto-related", cats['crypto'][:10])
    print_category("Network API references", set(cats['network_api'])[:10])
    print_category("Process API references", set(cats['process_api'])[:10])
    print_category("Suspicious patterns", cats['suspicious'][:10])

    # Generate report
    report = f"""# Triage Report: {filepath.name}

## Basic Information
| Property | Value |
|----------|-------|
| Filename | {filepath.name} |
| Size | {len(data):,} bytes |
| MD5 | `{md5}` |
| SHA-1 | `{sha1}` |
| SHA-256 | `{sha256}` |
| Entropy | {calculate_entropy(data):.2f} / 8.00 |
| Type | {ft['type']} |

## String Analysis
### Summary
- Total strings (≥6 chars): {len(strings_list)}

### Categories
"""

    for cat_name, cat_items in [
        ("URLs", cats['urls']),
        ("IP Addresses", list(set(cats['ips']))),
        ("Domains", cats['domains']),
        ("File Paths", cats['paths'][:20]),
        ("Registry Keys", cats['registry'][:15]),
        ("Crypto-related", cats['crypto'][:15]),
        ("Network APIs", list(set(cats['network_api']))[:15]),
        ("Process APIs", list(set(cats['process_api']))[:15]),
        ("Suspicious Patterns", cats['suspicious'][:15]),
    ]:
        if cat_items:
            report += f"\n#### {cat_name}\n"
            for item in cat_items:
                report += f"- `{item}`\n"

    # Save report
    out_dir = Path(output_dir) if output_dir else Path('.')
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{filepath.name}_triage.md"
    report_path.write_text(report, encoding='utf-8')

    # Save raw strings
    strings_path = out_dir / f"{filepath.name}_strings.txt"
    strings_path.write_text('\n'.join(strings_list), encoding='utf-8')

    print(f"\n[+] Report saved to: {report_path.resolve()}")
    print(f"[+] Strings saved to: {strings_path.resolve()}")

    return {
        'path': str(filepath.resolve()),
        'size': len(data),
        'md5': md5,
        'sha256': sha256,
        'entropy': round(calculate_entropy(data), 2),
        'type': ft['type'],
        'categories': {k: len(v) for k, v in cats.items() if v},
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Omni Flow Artifact Triage Tool')
    parser.add_argument('artifact', help='Artifact file to triage')
    parser.add_argument('--out', default='./triage', help='Output directory for reports')

    args = parser.parse_args()
    triage(args.artifact, args.out)