# -*- coding: utf-8 -*-
"""Email spoofing tools -- header manipulation, DMARC/SPF analysis.

Author: zxwn
"""
import socket, re


def check_dmarc(domain: str) -> dict:
    """Check DMARC DNS record for spoofability."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve("_dmarc." + domain, "TXT")
        for rdata in answers:
            txt = str(rdata).strip('"')
            if "v=DMARC1" in txt:
                policy = re.search(r"p=(\w+)", txt)
                pct = re.search(r"pct=(\d+)", txt)
                return {
                    "dmarc_record": txt,
                    "policy": policy.group(1) if policy else "none",
                    "pct": int(pct.group(1)) if pct else 100,
                    "spoofable": (policy and policy.group(1) == "none"),
                }
        return {"dmarc_record": None, "spoofable": True, "reason": "No DMARC"}
    except ImportError:
        return {"error": "pip install dnspython"}
    except Exception as e:
        return {"error": str(e), "spoofable": "unknown"}


def check_spf(domain: str) -> dict:
    """Check SPF record for allowed senders."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "TXT")
        for rdata in answers:
            txt = str(rdata).strip('"')
            if "v=spf1" in txt:
                all_match = re.search(r"([~\-?+]all)", txt)
                includes = re.findall(r"include:([^\s]+)", txt)
                ip4s = re.findall(r"ip4:([^\s]+)", txt)
                return {
                    "spf_record": txt,
                    "all_mechanism": all_match.group(1) if all_match else None,
                    "includes": includes,
                    "ip4s": ip4s,
                    "spoofable": all_match and all_match.group(1) in ("?all", "+all"),
                }
        return {"spf_record": None, "spoofable": True}
    except ImportError:
        return {"error": "pip install dnspython"}
    except:
        return {"error": "DNS lookup failed"}


def craft_smtp_spoof(smtp_server: str, sender: str, recipient: str,
                     subject: str, body: str) -> str:
    """Generate raw SMTP commands for email spoofing."""
    commands = [
        "EHLO mail.example.com",
        "MAIL FROM:<{}>".format(sender),
        "RCPT TO:<{}>".format(recipient),
        "DATA",
        "From: {} <{}>".format(sender.split("@")[0], sender),
        "To: {}".format(recipient),
        "Subject: {}".format(subject),
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=utf-8",
        "",
        body,
        ".",
        "QUIT",
    ]
    return "\r\n".join(commands)


if __name__ == "__main__":
    print("[spoof_tools] Loaded.")
    result = check_dmarc("example.com")
    for k, v in result.items():
        print("  {}: {}".format(k, v))
