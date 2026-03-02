#!/usr/bin/env python3
"""Extract reusable knowledge from completed plan steps and persist to stack knowledge files.

Scans plan JSON files for completed steps with populated knowledge objects,
then writes decisions, learnings, and patterns to the stack's docs/knowledge/ directory.

Usage:
    python extract-knowledge.py --stack live-moafunk                  # Extract from all plans in stack
    python extract-knowledge.py --plan <path-to-plan.json>            # Extract from single plan
    python extract-knowledge.py --stack live-moafunk --since 2026-02  # Only plans from Feb 2026+
    python extract-knowledge.py --dry-run --stack live-moafunk        # Preview without writing
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Regex patterns for auto-extraction from agent responses
DECISION_PATTERNS = [
    r"(?:I |We )?chose (.+?) because (.+)",
    r"(?:I |We )?decided to (.+?) (?:instead of|rather than) (.+)",
    r"Using (.+?) approach (?:because|since|as) (.+)",
    r"The best approach is (.+?) (?:because|since) (.+)",
]

LEARNING_PATTERNS = [
    r"(?:I |We )?(?:discovered|found|learned) that (.+)",
    r"(?:Important|Key) (?:insight|finding|learning): (.+)",
    r"Performance improved by (.+)",
    r"Pitfall: (.+)",
    r"(?:Note|TIL|Gotcha): (.+)",
]

BLOCKER_PATTERNS = [
    r"(?:B|b)locked by (.+)",
    r"(?:C|c)annot proceed (?:because|until) (.+)",
    r"(?:W|w)aiting for (.+)",
]


def extract_from_text(text: str) -> dict:
    """Extract knowledge items from free-form text using regex patterns."""
    knowledge = {"decisions": [], "learnings": [], "blockers": []}

    for pattern in DECISION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            knowledge["decisions"].append(match.group(0).strip())

    for pattern in LEARNING_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            knowledge["learnings"].append(match.group(0).strip())

    for pattern in BLOCKER_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            knowledge["blockers"].append(match.group(0).strip())

    return knowledge


def collect_step_knowledge(step: dict, plan_id: str) -> list[dict]:
    """Recursively collect knowledge from a step and its sub-steps."""
    items = []
    k = step.get("knowledge", {})

    if not k or k == {}:
        # Try extracting from task description and notes
        auto = extract_from_text(step.get("task", "") + " " + k.get("notes", ""))
        if any(auto.values()):
            k = auto

    # Collect decisions
    for d in k.get("decisions", []):
        items.append({
            "type": "decision",
            "content": d,
            "step_id": step["id"],
            "agent": step.get("agent", "unknown"),
            "plan_id": plan_id,
        })

    # Collect learnings
    for l in k.get("learnings", []):
        items.append({
            "type": "learning",
            "content": l,
            "step_id": step["id"],
            "agent": step.get("agent", "unknown"),
            "plan_id": plan_id,
        })

    # Collect blocker resolutions
    for b in k.get("blockers_encountered", []):
        if isinstance(b, dict) and b.get("resolution"):
            items.append({
                "type": "blocker-resolution",
                "content": f"{b['issue']} → {b['resolution']}",
                "step_id": step["id"],
                "agent": step.get("agent", "unknown"),
                "plan_id": plan_id,
            })
        elif isinstance(b, str) and b:
            items.append({
                "type": "blocker-resolution",
                "content": b,
                "step_id": step["id"],
                "agent": step.get("agent", "unknown"),
                "plan_id": plan_id,
            })

    # Collect notes as learnings if substantial
    notes = k.get("notes", "")
    if notes and len(notes) > 20:
        items.append({
            "type": "note",
            "content": notes,
            "step_id": step["id"],
            "agent": step.get("agent", "unknown"),
            "plan_id": plan_id,
        })

    # Recurse into sub_plan
    if "sub_plan" in step and step["sub_plan"]:
        for sub in step["sub_plan"].get("steps", []):
            items.extend(collect_step_knowledge(sub, plan_id))

    return items


def process_plan(plan_path: Path) -> list[dict]:
    """Extract all knowledge items from a plan."""
    content = plan_path.read_text()
    content = re.sub(r',(\s*[}\]])', r'\1', content)  # Fix trailing commas

    try:
        plan = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  ❌ {plan_path.name}: JSON error: {e}")
        return []

    plan_id = plan.get("plan_id", plan_path.stem)
    items = []

    for step in plan.get("steps", []):
        if step.get("status") in ("completed", "blocked"):
            items.extend(collect_step_knowledge(step, plan_id))

    return items


def write_knowledge_files(
    stack_root: Path,
    items: list[dict],
    dry_run: bool = False,
) -> dict:
    """Write extracted knowledge to stack knowledge directory."""
    knowledge_dir = stack_root / "docs" / "knowledge"
    decisions_dir = knowledge_dir / "decisions"
    patterns_dir = knowledge_dir / "patterns"

    stats = {"decisions": 0, "learnings": 0, "blocker_resolutions": 0, "notes": 0}

    # Group by type
    decisions = [i for i in items if i["type"] == "decision"]
    learnings = [i for i in items if i["type"] == "learning"]
    resolutions = [i for i in items if i["type"] == "blocker-resolution"]
    notes = [i for i in items if i["type"] == "note"]

    # Write decisions as JSONL
    if decisions:
        path = decisions_dir / "extracted-decisions.jsonl"
        if not dry_run:
            decisions_dir.mkdir(parents=True, exist_ok=True)
            existing = set()
            if path.exists():
                for line in path.read_text().splitlines():
                    if line.strip():
                        try:
                            existing.add(json.loads(line).get("content", ""))
                        except json.JSONDecodeError:
                            pass

            new_decisions = [d for d in decisions if d["content"] not in existing]
            if new_decisions:
                with open(path, "a") as f:
                    for d in new_decisions:
                        f.write(json.dumps(d, ensure_ascii=False) + "\n")
                stats["decisions"] = len(new_decisions)
        else:
            stats["decisions"] = len(decisions)

    # Write learnings as JSONL
    if learnings:
        path = knowledge_dir / "extracted-learnings.jsonl"
        if not dry_run:
            existing = set()
            if path.exists():
                for line in path.read_text().splitlines():
                    if line.strip():
                        try:
                            existing.add(json.loads(line).get("content", ""))
                        except json.JSONDecodeError:
                            pass

            new_learnings = [l for l in learnings if l["content"] not in existing]
            if new_learnings:
                with open(path, "a") as f:
                    for l in new_learnings:
                        f.write(json.dumps(l, ensure_ascii=False) + "\n")
                stats["learnings"] = len(new_learnings)
        else:
            stats["learnings"] = len(learnings)

    # Write blocker resolutions as JSONL
    if resolutions:
        path = knowledge_dir / "extracted-blocker-resolutions.jsonl"
        if not dry_run:
            existing = set()
            if path.exists():
                for line in path.read_text().splitlines():
                    if line.strip():
                        try:
                            existing.add(json.loads(line).get("content", ""))
                        except json.JSONDecodeError:
                            pass

            new_res = [r for r in resolutions if r["content"] not in existing]
            if new_res:
                with open(path, "a") as f:
                    for r in new_res:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                stats["blocker_resolutions"] = len(new_res)
        else:
            stats["blocker_resolutions"] = len(resolutions)

    # Write substantial notes
    if notes:
        path = knowledge_dir / "extracted-notes.jsonl"
        if not dry_run:
            existing = set()
            if path.exists():
                for line in path.read_text().splitlines():
                    if line.strip():
                        try:
                            existing.add(json.loads(line).get("content", ""))
                        except json.JSONDecodeError:
                            pass

            new_notes = [n for n in notes if n["content"] not in existing]
            if new_notes:
                with open(path, "a") as f:
                    for n in new_notes:
                        f.write(json.dumps(n, ensure_ascii=False) + "\n")
                stats["notes"] = len(new_notes)
        else:
            stats["notes"] = len(notes)

    return stats


def find_plans(root: Path, stack: str, since: Optional[str] = None) -> list[Path]:
    """Find plan files, optionally filtered by date prefix."""
    plan_dir = root / "stacks" / stack / ".copilot-agents" / "plans"
    if not plan_dir.exists():
        return []

    plans = sorted(plan_dir.glob("*.json"))

    if since:
        plans = [p for p in plans if p.stem >= since]

    # Exclude backup files
    plans = [p for p in plans if not p.name.endswith(".bak")]

    return plans


def main():
    root = Path(__file__).parent.parent.parent  # copilot-agents/

    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]

    stack = None
    plan_path = None
    since = None

    i = 0
    while i < len(args):
        if args[i] == "--stack" and i + 1 < len(args):
            stack = args[i + 1]
            i += 2
        elif args[i] == "--plan" and i + 1 < len(args):
            plan_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--since" and i + 1 < len(args):
            since = args[i + 1]
            i += 2
        else:
            i += 1

    if not stack and not plan_path:
        print("Usage: extract-knowledge.py [--dry-run] --stack <name> [--since YYYY-MM] | --plan <path>")
        sys.exit(1)

    if plan_path:
        plans = [plan_path]
        # Infer stack from path
        parts = plan_path.parts
        for j, p in enumerate(parts):
            if p == "stacks" and j + 1 < len(parts):
                stack = parts[j + 1]
                break
    else:
        plans = find_plans(root, stack, since)

    if not plans:
        print("No plan files found.")
        sys.exit(1)

    print(f"Extracting knowledge from {len(plans)} plan(s) in stack '{stack}'...")

    all_items = []
    for plan_path in plans:
        items = process_plan(plan_path)
        if items:
            print(f"  📋 {plan_path.name}: {len(items)} knowledge items")
        all_items.extend(items)

    if not all_items:
        print("\nNo knowledge items found in completed steps.")
        sys.exit(0)

    stack_root = root / "stacks" / stack
    stats = write_knowledge_files(stack_root, all_items, dry_run)

    total = sum(stats.values())
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Extracted {total} knowledge items:")
    print(f"  Decisions: {stats['decisions']}")
    print(f"  Learnings: {stats['learnings']}")
    print(f"  Blocker resolutions: {stats['blocker_resolutions']}")
    print(f"  Notes: {stats['notes']}")

    if not dry_run and total > 0:
        print(f"\nWritten to: {stack_root / 'docs' / 'knowledge'}/")


if __name__ == "__main__":
    main()
