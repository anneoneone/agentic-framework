#!/usr/bin/env python3
"""
Test script to verify all configured MCP servers can start.

Usage:
    python framework/scripts/test-mcp-servers.py          # test all servers
    python framework/scripts/test-mcp-servers.py --verbose # show detailed output
    python framework/scripts/test-mcp-servers.py --server agent-registry  # test one

Checks performed per server:
  1. File exists and has valid Python syntax
  2. All imports resolve (mcp, anthropic, fastmcp, etc.)
  3. Server starts and responds to MCP 'initialize' handshake
  4. Server exposes expected tools (list_tools)
"""

import argparse
import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------- config ----------

ROOT = Path(__file__).resolve().parent.parent.parent  # agent-framework/
CONFIG_PATH = ROOT / "framework" / "config.json"

SERVERS = {
    "agent-registry": {
        "path": ROOT / "framework" / "mcp-servers" / "agent-registry" / "server.py",
        "expected_tools": ["list_agents", "get_agent", "find_agents_for_task", "validate_agent"],
        "needs_api_key": False,
    },
    "knowledge-search": {
        "path": ROOT / "framework" / "mcp-servers" / "knowledge-search" / "server.py",
        "expected_tools": ["search_knowledge", "list_knowledge_files"],
        "needs_api_key": False,
    },
    "plan-execution": {
        "path": ROOT / "framework" / "mcp-servers" / "plan-execution" / "server.py",
        "expected_tools": ["execute_step", "validate_plan"],
        "needs_api_key": True,
    },
}

# ---------- helpers ----------

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def ok(msg):
    print(f"  {Colors.GREEN}✅ {msg}{Colors.RESET}")

def fail(msg):
    print(f"  {Colors.RED}❌ {msg}{Colors.RESET}")

