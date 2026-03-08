#!/usr/bin/env python3
"""Knowledge Sync — Extract knowledge from plans and sync to memento graph.

Reads completed plan steps, extracts decisions/learnings/notes from step
outputs and knowledge objects, and pushes them to the Neo4j knowledge graph
via GraphManager.ingest_step_knowledge().

Also writes knowledge entries to JSONL files for offline access.

Usage:
    python framework/scripts/knowledge-sync.py PLAN_FILE [OPTIONS]

Options:
    --stack STACK       Override stack name (default: from plan)
    --step STEP_ID      Sync only a specific step
    --dry-run           Show what would be synced without writing
    --import-stack STK  Import all existing JSONL/MD knowledge for a stack
    --import-all        Import knowledge for all stacks
    --verbose           Show detailed output
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT / "framework" / "mcp-servers" / "memento-knowledge"))


def load_plan(plan_path: str) -> dict:
    """Load plan JSON, handling trailing commas."""
    path = Path(plan_path)
    if not path.exists():
        print(f"Error: Plan file not found: {plan_path}")
        sys.exit(1)
    content = path.read_text(encoding="utf-8")
    content = re.sub(r",(\s*[}\]])", r"\1", content)
    return json.loads(content)


def flatten_steps(steps: list) -> list:
    """Flatten hierarchical steps."""
    flat = []
    for step in steps:
        flat.append(step)
        if step.get("sub_plan") and step["sub_plan"].get("steps"):
            flat.extend(flatten_steps(step["sub_plan"]["steps"]))
    return flat


def extract_knowledge_from_step(step: dict) -> list[dict]:
    """Extract knowledge items from a completed step.

    Sources:
    1. step.knowledge.decisions / step.knowledge.learnings (explicit)
    2. step.output.summary (heuristic extraction)
    """
    items = []

    # 1. Explicit knowledge entries
    knowledge = step.get("knowledge", {})

    for decision in knowledge.get("decisions", []):
        if isinstance(decision, str):
            items.append({"type": "decision", "content": decision})
        elif isinstance(decision, dict) and decision.get("content"):
            items.append({"type": "decision", "content": decision["content"]})

    for learning in knowledge.get("learnings", []):
        if isinstance(learning, str):
            items.append({"type": "learning", "content": learning})
        elif isinstance(learning, dict) and learning.get("content"):
            items.append({"type": "learning", "content": learning["content"]})

    for note in knowledge.get("notes", []):
        if isinstance(note, str):
            items.append({"type": "note", "content": note})
        elif isinstance(note, dict) and note.get("content"):
            items.append({"type": "note", "content": note["content"]})

    # 2. If no explicit knowledge, create a note from the output summary
    if not items:
        output = step.get("output", {})
        summary = output.get("summary", "")
        if summary and len(summary) > 20:
            task = step.get("task", "Unknown task")
            items.append({
                "type": "note",
                "content": f"Step {step.get('id', '?')}: {task} — {summary[:300]}",
            })

    return items


def write_jsonl(items: list[dict], stack: str, plan_id: str) -> Path:
    """Write knowledge items to a JSONL file in the stack's knowledge dir."""
    knowledge_dir = ROOT / "stacks" / stack / "docs" / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    filename = f"plan-{plan_id}-knowledge.jsonl"
    filepath = knowledge_dir / filename

    with open(filepath, "a", encoding="utf-8") as f:
        for item in items:
            entry = {
                "type": item["type"],
                "content": item["content"],
                "plan_id": plan_id,
                "step_id": item.get("step_id", ""),
                "agent": item.get("agent", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            f.write(json.dumps(entry, default=str) + "\n")

    return filepath


def sync_plan(plan_path: str, step_id: str | None = None,
              dry_run: bool = False, verbose: bool = False,
              stack_override: str | None = None) -> dict:
    """Sync knowledge from a plan to memento and JSONL.

    Returns stats dict.
    """
    plan = load_plan(plan_path)
    stack = stack_override or plan.get("stack", "unknown")
    plan_id = plan.get("plan_id", Path(plan_path).stem)

    steps = flatten_steps(plan.get("steps", []))
    completed_steps = [
        s for s in steps
        if s.get("status") in ("completed", "skipped")
    ]

    if step_id:
        completed_steps = [s for s in completed_steps if s.get("id") == step_id]
        if not completed_steps:
            print(f"Step {step_id} not found or not completed.")
            return {"synced": 0}

    # Collect all knowledge items
    all_items = []
    for step in completed_steps:
        items = extract_knowledge_from_step(step)
        for item in items:
            item["step_id"] = step.get("id", "")
            item["agent"] = step.get("agent", "")
        all_items.extend(items)

    if not all_items:
        print("No knowledge items to sync.")
        return {"synced": 0}

    print(f"\nKnowledge items found: {len(all_items)}")
    for item in all_items:
        icon = {"decision": "D", "learning": "L", "note": "N"}.get(item["type"], "?")
        print(f"  [{icon}] {item['content'][:80]}...")

    if dry_run:
        print("\nDry run — nothing written.")
        return {"synced": 0, "found": len(all_items)}

    # Write to JSONL
    jsonl_path = write_jsonl(all_items, stack, plan_id)
    print(f"\nWritten to: {jsonl_path}")

    # Push to Neo4j via GraphManager
    neo4j_stats = {"decisions": 0, "learnings": 0, "notes": 0}
    try:
        from graph import GraphManager
        graph = GraphManager(
            uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )

        neo4j_stats = graph.ingest_step_knowledge(
            stack=stack,
            plan_id=plan_id,
            step_id=step_id or "all",
            agent=None,
            knowledge_items=all_items,
        )
        print(f"Neo4j sync: {neo4j_stats}")
        graph.close()

    except Exception as e:
        print(f"Neo4j sync skipped: {e}")
        print("  Knowledge saved to JSONL only. Start Neo4j to enable graph sync.")

    return {
        "synced": len(all_items),
        "jsonl_path": str(jsonl_path),
        "neo4j": neo4j_stats,
    }


def import_stack_knowledge(stack: str, verbose: bool = False) -> dict:
    """Import all existing knowledge for a stack into Neo4j."""
    try:
        from graph import GraphManager
        from import_knowledge import import_stack as do_import

        graph = GraphManager(
            uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )

        stats = do_import(graph, ROOT, stack)
        graph.close()

        print(f"\nImported knowledge for stack '{stack}':")
        for key, val in stats.items():
            print(f"  {key}: {val}")

        return stats

    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def import_all_knowledge(verbose: bool = False) -> dict:
    """Import knowledge for all stacks."""
    stacks_dir = ROOT / "stacks"
    if not stacks_dir.exists():
        print("No stacks directory found.")
        return {}

    results = {}
    for stack_dir in sorted(stacks_dir.iterdir()):
        if stack_dir.is_dir() and not stack_dir.name.startswith("."):
            print(f"\n{'='*40}")
            print(f"Stack: {stack_dir.name}")
            results[stack_dir.name] = import_stack_knowledge(stack_dir.name, verbose)

    return results


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print(__doc__)
        sys.exit(0)

    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args
    import_all = "--import-all" in args

    stack_override = None
    if "--stack" in args:
        idx = args.index("--stack")
        stack_override = args[idx + 1] if idx + 1 < len(args) else None

    step_id = None
    if "--step" in args:
        idx = args.index("--step")
        step_id = args[idx + 1] if idx + 1 < len(args) else None

    if "--import-stack" in args:
        idx = args.index("--import-stack")
        stack_name = args[idx + 1] if idx + 1 < len(args) else None
        if not stack_name:
            print("Error: --import-stack requires a stack name")
            sys.exit(1)
        import_stack_knowledge(stack_name, verbose)
        sys.exit(0)

    if import_all:
        import_all_knowledge(verbose)
        sys.exit(0)

    # Default: sync from a plan file
    plan_path = args[0]
    if plan_path.startswith("--"):
        print("Error: first argument must be a plan file path")
        print(__doc__)
        sys.exit(1)

    stats = sync_plan(plan_path, step_id=step_id, dry_run=dry_run,
                      verbose=verbose, stack_override=stack_override)

    print(f"\nSync complete: {stats.get('synced', 0)} items")


if __name__ == "__main__":
    main()
