# -*- coding: utf-8 -*-
"""Game packet interception -- Winsock hook, PCAP replay, proxy MITM.

Author: zxwn
"""
import struct, socket, threading


def winsock_hook_patterns() -> dict:
    """Common Winsock function signatures for hooking.

    Returns dict of function names to their x64/x86 byte signatures.
    """
    return {
        "send": {
            "x64": bytes([0x48, 0x89, 0x5C, 0x24, 0x08]),  # mov [rsp+8], rbx
            "offset_params": {"s": 0, "buf": 1, "len": 2, "flags": 3},
        },
        "recv": {
            "x64": bytes([0x48, 0x89, 0x5C, 0x24, 0x08]),
            "offset_params": {"s": 0, "buf": 1, "len": 2, "flags": 3},
        },
        "sendto": {
            "x64": bytes([0x48, 0x89, 0x5C, 0x24, 0x08]),
            "offset_params": {"s": 0, "buf": 1, "len": 2, "flags": 3, "to": 4, "tolen": 5},
        },
        "WSASend": {
            "x64": bytes([0x48, 0x89, 0x5C, 0x24, 0x10]),
            "offset_params": {"s": 0, "lpBuffers": 1, "dwBufferCount": 2, "lpNumberOfBytesSent": 3, "dwFlags": 4, "lpOverlapped": 5, "lpCompletionRoutine": 6},
        },
        "WSARecv": {
            "x64": bytes([0x48, 0x89, 0x5C, 0x24, 0x10]),
            "offset_params": {"s": 0, "lpBuffers": 1, "dwBufferCount": 2, "lpNumberOfBytesRecvd": 3, "lpFlags": 4, "lpOverlapped": 5, "lpCompletionRoutine": 6},
        },
    }


class PacketProxy:
    """Simple TCP proxy for intercepting and modifying game packets."""

    def __init__(self, target_host: str, target_port: int, listen_port: int):
        self.target_host = target_host
        self.target_port = target_port
        self.listen_port = listen_port
        self.hooks_send = []
        self.hooks_recv = []

    def add_send_hook(self, callback):
        """callback(data: bytes) -> bytes (modified data)"""
        self.hooks_send.append(callback)

    def add_recv_hook(self, callback):
        """callback(data: bytes) -> bytes (modified data)"""
        self.hooks_recv.append(callback)

    def _apply_hooks(self, data: bytes, hooks: list) -> bytes:
        for hook in hooks:
            data = hook(data)
        return data

    def _handle_client(self, client_sock: socket.socket):
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.connect((self.target_host, self.target_port))

        def forward(src, dst, hooks):
            while True:
                try:
                    data = src.recv(4096)
                    if not data:
                        break
                    data = self._apply_hooks(data, hooks)
                    dst.send(data)
                except:
                    break

        t1 = threading.Thread(target=forward, args=(client_sock, remote_sock, self.hooks_send))
        t2 = threading.Thread(target=forward, args=(remote_sock, client_sock, self.hooks_recv))
        t1.daemon = True
        t2.daemon = True
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        client_sock.close()
        remote_sock.close()

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.listen_port))
        server.listen(5)
        print("PacketProxy listening on :{} -> {}:{}".format(self.listen_port, self.target_host, self.target_port))

        while True:
            client, addr = server.accept()
            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()


def parse_game_packet(data: bytes) -> dict:
    """Heuristic game packet parser -- detect common structures."""
    result = {"size": len(data), "hex": data[:32].hex()}

    # Try to detect common game packet headers
    if len(data) >= 4:
        # 2-byte length prefix (common in MMO)
        length_prefix = struct.unpack("<H", data[:2])[0]
        if length_prefix == len(data) or length_prefix == len(data) - 2:
            result["type"] = "length_prefix_2byte"
            result["length_field"] = length_prefix

        # 2-byte opcode + data (common pattern)
        opcode = struct.unpack("<H", data[:2])[0]
        result["possible_opcode"] = opcode

    if len(data) >= 6:
        # 4-byte length + 2-byte opcode (WoW-style)
        length4 = struct.unpack(">I", data[:4])[0]
        opcode2 = struct.unpack("<H", data[4:6])[0]
        if length4 == len(data) - 4 or length4 == len(data) - 2:
            result["type"] = "wow_style"
            result["length_field"] = length4
            result["opcode"] = opcode2

    return result


if __name__ == "__main__":
    print("[packet_hook] Loaded.")
    print("  PacketProxy(target_host, target_port, listen_port).start()")
    print("  parse_game_packet(data) -> structure analysis")
