#!/usr/bin/env python3
"""Link Stack — Create and manage project/ symlinks for linked stacks.

A "linked stack" is one where the project source lives in an external repository.
The stack dir (stacks/STACKNAME/) contains only framework metadata (agents, plans,
docs/knowledge), and a gitignored `project/` symlink points to the external repo.

Configuration is stored in stacks/STACKNAME/.stack.json:
    {
        "stack": "my-project",
        "type": "linked",
        "repo_path": "/absolute/path/to/repo",
        "repo_url": "git@github.com:you/repo.git",   (optional)
        "created_at": "2026-03-09T00:00:00Z"
    }

Usage:
    python framework/scripts/link-stack.py --stack STACKNAME   # create/repair one
    python framework/scripts/link-stack.py --all               # all linked stacks
    python framework/scripts/link-stack.py --check             # status only (no changes)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()
STACKS_DIR = ROOT / "stacks"


def ok(msg: str):
    print(f"  \033[32m✓\033[0m  {msg}")


def warn(msg: str):
    print(f"  \033[33m⚠\033[0m  {msg}")


def fail(msg: str):
    print(f"  \033[31m✗\033[0m  {msg}")


def step(msg: str):
    print(f"\n\033[1m── {msg} ──\033[0m")


def load_stack_config(stack_dir: Path) -> dict | None:
    """Load .stack.json from a stack directory. Returns None if not present or invalid."""
    config_path = stack_dir / ".stack.json"
    if not config_path.exists():
        return None
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{stack_dir.name}/.stack.json: invalid JSON — {e}")
        return None


def _link_one(src: Path, dst: Path, label: str, stack_name: str, check_only: bool, force: bool = False) -> bool:
    """Generic helper: create or verify a single symlink dst → src.

    force=True allows replacing a real (non-symlink) file/dir, e.g. for .mcp.json
    that may have been created manually before linking was introduced.
    """
    if check_only:
        if dst.is_symlink() and dst.resolve() == src.resolve():
            ok(f"{stack_name}: {label} → framework")
            return True
        if not dst.exists():
            warn(f"{stack_name}: {label} missing — run link-stack.py --stack {stack_name}")
            return False
        warn(f"{stack_name}: {label} exists but is not a symlink to framework")
        return False

    dst.parent.mkdir(exist_ok=True)

    if dst.is_symlink():
        if dst.resolve() == src.resolve():
            ok(f"{stack_name}: {label} already linked → framework")
            return True
        dst.unlink()
    elif dst.exists():
        if force:
            dst.unlink() if dst.is_file() else None
            if dst.exists():
                fail(f"{stack_name}: {label} exists as a directory — won't overwrite")
                return False
        else:
            fail(f"{stack_name}: {label} exists as a real file/directory — won't overwrite")
            return False

    dst.symlink_to(src)
    ok(f"{stack_name}: {label} → framework")
    return True


def link_claude_dir(repo_path: Path, framework_root: Path, stack_name: str, stack_dir: Path, check_only: bool = False) -> bool:
    """Create or verify .claude/{commands,agents,settings.local.json} symlinks.

    Ensures slash commands, stack specialist agents, MCP permissions, and enabled
    servers are all available when the project repo is opened as the primary VSCode root.

    .claude/agents links to the stack's agents dir (not the framework meta-agents).
    """
    fw_claude = framework_root / ".claude"
    proj_claude = repo_path / ".claude"
    stack_agents = stack_dir / "agents"

    results = [
        _link_one(fw_claude / "commands", proj_claude / "commands", ".claude/commands", stack_name, check_only),
        _link_one(stack_agents, proj_claude / "agents", ".claude/agents", stack_name, check_only),
        _link_one(fw_claude / "settings.local.json", proj_claude / "settings.local.json", ".claude/settings.local.json", stack_name, check_only),
        _link_one(framework_root / ".mcp.json", repo_path / ".mcp.json", ".mcp.json", stack_name, check_only, force=True),
    ]
    return all(results)


def link_stack(stack_dir: Path, check_only: bool = False) -> bool:
    """Create or verify the project/ symlink for a linked stack.

    Also creates .claude/commands symlink in the project repo so that
    framework slash commands are available when the project is opened in VSCode.

    Returns True if OK (or would be OK in check mode), False on error.
    """
    config = load_stack_config(stack_dir)
    if config is None:
        return True  # Not a linked stack — skip silently

    if config.get("type") != "linked":
        return True  # Embedded stack — skip silently

    stack_name = stack_dir.name
    repo_path_str = config.get("repo_path", "").strip()
    if not repo_path_str:
        fail(f"{stack_name}: .stack.json missing 'repo_path'")
        return False

    repo_path = Path(repo_path_str)
    symlink = stack_dir / "project"

    # --- Check mode: report status only ---
    if check_only:
        if not repo_path.exists():
            warn(f"{stack_name}: repo_path '{repo_path}' not found on this machine")
            return False
        ok_project = False
        if symlink.is_symlink() and symlink.resolve() == repo_path.resolve():
            ok(f"{stack_name}: project/ → {repo_path}")
            ok_project = True
        elif symlink.is_symlink():
            warn(f"{stack_name}: project/ symlink exists but points to wrong path")
        else:
            warn(f"{stack_name}: project/ symlink missing — run link-stack.py --stack {stack_name}")
        ok_commands = link_claude_dir(repo_path, ROOT, stack_name, stack_dir, check_only=True)
        return ok_project and ok_commands

    # --- Link mode: create/repair symlink ---
    if not repo_path.exists():
        fail(f"{stack_name}: repo_path '{repo_path}' does not exist on this machine")
        hint = config.get("repo_url", "")
        if hint:
            print(f"       Clone it first: git clone {hint} {repo_path}")
        return False

    # Remove stale symlink
    if symlink.is_symlink():
        current_target = symlink.resolve()
        if current_target != repo_path.resolve():
            symlink.unlink()
        else:
            ok(f"{stack_name}: project/ already linked → {repo_path}")
            link_claude_dir(repo_path, ROOT, stack_name, stack_dir)
            return True

    # Remove accidental directory at the same path
    if symlink.exists():
        fail(f"{stack_name}: 'project' exists as a real directory — won't overwrite")
        return False

    symlink.symlink_to(repo_path)
    ok(f"{stack_name}: project/ → {repo_path}")
    link_claude_dir(repo_path, ROOT, stack_name, stack_dir)
    return True


def find_linked_stacks() -> list[Path]:
    """Return stack dirs that have a .stack.json with type: linked."""
    if not STACKS_DIR.exists():
        return []
    result = []
    for stack_dir in sorted(STACKS_DIR.iterdir()):
        if not stack_dir.is_dir():
            continue
        config = load_stack_config(stack_dir)
        if config and config.get("type") == "linked":
            result.append(stack_dir)
    return result


def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    check_only = "--check" in args
    do_all = "--all" in args

    if check_only:
        print("\033[1m")
        print("╔══════════════════════════════════════════╗")
        print("║     Link Stack — Status Check            ║")
        print("╚══════════════════════════════════════════╝")
        print("\033[0m")

        linked = find_linked_stacks()
        if not linked:
            print("  No linked stacks found.")
            sys.exit(0)

        errors = 0
        for stack_dir in linked:
            if not link_stack(stack_dir, check_only=True):
                errors += 1

        print()
        if errors == 0:
            print("\033[32m\033[1mAll linked stacks OK.\033[0m")
        else:
            print(f"\033[33m\033[1m{errors} issue(s) found.\033[0m")
        sys.exit(1 if errors > 0 else 0)

    if do_all:
        step("Linking all stacks")
        linked = find_linked_stacks()
        if not linked:
            print("  No linked stacks found.")
            sys.exit(0)
        errors = 0
        for stack_dir in linked:
            if not link_stack(stack_dir):
                errors += 1
        print()
        if errors == 0:
            print("\033[32m\033[1mDone.\033[0m")
        else:
            print(f"\033[33m\033[1m{errors} error(s).\033[0m")
        sys.exit(1 if errors > 0 else 0)

    # Single stack mode
    try:
        stack_idx = args.index("--stack")
        stack_name = args[stack_idx + 1]
    except (ValueError, IndexError):
        fail("Usage: link-stack.py --stack STACKNAME | --all | --check")
        sys.exit(1)

    stack_dir = STACKS_DIR / stack_name
    if not stack_dir.is_dir():
        fail(f"Stack directory not found: {stack_dir}")
        sys.exit(1)

    config = load_stack_config(stack_dir)
    if config is None:
        fail(f"{stack_name}: no .stack.json found")
        print("       Create one with: /create-stack --link /path/to/repo --name " + stack_name)
        sys.exit(1)

    if config.get("type") != "linked":
        warn(f"{stack_name}: .stack.json type is '{config.get('type')}', not 'linked' — nothing to do")
        sys.exit(0)

    success = link_stack(stack_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
