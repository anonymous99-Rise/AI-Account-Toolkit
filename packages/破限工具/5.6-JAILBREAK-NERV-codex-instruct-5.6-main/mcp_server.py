# -*- coding: utf-8 -*-
"""NERV-BREAK-5.6 MCP Server — Kali Linux + Security Tools

Exposes security tools as MCP tools for Codex CLI.
Supports: nmap, sqlmap, hydra, metasploit, john, hashcat, wireshark, burp, etc.

Usage:
  python mcp_server.py                          # stdio mode (Codex MCP)
  python mcp_server.py --port 9000              # HTTP mode (debug)
  python mcp_server.py --kali --ssh root@kali   # Remote Kali via SSH

Author: zxwn
"""
import sys, os, json, subprocess, threading, time, re, shlex
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ═══════════════════════════════════════════════════════════
# TOOL DEFINITIONS — loaded from tools/tools.json
# ═══════════════════════════════════════════════════════════
def load_tools():
    """Load tool definitions from tools/tools.json, fallback to built-in."""
    tools_file = BASE / "tools" / "tools.json"
    if tools_file.exists():
        try:
            data = json.loads(tools_file.read_text(encoding="utf-8"))
            tools = {}
            config = data.get("_config", {})
            for t in data.get("tools", []):
                tools[t["name"]] = {
                    "description": t["desc"],
                    "params": t["params"],
                    "cmd": t["cmd"],
                }
            return tools, config
        except Exception as e:
            print(f"[MCP] Warning: tools.json error: {e}, using defaults")
    return _BUILTIN_TOOLS, {}

_BUILTIN_TOOLS = {
    "python_exec": {"description": "Execute Python code", "params": ["code"], "cmd": "python -c '{code}'"},
    "shell_exec": {"description": "Execute shell command", "params": ["command"], "cmd": "{command}"},
    "powershell_exec": {"description": "Execute PowerShell command", "params": ["command"], "cmd": "powershell -Command \"{command}\""},
}
TOOLS = {}
TOOL_CONFIG = {}

# ═══════════════════════════════════════════════════════════
# BACKENDS — Kali Linux access methods
# ═══════════════════════════════════════════════════════════
BACKEND = "local"       # local | wsl | docker | ssh
KALI_SSH = None         # "root@192.168.1.100"
DOCKER_CONTAINER = None # "kali-tools"
WSL_DISTRO = "kali-linux"

def detect_backend():
    """Auto-detect available Kali backend."""
    global BACKEND
    # Check WSL
    try:
        r = subprocess.run(["wsl", "-d", WSL_DISTRO, "echo", "OK"], capture_output=True, text=True, timeout=30)
        if "OK" in r.stdout:
            BACKEND = "wsl"
            return "wsl"
    except: pass
    # Check Docker
    try:
        r = subprocess.run(["docker", "ps", "--filter", "name=kali-tools", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10)
        if "kali" in r.stdout.lower():
            DOCKER_CONTAINER = r.stdout.strip()
            BACKEND = "docker"
            return "docker"
    except: pass
    return "local"

def run_tool(cmd, timeout=600):
    """Execute tool via current backend."""
    if BACKEND == "wsl":
        r = subprocess.run(
            ["wsl", "-d", WSL_DISTRO, "bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout + "\n" + r.stderr
    elif BACKEND == "docker":
        r = subprocess.run(
            ["docker", "exec", DOCKER_CONTAINER or "kali-tools", "bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout + "\n" + r.stderr
    elif BACKEND == "ssh":
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5", KALI_SSH, cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout + "\n" + r.stderr
    else:
        # Local Windows — try directly, fall back to wsl if command not found
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(BASE))
            return r.stdout + "\n" + r.stderr
        except FileNotFoundError:
            # Try WSL as fallback
            try:
                r = subprocess.run(["wsl", "bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
                return r.stdout + "\n" + r.stderr
            except:
                return f"Error: tool not found. Install via WSL Kali or add to PATH.\nCommand: {cmd}"

# ═══════════════════════════════════════════════════════════
# MCP Protocol Handler
# ═══════════════════════════════════════════════════════════
def handle_request(req: dict) -> dict:
    """Process MCP JSON-RPC request."""
    method = req.get("method", "")
    req_id = req.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "nerv-break", "version": "5.6"},
                "capabilities": {"tools": {}},
            }
        }
    
    elif method == "tools/list":
        tools_list = []
        for name, info in TOOLS.items():
            tools_list.append({
                "name": name,
                "description": info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": {p: {"type": "string"} for p in info["params"]},
                    "required": info["params"],
                }
            })
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}
    
    elif method == "tools/call":
        p = req.get("params", {})
        tool_name = p.get("name", "")
        args = p.get("arguments", {})
        
        if tool_name not in TOOLS:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -1, "message": f"Unknown tool: {tool_name}"}}
        
        info = TOOLS[tool_name]
        try:
            # Build command
            clean_args = {}
            for key in info["params"]:
                clean_args[key] = str(args.get(key, "")).replace("'", "'\"'\"'")
            
            cmd = info["cmd"].format(**clean_args)
            
            # Execute via appropriate backend
            output = run_tool(cmd)
            output = output[:100000]  # Truncate huge output
            
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": output or "(no output)"}]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                }
            }
    
    elif method == "notifications/initialized":
        return None  # No response needed
    
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -1, "message": f"Unknown method: {method}"}}

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def stdio_loop():
    """MCP stdio transport — read JSON-RPC from stdin, write to stdout."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            resp = handle_request(req)
            if resp:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            break
        except Exception as e:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -1, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()

def http_loop(port):
    """MCP HTTP transport — for debugging."""
    import http.server
    
    class MCPHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            req = json.loads(body)
            resp = handle_request(req)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if resp:
                self.wfile.write(json.dumps(resp).encode())
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(b"MCP server running")
        def log_message(self, *args): pass
    
    print(f"[MCP] HTTP server on port {port}")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), MCPHandler).serve_forever()

if __name__ == "__main__":
    # Load tools from tools.json
    loaded_tools, loaded_config = load_tools()
    TOOLS.clear(); TOOLS.update(loaded_tools)
    TOOL_CONFIG.clear(); TOOL_CONFIG.update(loaded_config)
    
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, help="HTTP port for debug mode")
    ap.add_argument("--kali", metavar="SSH", help="Kali SSH address (user@host)")
    ap.add_argument("--wsl", action="store_true", help="Use WSL Kali Linux")
    ap.add_argument("--docker", metavar="CONTAINER", help="Use Docker container")
    ap.add_argument("--auto", action="store_true", help="Auto-detect best backend")
    args = ap.parse_args()
    
    if args.auto:
        backend = detect_backend()
        print(f"[MCP] Auto-detected backend: {backend}")
    elif args.wsl:
        BACKEND = "wsl"
        print(f"[MCP] WSL Kali: {WSL_DISTRO}")
    elif args.docker:
        BACKEND = "docker"
        DOCKER_CONTAINER = args.docker
        print(f"[MCP] Docker: {args.docker}")
    elif args.kali:
        BACKEND = "ssh"
        KALI_SSH = args.kali
        print(f"[MCP] Kali SSH: {KALI_SSH}")
    else:
        # Try auto-detect first, fall back to local
        backend = detect_backend()
        print(f"[MCP] Backend: {backend}")
    
    if args.port:
        http_loop(args.port)
    else:
        stdio_loop()
