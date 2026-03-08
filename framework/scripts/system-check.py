#!/usr/bin/env python3
"""System check for Agent Framework.

Validates that all required services, dependencies, and configuration are working.

Usage:
    python framework/scripts/system-check.py
    python framework/scripts/system-check.py --verbose
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()

VERBOSE = "--verbose" in sys.argv


def ok(msg: str):
    print(f"  \033[32m✓\033[0m  {msg}")


def warn(msg: str):
    print(f"  \033[33m⚠\033[0m  {msg}")


def fail(msg: str):
    print(f"  \033[31m✗\033[0m  {msg}")


def step(msg: str):
    print(f"\n\033[1m── {msg} ──\033[0m")


def check_command(name: str, args: list[str] = None) -> bool:
    """Check if a command is available."""
    if shutil.which(name):
        if VERBOSE and args:
            try:
                result = subprocess.run(
                    [name] + args,
                    capture_output=True, text=True, timeout=5
                )
                version = result.stdout.strip().split("\n")[0]
                ok(f"{name}: {version}")
            except Exception:
                ok(f"{name}: found")
        else:
            ok(f"{name}: found")
        return True
    else:
        fail(f"{name}: not found")
        return False


def check_python_package(name: str) -> bool:
    """Check if a Python package is importable."""
    try:
        __import__(name)
        ok(f"python: {name}")
        return True
    except ImportError:
        fail(f"python: {name} not installed")
        return False


def check_directory_structure() -> int:
    """Check required directories exist."""
    errors = 0

    required_dirs = [
        "framework/core/common-agents",
        ".claude/agents",
        "framework/core/guidelines",
        "framework/mcp-servers",
        "framework/schemas",
        "framework/templates",
        "framework/scripts",
        "stacks",
    ]

    for d in required_dirs:
        path = ROOT / d
        if path.exists():
            ok(d)
        else:
            fail(f"{d}: missing")
            errors += 1

    return errors


def check_mcp_config() -> int:
    """Check .mcp.json configuration."""
    errors = 0
    mcp_path = ROOT / ".mcp.json"

    if not mcp_path.exists():
        fail(".mcp.json: not found")
        return 1

    try:
        with open(mcp_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        fail(f".mcp.json: invalid JSON - {e}")
        return 1

    servers = config.get("mcpServers", {})
    ok(f".mcp.json: {len(servers)} servers configured")

    for name, server_config in servers.items():
        cmd = server_config.get("command", "")
        args = server_config.get("args", [])

        # Check command exists
        if not shutil.which(cmd) and not Path(cmd).exists():
            warn(f"  {name}: command '{cmd}' not found")
            errors += 1
            continue

        # For custom Python servers, check the script exists
        if args and args[0].endswith(".py"):
            script_path = Path(args[0])
            if script_path.exists():
                ok(f"  {name}: script exists")
            else:
                fail(f"  {name}: script not found at {args[0]}")
                errors += 1
        else:
            ok(f"  {name}: {cmd}")

    return errors


def check_neo4j() -> bool:
    """Check if Neo4j is accessible."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5
        )
        containers = result.stdout.strip().split("\n")
        neo4j_running = any("neo4j" in c.lower() for c in containers if c)

        if neo4j_running:
            ok("Neo4j: running (Docker)")
            return True
        else:
            warn("Neo4j: not running (memento-knowledge will fail)")
            return False
    except Exception:
        warn("Neo4j: cannot check (Docker not available)")
        return False


def check_api_keys() -> int:
    """Check required API keys."""
    errors = 0

    if os.environ.get("ANTHROPIC_API_KEY"):
        masked = "***" + os.environ["ANTHROPIC_API_KEY"][-4:]
        ok(f"ANTHROPIC_API_KEY: set ({masked})")
    else:
        warn("ANTHROPIC_API_KEY: not set")
        errors += 1

    return errors


def check_agent_files() -> int:
    """Count and validate agent files."""
    agent_files = []

    # Framework agents
    for subdir in ["common-agents", "shared-agents"]:
        agent_dir = ROOT / "framework" / "core" / subdir
        if agent_dir.exists():
            agent_files.extend(agent_dir.glob("*.agent.md"))

    # Claude Code agents
    claude_dir = ROOT / ".claude" / "agents"
    if claude_dir.exists():
        agent_files.extend(claude_dir.glob("*.agent.md"))

    # Stack agents
    stacks_dir = ROOT / "stacks"
    if stacks_dir.exists():
        for stack_dir in stacks_dir.iterdir():
            if stack_dir.is_dir():
                agents_dir = stack_dir / "agents"
                if agents_dir.exists():
                    agent_files.extend(agents_dir.glob("*.agent.md"))

    if agent_files:
        ok(f"Agent files: {len(agent_files)} found")
        if VERBOSE:
            for f in sorted(agent_files):
                rel = f.relative_to(ROOT) if f.is_relative_to(ROOT) else f
                print(f"       {rel}")
    else:
        warn("No agent files found")

    return 0


def check_slash_commands() -> int:
    """Check slash commands exist."""
    commands_dir = ROOT / ".claude" / "commands"
    if not commands_dir.exists():
        fail(".claude/commands/: missing")
        return 1

    expected = [
        "task", "create-stack", "plan", "execute-plan", "show-plan",
        "finalize", "validate-agents", "update-agents",
        "knowledge-sync", "token-telemetry", "system-check",
    ]

    errors = 0
    for cmd in expected:
        path = commands_dir / f"{cmd}.md"
        if path.exists():
            ok(f"/{cmd}")
        else:
            warn(f"/{cmd}: missing ({path.name})")
            errors += 1

    return errors


def check_scripts() -> int:
    """Check framework scripts exist."""
    expected = [
        "task-executor.py", "plan-executor.py", "knowledge-sync.py",
        "validate-agent.py", "update-agents.py", "token-telemetry.py",
        "system-check.py",
    ]

    errors = 0
    scripts_dir = ROOT / "framework" / "scripts"
    for script in expected:
        path = scripts_dir / script
        if path.exists():
            ok(f"scripts/{script}")
        else:
            warn(f"scripts/{script}: missing")
            errors += 1

    return errors


def main():
    print("\033[1m")
    print("╔══════════════════════════════════════════╗")
    print("║     Agent Framework — System Check       ║")
    print("╚══════════════════════════════════════════╝")
    print("\033[0m")

    total_errors = 0

    step("1/8  System Dependencies")
    check_command("python3", ["--version"])
    check_command("npx", ["--version"])
    check_command("docker", ["--version"])
    check_command("git", ["--version"])

    step("2/8  Python Packages")
    check_python_package("anthropic")
    check_python_package("fastmcp")

    step("3/8  Directory Structure")
    total_errors += check_directory_structure()

    step("4/8  MCP Server Configuration")
    total_errors += check_mcp_config()

    step("5/8  Services")
    check_neo4j()
    total_errors += check_api_keys()

    step("6/8  Agent Files")
    total_errors += check_agent_files()

    step("7/8  Slash Commands")
    total_errors += check_slash_commands()

    step("8/8  Framework Scripts")
    total_errors += check_scripts()

    print()
    if total_errors == 0:
        print("\033[32m\033[1mAll checks passed.\033[0m")
    else:
        print(f"\033[33m\033[1m{total_errors} issue(s) found.\033[0m")

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
