#!/usr/bin/env python3
"""
Omni Flow - Case Workspace Creator
Creates a structured workspace for security research cases.
"""

import argparse
import os
import shutil
import hashlib
import time
from datetime import datetime
from pathlib import Path


def sha256_file(filepath: str) -> str:
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def create_case(case_name: str, goal: str, output: str, artifacts: list = None):
    """Create a structured case workspace."""

    # Base directory
    base = Path(output) / case_name
    base.mkdir(parents=True, exist_ok=True)

    # Directory structure
    dirs = [
        'artifacts',       # Original samples (read-only copies)
        'artifacts/originals',
        'analysis',        # Analysis outputs
        'analysis/static',
        'analysis/dynamic',
        'analysis/memory',
        'evidence',        # Screenshots, logs, proof
        'evidence/screenshots',
        'evidence/logs',
        'evidence/packets',
        'patches',         # Binary patches / modifications
        'reports',         # Final reports
        'scripts',         # Case-specific scripts
        'workspace',       # Working files
    ]

    for d in dirs:
        (base / d).mkdir(parents=True, exist_ok=True)

    # Copy artifacts if provided
    artifact_info = []
    if artifacts:
        for artifact in artifacts:
            artifact_path = Path(artifact)
            if artifact_path.exists():
                dest = base / 'artifacts' / 'originals' / artifact_path.name
                shutil.copy2(artifact_path, dest)
                info = {
                    'name': artifact_path.name,
                    'sha256': sha256_file(str(dest)),
                    'size': dest.stat().st_size,
                    'source': str(artifact_path.resolve()),
                }
                artifact_info.append(info)
                print(f"[+] Artifact copied: {artifact_path.name} ({info['sha256'][:16]}...)")

    # Create README
    readme = f"""# Case: {case_name}

## Meta Information
- **Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Goal**: {goal}
- **Status**: Active

## Artifacts
"""

    if artifact_info:
        readme += "| File | SHA-256 | Size | Source |\n"
        readme += "|------|---------|------|--------|\n"
        for a in artifact_info:
            readme += f"| {a['name']} | `{a['sha256'][:16]}...` | {a['size']} bytes | {a['source']} |\n"
    else:
        readme += "No artifacts added yet.\n"

    readme += """
## Directory Structure

```
├── artifacts/
│   └── originals/     # Original samples (DO NOT MODIFY)
├── analysis/
│   ├── static/        # Static analysis results
│   ├── dynamic/       # Dynamic analysis results
│   └── memory/        # Memory dumps
├── evidence/
│   ├── screenshots/   # Evidence screenshots
│   ├── logs/          # Tool logs and output
│   └── packets/       # Network captures
├── patches/           # Binary patches
├── reports/           # Final reports
├── scripts/           # Case-specific automation
└── workspace/         # Temporary working files
```

## Notes
<!-- Add your notes here -->
"""
    (base / 'README.md').write_text(readme, encoding='utf-8')

    # Create initial report template
    report = f"""# Analysis Report: {case_name}

## Executive Summary
*To be completed*

## Findings Summary
| # | Severity | Type | Status |
|---|----------|------|--------|
| - | - | - | - |

## Detailed Findings
### Finding 1: [Title]
**Severity**: High
**Type**: [Category]
**Status**: Under Investigation

### Description
...

### Evidence
...

### Remediation
...

## IOCs
```yaml
network:
  domains: []
  ips: []
  urls: []

filesystem:
  paths: []

hashes:
  md5: []
  sha256: []

mutexes: []
```

## Timeline
| Time | Event |
|------|-------|
| - | - |

## Appendix
- Tools used:
- Command log:
"""
    (base / 'reports' / 'initial-template.md').write_text(report, encoding='utf-8')

    print(f"\n[+] Case created: {base.resolve()}")
    print(f"    Goal: {goal}")
    print(f"    Artifacts: {len(artifact_info)} file(s)")
    return str(base.resolve())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Omni Flow Case Creator')
    parser.add_argument('--case-name', required=True, help='Case identifier name')
    parser.add_argument('--goal', required=True, help='Analysis goal description')
    parser.add_argument('--out', default='./cases', help='Output base directory')
    parser.add_argument('artifacts', nargs='*', help='Artifact files to include')

    args = parser.parse_args()
    create_case(args.case_name, args.goal, args.out, args.artifacts)