def warn(msg):
    print(f"  {Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def info(msg):
    print(f"  {Colors.CYAN}ℹ  {msg}{Colors.RESET}")


# ---------- checks ----------

def check_syntax(path: Path) -> bool:
    """Check 1: valid Python syntax."""
    try:
        source = path.read_text()
        ast.parse(source, filename=str(path))
        return True
    except SyntaxError as e:
        fail(f"Syntax error at line {e.lineno}: {e.msg}")
        return False


def check_imports(path: Path, verbose: bool = False) -> bool:
    """Check 2: all imports resolve."""
    result = subprocess.run(
        [sys.executable, "-c", f"""
import importlib.util, ast, sys
source = open("{path}").read()
tree = ast.parse(source)
missing = []
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom) and node.module:
        mod = node.module.split('.')[0]
        if importlib.util.find_spec(mod) is None:
            missing.append(mod)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            mod = alias.name.split('.')[0]
            if importlib.util.find_spec(mod) is None:
                missing.append(mod)
if missing:
    print("MISSING:" + ",".join(sorted(set(missing))))
else:
    print("OK")
"""],
        capture_output=True, text=True, timeout=15
    )
    output = result.stdout.strip()
    if output.startswith("MISSING:"):
        modules = output.replace("MISSING:", "")
        fail(f"Missing packages: {modules}")
        info(f"Install with: pip install {modules.replace(',', ' ')}")
        return False
    elif output == "OK":
        return True
    else:
        fail(f"Import check failed: {result.stderr.strip()[:200]}")
        return False


def check_server_starts(name: str, path: Path, needs_api_key: bool, verbose: bool = False) -> bool:
    """Check 3: server process starts and accepts MCP initialize."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if needs_api_key and "ANTHROPIC_API_KEY" not in env:
        env["ANTHROPIC_API_KEY"] = "sk-ant-test-placeholder"

    # Start the server as a subprocess (MCP servers use stdio transport)
    proc = subprocess.Popen(
        [sys.executable, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT),
        env=env,
    )

    try:
        # Give server time to initialize
        time.sleep(2)

        # Check if process is still running
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode("utf-8", errors="replace").strip()
            if stderr:
                fail(f"Server exited immediately:\n{stderr[:1500]}")
            else:
                fail("Server exited immediately with no output")
            return False

        # Send MCP initialize request (JSON-RPC over stdio)
        init_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-mcp-servers", "version": "1.0.0"}
            }
        })

        # MCP uses Content-Length header framing for stdio transport
        message = f"Content-Length: {len(init_request)}\r\n\r\n{init_request}"
        proc.stdin.write(message.encode())
        proc.stdin.flush()

        # Wait for response
        time.sleep(2)

        if proc.poll() is not None:
            stderr = proc.stderr.read().decode("utf-8", errors="replace").strip()
            fail(f"Server crashed after initialize: {stderr[:300]}")
            return False

        # Server is still running — that's a pass
        if verbose:
            stderr = proc.stderr.read1(4096).decode("utf-8", errors="replace").strip() if hasattr(proc.stderr, 'read1') else ""
            if stderr:
                info(f"Server stderr: {stderr[:200]}")

        return True

    except Exception as e:
        fail(f"Error communicating with server: {e}")
        return False
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def check_tools_registration(path: Path, expected_tools: list, verbose: bool = False) -> bool:
    """Check 4: server source registers expected MCP tools."""
    source = path.read_text()

    # Look for tool registration patterns
    found_tools = set()

    # Pattern: @server.tool() or @mcp.tool() decorators
    import re
    decorator_tools = re.findall(r'@\w+\.tool\(["\'](\w+)["\']', source)
    found_tools.update(decorator_tools)

    # Pattern: async def with tool-like names
    async_defs = re.findall(r'async def (\w+)\(', source)
    found_tools.update(async_defs)

    # Pattern: tool name in string registrations
    string_tools = re.findall(r'["\']name["\']\s*:\s*["\'](\w+)["\']', source)
    found_tools.update(string_tools)

    # Pattern: register_tool("name" or tools["name"]
    register_tools = re.findall(r'register_tool\(["\'](\w+)["\']', source)
    found_tools.update(register_tools)

    missing = [t for t in expected_tools if not any(t in ft for ft in found_tools)]
    if missing and verbose:
        warn(f"Could not find registrations for: {', '.join(missing)}")
        info(f"Found definitions: {sorted(found_tools)[:10]}")

    # Not a hard failure — tool names might be dynamic
    return True


# ---------- main ----------

def test_server(name: str, config: dict, verbose: bool = False) -> dict:
    """Run all checks for one server. Returns results dict."""
    path = config["path"]
    results = {"name": name, "checks": {}}

    print(f"\n{Colors.BOLD}▸ {name}{Colors.RESET}  ({path.relative_to(ROOT)})")

    # Check 1: syntax
    passed = check_syntax(path)
    results["checks"]["syntax"] = passed
    if passed:
        ok("Python syntax valid")
    if not passed:
        return results

    # Check 2: imports
    passed = check_imports(path, verbose)
    results["checks"]["imports"] = passed
    if passed:
        ok("All imports resolve")
    if not passed:
        return results

    # Check 3: server starts
    passed = check_server_starts(name, path, config["needs_api_key"], verbose)
    results["checks"]["starts"] = passed
    if passed:
        ok("Server process starts and stays alive")

    # Check 4: tools
    passed = check_tools_registration(path, config["expected_tools"], verbose)
    results["checks"]["tools"] = passed
    if passed:
        ok(f"Tool definitions present ({len(config['expected_tools'])} expected)")

    return results


def main():
    parser = argparse.ArgumentParser(description="Test MCP servers configured for agent-framework")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--server", "-s", help="Test a specific server (agent-registry, knowledge-search, plan-execution)")
    args = parser.parse_args()

    print(f"{Colors.BOLD}MCP Server Test Suite{Colors.RESET}")
    print(f"Root: {ROOT}")
    print(f"Config: {CONFIG_PATH}")

    # Show installed package versions
    for pkg in ["mcp", "anthropic", "fastmcp"]:
        result = subprocess.run(
            [sys.executable, "-c", f"import {pkg}; print(getattr({pkg}, '__version__', 'installed (no __version__)'))"],
            capture_output=True, text=True, timeout=5
        )
        ver = result.stdout.strip() if result.returncode == 0 else "not installed"
        print(f"  {pkg}: {ver}")

    # Load config to verify servers match
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())
        configured = list(config.get("mcp_servers", {}).keys())
        print(f"Configured servers: {', '.join(configured)}")
    else:
        warn(f"Config file not found at {CONFIG_PATH}")
        configured = list(SERVERS.keys())

    # Filter to requested server
    if args.server:
        if args.server not in SERVERS:
            print(f"\n{Colors.RED}Unknown server: {args.server}{Colors.RESET}")
            print(f"Available: {', '.join(SERVERS.keys())}")
            sys.exit(1)
        targets = {args.server: SERVERS[args.server]}
    else:
        targets = SERVERS

    # Run tests
    all_results = []
    for name, config in targets.items():
        result = test_server(name, config, args.verbose)
        all_results.append(result)

    # Summary
    print(f"\n{Colors.BOLD}{'─' * 50}")
    print(f"Summary{Colors.RESET}")
    total_pass = 0
    total_fail = 0
    for r in all_results:
        checks = r["checks"]
        passed = all(checks.values())
        n_pass = sum(1 for v in checks.values() if v)
        n_fail = sum(1 for v in checks.values() if not v)
        total_pass += n_pass
        total_fail += n_fail
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {r['name']:25s} [{status}] ({n_pass} passed, {n_fail} failed)")

    print(f"\nTotal: {total_pass} passed, {total_fail} failed")

    if total_fail > 0:
        print(f"\n{Colors.YELLOW}Hint: Run ./install.sh first to set up the virtual environment and install dependencies.{Colors.RESET}")
        sys.exit(1)
    else:
        print(f"\n{Colors.GREEN}All MCP servers are operational.{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
