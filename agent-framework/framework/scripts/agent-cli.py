#!/usr/bin/env python3
"""Agent Framework CLI — invoke agents via the Claude API.

Usage:
    agent-cli task "description" [--stack STACK] [--interactive]
    agent-cli invoke AGENT "task description" [--stack STACK]
    agent-cli plan PLAN_FILE [--mode sequential|batch|dry-run]
    agent-cli list [--stack STACK]

Examples:
    # Auto-select best agent for a task
    python agent-cli.py task "Add WebSocket reconnection logic" --stack live-moafunk

    # Invoke a specific agent
    python agent-cli.py invoke axum-backend "Add health check endpoint"

    # Execute a plan
    python agent-cli.py plan plans/my-plan.json --mode batch

    # List available agents
    python agent-cli.py list --stack live-moafunk
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

# Add framework root to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_DIR = SCRIPT_DIR.parent
ROOT_DIR = FRAMEWORK_DIR.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(FRAMEWORK_DIR))

from config import load_config, Config

# Import AgentRegistry from agent-registry MCP server
REGISTRY_DIR = FRAMEWORK_DIR / "mcp-servers" / "agent-registry"
sys.path.insert(0, str(REGISTRY_DIR))


# ---------------------------------------------------------------------------
# Agent file helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from an agent.md file."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    metadata: dict = {}
    current_key: Optional[str] = None
    current_list: Optional[list] = None

    for line in frontmatter_text.split("\n"):
        line = line.rstrip()

        # List item
        if line.startswith("  - ") or line.startswith("    - "):
            value = line.strip().lstrip("- ").strip()
            if current_list is not None:
                current_list.append(value)
            continue

        # Key-value
        match = re.match(r'^([\w-]+):\s*(.*)', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()

            # Inline list [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
                metadata[key] = [i for i in items if i]
                current_key = key
                current_list = None
                continue

            if value:
                metadata[key] = value.strip('"').strip("'")
                current_key = key
                current_list = None
            else:
                # Start of a list or nested mapping
                metadata[key] = []
                current_key = key
                current_list = metadata[key]

    return metadata, body


def find_agent_file(agent_name: str, config: Config, stack: Optional[str] = None) -> Optional[Path]:
    """Find an agent .agent.md file by name.

    Search order:
    1. stacks/<stack>/agents/ (if stack specified)
    2. framework/core/common-agents/
    3. framework/core/shared-agents/
    4. framework/core/meta-agents/
    5. All stacks (glob)
    """
    name = agent_name.lstrip("@").replace(".agent.md", "")
    filename = f"{name}.agent.md"

    candidates = []

    if stack:
        candidates.append(config.root_path / "stacks" / stack / "agents" / filename)

    candidates.extend([
        config.root_path / "framework" / "core" / "common-agents" / filename,
        config.root_path / "framework" / "core" / "shared-agents" / filename,
        config.root_path / "framework" / "core" / "meta-agents" / filename,
    ])

    for c in candidates:
        try:
            if c.exists():
                return c.resolve()
        except OSError:
            continue

    # Fallback: glob all stacks
    for match in config.root_path.glob(f"stacks/*/agents/{filename}"):
        return match.resolve()

    return None


def load_agent_prompt(agent_path: Path) -> tuple[str, dict]:
    """Load an agent file and return (system_prompt, metadata)."""
    content = agent_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)

    # Build system prompt: include both frontmatter context and body
    parts = []

    if metadata.get("name"):
        parts.append(f"You are the {metadata['name']} agent.")
    if metadata.get("description"):
        parts.append(metadata["description"])

    if metadata.get("scope"):
        scope = metadata["scope"]
        if isinstance(scope, list):
            parts.append("Your scope: " + ", ".join(scope))

    if body:
        parts.append("")
        parts.append(body)

    system_prompt = "\n".join(parts)
    return system_prompt, metadata


# ---------------------------------------------------------------------------
# Agent Registry integration
# ---------------------------------------------------------------------------

def get_registry(config: Config):
    """Import and instantiate the AgentRegistry."""
    try:
        from server import AgentRegistry
        return AgentRegistry(config.root_path)
    except ImportError:
        print("Warning: Could not import AgentRegistry. Agent discovery limited.", file=sys.stderr)
        return None


def find_agents_for_task(task: str, config: Config, stack: Optional[str] = None) -> list[dict]:
    """Find best agents for a task using the registry."""
    registry = get_registry(config)
    if registry is None:
        return []

    try:
        results = registry.find_agents_for_task(task, stack=stack)
        return results
    except Exception as e:
        print(f"Warning: Agent search failed: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Claude API execution
# ---------------------------------------------------------------------------

def call_claude(system_prompt: str, user_message: str, config: Config, stream: bool = True) -> str:
    """Call the Claude Messages API with an agent system prompt.

    Args:
        system_prompt: Agent's system prompt (from .agent.md)
        user_message: The task/question to execute
        config: Framework config with API key and model
        stream: Whether to stream the response

    Returns:
        Full response text
    """
    try:
        import anthropic
    except ImportError:
        print("Error: 'anthropic' package not installed. Run: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=config.api_key)

    if stream:
        response_text = ""
        with client.messages.stream(
            model=config.model,
            max_tokens=config.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream_obj:
            for text in stream_obj.text_stream:
                print(text, end="", flush=True)
                response_text += text
        print()  # Final newline
        return response_text
    else:
        response = client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text
        print(text)
        return text


def call_claude_batch(tasks: list[dict], config: Config) -> list[dict]:
    """Execute multiple agent tasks via the Batch API.

    Args:
        tasks: List of dicts with keys: agent_name, task, system_prompt, step_id
        config: Framework config

    Returns:
        List of result dicts with keys: step_id, agent_name, response, status
    """
    try:
        import anthropic
    except ImportError:
        print("Error: 'anthropic' package not installed.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=config.api_key)

    # Build batch requests
    requests = []
    for i, task in enumerate(tasks):
        requests.append({
            "custom_id": task.get("step_id", f"task-{i}"),
            "params": {
                "model": config.model,
                "max_tokens": config.max_tokens,
                "system": task["system_prompt"],
                "messages": [{"role": "user", "content": task["task"]}],
            }
        })

    print(f"Submitting batch with {len(requests)} requests...")
    batch = client.messages.batches.create(requests=requests)
    batch_id = batch.id
    print(f"Batch ID: {batch_id}")

    # Poll for completion
    timeout = config.batch.timeout_minutes * 60
    interval = config.batch.poll_interval_seconds
    elapsed = 0

    while elapsed < timeout:
        status = client.messages.batches.retrieve(batch_id)
        print(f"  Status: {status.processing_status} ({elapsed}s elapsed)", end="\r")

        if status.processing_status == "ended":
            print(f"\nBatch completed in {elapsed}s")
            break

        time.sleep(interval)
        elapsed += interval
    else:
        print(f"\nBatch timed out after {timeout}s")
        return []

    # Collect results
    results = []
    for result in client.messages.batches.results(batch_id):
        step_id = result.custom_id
        if result.result.type == "succeeded":
            response_text = result.result.message.content[0].text
            results.append({
                "step_id": step_id,
                "response": response_text,
                "status": "completed",
                "tokens_used": result.result.message.usage.output_tokens,
            })
        else:
            results.append({
                "step_id": step_id,
                "response": f"Error: {result.result.type}",
                "status": "failed",
                "tokens_used": 0,
            })

    return results


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_task(args, config: Config):
    """Execute a task with auto-selected agent."""
    task_description = args.task
    stack = args.stack

    print(f"Finding best agent for: \"{task_description}\"")
    if stack:
        print(f"  Stack: {stack}")

    # Find matching agents
    candidates = find_agents_for_task(task_description, config, stack)

    if not candidates:
        print("No matching agents found. Try specifying a stack with --stack.")
        sys.exit(1)

    # Display candidates
    print(f"\nTop agent candidates:")
    for i, candidate in enumerate(candidates[:5]):
        agent = candidate["agent"] if isinstance(candidate, dict) else candidate[0]
        score = candidate["score"] if isinstance(candidate, dict) else candidate[1]
        name = agent.get("name", agent.name) if isinstance(agent, dict) else agent.name
        desc = agent.get("description", "") if isinstance(agent, dict) else agent.description
        quality = candidate.get("match_quality", "") if isinstance(candidate, dict) else ""
        print(f"  {i+1}. {name} (score: {score}{', ' + quality if quality else ''})")
        print(f"     {desc[:80]}")

    # Select agent
    if args.interactive and len(candidates) > 1:
        choice = input(f"\nSelect agent [1-{min(5, len(candidates))}] (default: 1): ").strip()
        idx = (int(choice) - 1) if choice.isdigit() and 1 <= int(choice) <= len(candidates) else 0
    else:
        idx = 0
        best = candidates[0]
        agent = best["agent"] if isinstance(best, dict) else best[0]
        name = agent.get("name", agent.name) if isinstance(agent, dict) else agent.name
        print(f"\nAuto-selected: {name}")

    selected = candidates[idx]
    agent = selected["agent"] if isinstance(selected, dict) else selected[0]
    agent_name = agent.get("name", agent.name) if isinstance(agent, dict) else agent.name

    # Load agent and execute
    agent_path = find_agent_file(agent_name, config, stack)
    if not agent_path:
        print(f"Error: Could not find agent file for '{agent_name}'")
        sys.exit(1)

    system_prompt, metadata = load_agent_prompt(agent_path)
    print(f"\n{'='*60}")
    print(f"Agent: {agent_name} | Model: {config.model}")
    print(f"{'='*60}\n")

    call_claude(system_prompt, task_description, config)


def cmd_invoke(args, config: Config):
    """Invoke a specific agent directly."""
    agent_name = args.agent.lstrip("@")
    task = args.task

    agent_path = find_agent_file(agent_name, config, args.stack)
    if not agent_path:
        print(f"Error: Agent '{agent_name}' not found.")
        print(f"  Searched in: stacks/*/agents/, framework/core/*/")
        sys.exit(1)

    system_prompt, metadata = load_agent_prompt(agent_path)

    print(f"Agent: {agent_name} ({agent_path.relative_to(config.root_path)})")
    print(f"Model: {config.model}")
    print(f"{'='*60}\n")

    call_claude(system_prompt, task, config)


def cmd_plan(args, config: Config):
    """Execute a plan file."""
    import subprocess

    plan_path = Path(args.plan_file)
    if not plan_path.exists():
        print(f"Error: Plan file not found: {plan_path}")
        sys.exit(1)

    executor = SCRIPT_DIR / "plan-executor.py"
    if not executor.exists():
        print(f"Error: plan-executor.py not found at {executor}")
        sys.exit(1)

    cmd = [sys.executable, str(executor), str(plan_path)]
    if args.mode:
        cmd.extend(["--mode", args.mode])
    if args.auto_approve:
        cmd.append("--auto-approve")
    if args.resume:
        cmd.append("--resume")
    if args.verbose:
        cmd.append("--verbose")

    print(f"Executing plan: {plan_path}")
    print(f"Mode: {args.mode or 'sequential'}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, env={**dict(os.environ), "ANTHROPIC_API_KEY": config.api_key, "ANTHROPIC_MODEL": config.model})
    sys.exit(result.returncode)


def cmd_list(args, config: Config):
    """List available agents."""
    registry = get_registry(config)
    if registry is None:
        # Fallback: manual scan
        print("Scanning for agents...")
        for agent_dir_name in config.agent_dirs:
            for stack_dir in (config.root_path / "stacks").iterdir():
                agent_dir = stack_dir / agent_dir_name
                if agent_dir.is_dir():
                    for f in sorted(agent_dir.glob("*.agent.md")):
                        name = f.stem.replace(".agent", "")
                        print(f"  {name:30s} ({f.relative_to(config.root_path)})")
        return

    agents = registry.list_agents(stack=args.stack)

    if not agents:
        print("No agents found.")
        return

    # Group by stack
    by_stack: dict[str, list] = {}
    for agent in agents:
        stack = getattr(agent, "stack", None) or "framework"
        by_stack.setdefault(stack, []).append(agent)

    for stack_name, stack_agents in sorted(by_stack.items()):
        print(f"\n{stack_name}:")
        for agent in sorted(stack_agents, key=lambda a: a.name):
            desc = agent.description[:60] if agent.description else ""
            print(f"  {agent.name:30s} {desc}")

    print(f"\nTotal: {len(agents)} agents")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import os

    parser = argparse.ArgumentParser(
        prog="agent-cli",
        description="Agent Framework CLI — invoke agents via the Claude API",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # task
    task_parser = subparsers.add_parser("task", help="Auto-select agent and execute a task")
    task_parser.add_argument("task", help="Task description")
    task_parser.add_argument("--stack", "-s", help="Limit to a specific stack")
    task_parser.add_argument("--interactive", "-i", action="store_true", help="Choose agent interactively")

    # invoke
    invoke_parser = subparsers.add_parser("invoke", help="Invoke a specific agent")
    invoke_parser.add_argument("agent", help="Agent name (e.g. axum-backend)")
    invoke_parser.add_argument("task", help="Task description")
    invoke_parser.add_argument("--stack", "-s", help="Stack to search in")

    # plan
    plan_parser = subparsers.add_parser("plan", help="Execute a plan file")
    plan_parser.add_argument("plan_file", help="Path to plan JSON file")
    plan_parser.add_argument("--mode", "-m", choices=["sequential", "batch", "dry-run"], default="sequential")
    plan_parser.add_argument("--auto-approve", action="store_true", help="Skip approval prompts")
    plan_parser.add_argument("--resume", action="store_true", help="Resume from last completed step")
    plan_parser.add_argument("--verbose", "-v", action="store_true")

    # list
    list_parser = subparsers.add_parser("list", help="List available agents")
    list_parser.add_argument("--stack", "-s", help="Filter by stack")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Load config
    config = load_config()
    errors = config.validate()

    # list doesn't need API key
    if args.command != "list" and errors:
        print("Configuration errors:")
        for e in errors:
            print(f"  - {e}")
        print("\nSet ANTHROPIC_API_KEY or add it to framework/config.json")
        sys.exit(1)

    # Dispatch
    commands = {
        "task": cmd_task,
        "invoke": cmd_invoke,
        "plan": cmd_plan,
        "list": cmd_list,
    }

    commands[args.command](args, config)


if __name__ == "__main__":
    main()
