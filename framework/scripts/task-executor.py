#!/usr/bin/env python3
"""Task Executor — Enforced pre/post knowledge hooks for single tasks.

Wraps the Anthropic Messages API to ensure every task gets:
  Phase 1: Pre-task knowledge fetch (search graph, load agent context)
  Phase 2: Execute with specialist agent (system prompt from .agent.md)
  Phase 3: Post-task knowledge capture (extract decisions/learnings, save to graph)

Usage:
    python framework/scripts/task-executor.py --stack STACK --task "TASK DESCRIPTION" [OPTIONS]
    python framework/scripts/task-executor.py --stack STACK --agent @agent-name --task "TASK" [OPTIONS]

Options:
    --stack STACK       Stack name (required)
    --task TASK         Task description (required)
    --agent AGENT       Force a specific agent (skip agent discovery)
    --model MODEL       Override model (default: claude-sonnet-4-5-20250929)
    --max-tokens N      Max response tokens (default: 4096)
    --dry-run           Show what would happen without executing
    --skip-knowledge    Skip knowledge fetch/capture (for testing)
    --verbose           Show detailed output
    --context FILE      Additional context file(s) to include (repeatable)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT / "framework" / "mcp-servers" / "memento-knowledge"))
sys.path.insert(0, str(ROOT / "framework" / "mcp-servers" / "agent-registry"))


# ──────────────────────────────────────────────────────────────────────
# Agent Discovery
# ──────────────────────────────────────────────────────────────────────

def find_agent_file(agent_name: str) -> Optional[Path]:
    """Find agent .agent.md file by name."""
    name = agent_name.lstrip("@")
    search_dirs = [
        ROOT / "stacks",
        ROOT / "framework" / "core" / "common-agents",
        ROOT / "framework" / "core" / "shared-agents",
        ROOT / ".claude" / "agents",
    ]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for match in search_dir.rglob(f"{name}.agent.md"):
            return match
    return None


def get_agent_system_prompt(agent_path: Path) -> str:
    """Extract the body (after frontmatter) from an agent file."""
    content = agent_path.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].strip()
    return content.strip()


def discover_agent(task: str, stack: str) -> Optional[str]:
    """Use agent-registry to find the best agent for a task.

    Falls back to keyword matching if the registry module isn't available.
    """
    try:
        from server import AgentRegistry
        registry = AgentRegistry(str(ROOT))
        results = registry.find_agents_for_task(task, stack)
        if results:
            best_agent, score = results[0]
            if score > 0:
                return best_agent.name
    except Exception:
        pass

    # Fallback: scan agent files and do simple keyword matching
    agents_dir = ROOT / "stacks" / stack / "agents"
    if not agents_dir.exists():
        return None

    task_words = set(w.lower() for w in re.findall(r"\w+", task) if len(w) > 3)
    best_match = None
    best_score = 0

    for agent_file in agents_dir.glob("*.agent.md"):
        if agent_file.is_symlink():
            # Common agents — lower priority for stack tasks
            continue
        name = agent_file.stem.replace(".agent", "")
        content = agent_file.read_text(encoding="utf-8")[:500].lower()
        score = sum(1 for w in task_words if w in content or w in name)
        if score > best_score:
            best_score = score
            best_match = name

    return best_match


# ──────────────────────────────────────────────────────────────────────
# Phase 1: Pre-task Knowledge Fetch
# ──────────────────────────────────────────────────────────────────────

def fetch_knowledge(task: str, stack: str, agent_name: str, verbose: bool = False) -> dict:
    """Query the knowledge graph for context relevant to this task.

    Returns a dict with 'decisions', 'learnings', 'agent_context', 'constraints'.
    """
    result = {
        "decisions": [],
        "learnings": [],
        "agent_context": {},
        "constraints": [],
        "available": False,
    }

    try:
        from graph import GraphManager

        graph = GraphManager(
            uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )
        result["available"] = True

        # Search for task-relevant knowledge
        search_results = graph.search_fulltext(task, stack, limit=10)
        for item in search_results:
            labels = item.get("labels", [])
            content = item.get("properties", {}).get("content", "")
            if "Decision" in labels:
                result["decisions"].append(content)
                result["constraints"].append(content)
            elif "Learning" in labels:
                result["learnings"].append(content)

        # Get agent-specific context
        if agent_name:
            agent_ctx = graph.get_agent_context(f"@{agent_name}", stack)
            result["agent_context"] = agent_ctx

        graph.close()

        if verbose:
            print(f"  Knowledge: {len(result['decisions'])} decisions, "
                  f"{len(result['learnings'])} learnings, "
                  f"{len(result['constraints'])} constraints")

    except Exception as e:
        if verbose:
            print(f"  Knowledge graph unavailable: {e}")

    return result


# ──────────────────────────────────────────────────────────────────────
# Phase 2: Execute Task
# ──────────────────────────────────────────────────────────────────────

def build_user_message(task: str, knowledge: dict, context_files: list[str] = None) -> str:
    """Build the user message with task + knowledge context + file context."""
    parts = []

    # Knowledge context
    if knowledge.get("constraints"):
        parts.append("## Relevant Decisions (do not contradict these)")
        for i, d in enumerate(knowledge["constraints"][:5], 1):
            parts.append(f"{i}. {d}")
        parts.append("")

    if knowledge.get("learnings"):
        parts.append("## Relevant Learnings")
        for i, l in enumerate(knowledge["learnings"][:5], 1):
            parts.append(f"{i}. {l}")
        parts.append("")

    # Additional context files
    if context_files:
        parts.append("## Additional Context")
        for filepath in context_files:
            path = Path(filepath)
            if path.exists():
                content = path.read_text(encoding="utf-8")[:3000]
                parts.append(f"### {path.name}")
                parts.append(f"```\n{content}\n```")
                parts.append("")

    # Task
    parts.append("## Task")
    parts.append(task)

    return "\n".join(parts)


def execute_task(
    task: str,
    system_prompt: str,
    model: str,
    max_tokens: int,
    knowledge: dict,
    context_files: list[str] = None,
) -> dict:
    """Execute the task via Anthropic Messages API."""
    try:
        import anthropic
    except ImportError:
        return {
            "status": "error",
            "response": "anthropic package not installed",
            "tokens_used": 0,
            "duration_seconds": 0,
        }

    start = time.time()
    user_message = build_user_message(task, knowledge, context_files)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        text = ""
        if response.content:
            text = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])

        tokens = response.usage.input_tokens + response.usage.output_tokens
        duration = time.time() - start

        return {
            "status": "completed",
            "response": text,
            "tokens_used": tokens,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "duration_seconds": round(duration, 1),
        }

    except Exception as e:
        return {
            "status": "error",
            "response": str(e),
            "tokens_used": 0,
            "duration_seconds": round(time.time() - start, 1),
        }


# ──────────────────────────────────────────────────────────────────────
# Phase 3: Post-task Knowledge Capture
# ──────────────────────────────────────────────────────────────────────

# Patterns that indicate a decision or learning in the response
DECISION_PATTERNS = [
    r"(?:I |We )(?:decided|chose|selected|opted) (?:to |for )(.+?)(?:\.|$)",
    r"(?:Decision|Approach): (.+?)(?:\.|$)",
    r"(?:Using|Went with|Going with) (.+?) (?:because|since|as)(.+?)(?:\.|$)",
]

LEARNING_PATTERNS = [
    r"(?:I |We )(?:discovered|found|learned|noticed) (?:that )?(.+?)(?:\.|$)",
    r"(?:Learning|Insight|Note): (.+?)(?:\.|$)",
    r"(?:Turns out|It appears|Interestingly),? (.+?)(?:\.|$)",
]


def extract_knowledge_from_response(response_text: str) -> dict:
    """Extract decisions and learnings from the specialist's response.

    Uses regex patterns to find decision/learning language.
    Returns dict with 'decisions' and 'learnings' lists.
    """
    decisions = []
    learnings = []

    for pattern in DECISION_PATTERNS:
        for match in re.finditer(pattern, response_text, re.IGNORECASE | re.MULTILINE):
            text = match.group(0).strip()
            if len(text) > 20 and text not in decisions:
                decisions.append(text[:300])

    for pattern in LEARNING_PATTERNS:
        for match in re.finditer(pattern, response_text, re.IGNORECASE | re.MULTILINE):
            text = match.group(0).strip()
            if len(text) > 20 and text not in learnings:
                learnings.append(text[:300])

    return {"decisions": decisions[:5], "learnings": learnings[:5]}


def save_knowledge(
    extracted: dict,
    stack: str,
    agent_name: str,
    task: str,
    verbose: bool = False,
) -> dict:
    """Save extracted knowledge to the graph and JSONL.

    Returns stats dict.
    """
    stats = {"decisions_saved": 0, "learnings_saved": 0, "graph": False, "jsonl": False}

    # Always write to JSONL (works offline)
    knowledge_dir = ROOT / "stacks" / stack / "docs" / "knowledge"
    if knowledge_dir.exists() or (ROOT / "stacks" / stack).exists():
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        jsonl_path = knowledge_dir / f"tasks-{date_str}.jsonl"

        with open(jsonl_path, "a", encoding="utf-8") as f:
            for d in extracted["decisions"]:
                entry = {
                    "type": "decision",
                    "content": d,
                    "agent": agent_name or "",
                    "source": "task-executor",
                    "task": task[:200],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                f.write(json.dumps(entry, default=str) + "\n")
                stats["decisions_saved"] += 1

            for l in extracted["learnings"]:
                entry = {
                    "type": "learning",
                    "content": l,
                    "agent": agent_name or "",
                    "source": "task-executor",
                    "task": task[:200],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                f.write(json.dumps(entry, default=str) + "\n")
                stats["learnings_saved"] += 1

        stats["jsonl"] = True
        if verbose:
            print(f"  JSONL: {jsonl_path}")

    # Try to save to Neo4j
    try:
        from graph import GraphManager

        graph = GraphManager(
            uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )

        for d in extracted["decisions"]:
            graph._ensure_stack(stack)
            node = graph.create_node("Decision", {
                "content": d,
                "stack": stack,
                "agent": agent_name or "",
                "source": "task-executor",
            })
            if node:
                graph.create_relationship(node["id"], f"stack_{stack}", "BELONGS_TO")
                if agent_name:
                    graph._ensure_agent(agent_name, stack)
                    graph.create_relationship(
                        node["id"], f"agent_{stack}_{agent_name.lstrip('@')}", "MADE_BY"
                    )

        for l in extracted["learnings"]:
            graph._ensure_stack(stack)
            node = graph.create_node("Learning", {
                "content": l,
                "stack": stack,
                "agent": agent_name or "",
                "source": "task-executor",
            })
            if node:
                graph.create_relationship(node["id"], f"stack_{stack}", "BELONGS_TO")
                if agent_name:
                    graph._ensure_agent(agent_name, stack)
                    graph.create_relationship(
                        node["id"], f"agent_{stack}_{agent_name.lstrip('@')}", "MADE_BY"
                    )

        graph.close()
        stats["graph"] = True

    except Exception as e:
        if verbose:
            print(f"  Neo4j save skipped: {e}")

    return stats


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    if "--help" in sys.argv or "-h" in sys.argv or len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    args = sys.argv[1:]

    # Parse arguments
    def get_arg(flag: str) -> Optional[str]:
        if flag in args:
            idx = args.index(flag)
            if idx + 1 < len(args):
                return args[idx + 1]
        return None

    stack = get_arg("--stack")
    task = get_arg("--task")
    agent_override = get_arg("--agent")
    model = get_arg("--model") or "claude-sonnet-4-5-20250929"
    max_tokens = int(get_arg("--max-tokens") or "4096")
    dry_run = "--dry-run" in args
    skip_knowledge = "--skip-knowledge" in args
    verbose = "--verbose" in args

    # Collect context files
    context_files = []
    for i, arg in enumerate(args):
        if arg == "--context" and i + 1 < len(args):
            context_files.append(args[i + 1])

    if not stack:
        print("Error: --stack is required")
        sys.exit(1)
    if not task:
        print("Error: --task is required")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Task Executor")
    print(f"{'='*60}")
    print(f"Stack: {stack}")
    print(f"Task:  {task[:80]}{'...' if len(task) > 80 else ''}")

    # ── Phase 1: Agent Discovery ──────────────────────────────────
    print(f"\n── Phase 1: Pre-task ──")

    agent_name = agent_override
    if agent_name:
        agent_name = agent_name.lstrip("@")
        print(f"  Agent: @{agent_name} (specified)")
    else:
        print(f"  Discovering best agent...")
        agent_name = discover_agent(task, stack)
        if agent_name:
            print(f"  Agent: @{agent_name} (auto-discovered)")
        else:
            print(f"  No specialist found — using coordinator as fallback")
            agent_name = "coordinator"

    agent_path = find_agent_file(agent_name)
    if agent_path:
        print(f"  Agent file: {agent_path.relative_to(ROOT)}")
        system_prompt = get_agent_system_prompt(agent_path)
    else:
        print(f"  Warning: No .agent.md found for @{agent_name}")
        system_prompt = f"You are the {agent_name} specialist."

    # ── Phase 1: Knowledge Fetch ──────────────────────────────────
    knowledge = {"decisions": [], "learnings": [], "constraints": [], "available": False}

    if not skip_knowledge:
        print(f"  Fetching knowledge...")
        knowledge = fetch_knowledge(task, stack, agent_name, verbose)
        if knowledge["available"]:
            print(f"  Knowledge: {len(knowledge['decisions'])} decisions, "
                  f"{len(knowledge['learnings'])} learnings")
        else:
            print(f"  Knowledge graph unavailable — proceeding without context")
    else:
        print(f"  Knowledge fetch skipped (--skip-knowledge)")

    if dry_run:
        print(f"\n── Dry run — would execute with @{agent_name} ──")
        print(f"  Model: {model}")
        print(f"  Max tokens: {max_tokens}")
        print(f"  Context files: {len(context_files)}")
        print(f"  Constraints: {len(knowledge.get('constraints', []))}")
        sys.exit(0)

    # ── Phase 2: Execute ──────────────────────────────────────────
    print(f"\n── Phase 2: Execute (@{agent_name}) ──")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    print(f"  Model: {model}")
    result = execute_task(task, system_prompt, model, max_tokens, knowledge, context_files)

    if result["status"] == "completed":
        print(f"  Status: completed ({result['tokens_used']} tokens, {result['duration_seconds']}s)")
        if verbose:
            print(f"\n  Response preview:\n  {result['response'][:300]}...")
    else:
        print(f"  Status: {result['status']}")
        print(f"  Error: {result['response'][:200]}")
        sys.exit(1)

    # ── Phase 3: Post-task Knowledge Capture ──────────────────────
    print(f"\n── Phase 3: Post-task ──")

    if skip_knowledge:
        print(f"  Knowledge capture skipped (--skip-knowledge)")
    else:
        extracted = extract_knowledge_from_response(result["response"])
        total_extracted = len(extracted["decisions"]) + len(extracted["learnings"])

        if total_extracted > 0:
            print(f"  Extracted: {len(extracted['decisions'])} decisions, "
                  f"{len(extracted['learnings'])} learnings")

            for d in extracted["decisions"]:
                print(f"    [D] {d[:80]}...")
            for l in extracted["learnings"]:
                print(f"    [L] {l[:80]}...")

            save_stats = save_knowledge(extracted, stack, agent_name, task, verbose)
            print(f"  Saved: {save_stats['decisions_saved']} decisions, "
                  f"{save_stats['learnings_saved']} learnings "
                  f"(graph: {'yes' if save_stats['graph'] else 'no'}, "
                  f"jsonl: {'yes' if save_stats['jsonl'] else 'no'})")
        else:
            print(f"  No decisions/learnings extracted from response")

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Done: @{agent_name} | {result['tokens_used']} tokens | {result['duration_seconds']}s")
    print(f"{'='*60}\n")

    # Print the full response
    print(result["response"])


if __name__ == "__main__":
    main()
