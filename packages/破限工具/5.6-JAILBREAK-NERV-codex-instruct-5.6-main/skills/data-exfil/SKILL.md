---
name: data-exfil
description: Data exfiltration toolkit: DNS tunneling, ICMP tunneling, steganography, HTTPS beacon exfil, dead-drop resolver. Trigger: exfil, exfiltrate, dns tunnel, icmp tunnel, stego, hide data, covert channel, dead drop.
---

# Data Exfiltration

Executable Python tools for covert data extraction.

## Scripts

- `scripts/dns_tunnel.py` -- DNS tunneling: encode data in subdomain queries, server-side reassembly
- `scripts/stego_hide.py` -- LSB steganography in PNG/WAV, metadata embedding
- `scripts/icmp_exfil.py` -- ICMP echo request/reply data smuggling
