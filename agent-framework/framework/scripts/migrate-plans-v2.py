#!/usr/bin/env python3
"""Migrate plan JSON files from schema v1.1 to v2.0.

Adds new v2.0 fields with sensible defaults while preserving all existing data.
Non-destructive: creates .v1.1.bak backup before modifying.

Usage:
    python migrate-plans-v2.py --all                  # Migrate all plans
    python migrate-plans-v2.py --stack live-moafunk    # Migrate one stack
    python migrate-plans-v2.py <path-to-plan.json>     # Migrate single plan
    python migrate-plans-v2.py --dry-run --all         # Preview without writing
"""

import json
import re
import shutil
import sys
from pathlib import Path


def migrate_step(step: dict) -> dict:
    """Add v2.0 fields to a plan step."""
    # New fields with defaults
    step.setdefault("parallel_group", None)
    step.setdefault("priority", "normal")
    step.setdefault("estimated_tokens", None)
    step.setdefault("context_needed", [])
    step.setdefault("mcp_tools", [])
    step.setdefault("output", None)
    step.setdefault("artifacts", [])
    step.setdefault("knowledge", {})
    step.setdefault("cross_stack_dependencies", [])

    # If step is completed and has artifacts, create an output stub
    if step["status"] == "completed" and step.get("output") is None:
        files_created = [
            a["path"] for a in step.get("artifacts", [])
            if a.get("type") == "file" and a.get("verified_at")
        ]
        if files_created:
            step["output"] = {
                "summary": f"Completed: {step['task'][:80]}",
                "files_created": files_created,
                "files_modified": [],
                "tokens_used": None,
                "duration_seconds": None,
            }

    # Recursively migrate sub_plan steps
    if "sub_plan" in step and step["sub_plan"]:
        for sub_step in step["sub_plan"].get("steps", []):
            migrate_step(sub_step)

    return step


def migrate_plan(plan: dict) -> dict:
    """Migrate a v1.1 plan to v2.0."""
    if plan.get("schema_version") == "2.0":
        return plan  # Already migrated

    # Bump version
    plan["schema_version"] = "2.0"

    # Add new top-level fields
    plan.setdefault("execution_mode", "sequential")
    plan.setdefault("batch_config", None)
    plan.setdefault("context_sources", [])
    plan.setdefault("token_budget", None)
    plan.setdefault("related_plans", [])

    # Migrate all steps
    for step in plan.get("steps", []):
        migrate_step(step)

    return plan


def find_plans(root: Path, stack: str = None) -> list[Path]:
    """Find all plan JSON files."""
    if stack:
        pattern = f"stacks/{stack}/.copilot-agents/plans/*.json"
    else:
        pattern = "stacks/**/.copilot-agents/plans/*.json"
    return sorted(root.glob(pattern))


def main():
    root = Path(__file__).parent.parent.parent  # copilot-agents/

    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]

    if not args:
        print("Usage: migrate-plans-v2.py [--dry-run] <path> | --all | --stack <name>")
        sys.exit(1)

    if args[0] == "--all":
        plans = find_plans(root)
    elif args[0] == "--stack":
        stack = args[1] if len(args) > 1 else None
        if not stack:
            print("Usage: migrate-plans-v2.py --stack <stack-name>")
            sys.exit(1)
        plans = find_plans(root, stack)
    else:
        plans = [Path(args[0])]

    if not plans:
        print("No plan files found.")
        sys.exit(1)

    migrated = 0
    skipped = 0
    errors = 0

    for plan_path in plans:
        try:
            content = plan_path.read_text()
            # Fix trailing commas
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            plan = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"  ❌ {plan_path.name}: JSON parse error: {e}")
            errors += 1
            continue

        if plan.get("schema_version") == "2.0":
            print(f"  ⏭️  {plan_path.name}: already v2.0")
            skipped += 1
            continue

        old_version = plan.get("schema_version", "unknown")
        migrated_plan = migrate_plan(plan)

        if dry_run:
            new_fields = []
            if "execution_mode" not in content:
                new_fields.append("execution_mode")
            if "token_budget" not in content:
                new_fields.append("token_budget")
            step_count = len(plan.get("steps", []))
            print(f"  📋 {plan_path.name}: {old_version} → 2.0 ({step_count} steps, +{len(new_fields)} top-level fields)")
        else:
            # Backup original
            backup_path = plan_path.with_suffix(".v1.1.bak")
            if not backup_path.exists():
                shutil.copy2(plan_path, backup_path)

            # Write migrated plan
            plan_path.write_text(json.dumps(migrated_plan, indent=2, ensure_ascii=False) + "\n")
            print(f"  ✅ {plan_path.name}: {old_version} → 2.0")
            migrated += 1

    print(f"\nSummary: {len(plans)} plans, {migrated} migrated, {skipped} skipped, {errors} errors")
    if dry_run:
        print("(dry run — no files modified)")


if __name__ == "__main__":
    main()
