#!/usr/bin/env python3
"""Normalize plan step status values: 'done' → 'completed'.

Scans all JSON plan files and fixes inconsistent status enum usage.
The canonical statuses are: pending, in-progress, completed, blocked, skipped.
"""

import json
import sys
from pathlib import Path


def normalize_steps(steps: list, fixed_count: int = 0) -> int:
    """Recursively normalize status in steps and sub-plans."""
    for step in steps:
        if step.get("status") == "done":
            step["status"] = "completed"
            fixed_count += 1
        sub_plan = step.get("sub_plan")
        if sub_plan and "steps" in sub_plan:
            fixed_count = normalize_steps(sub_plan["steps"], fixed_count)
    return fixed_count


def normalize_plan(plan_path: Path) -> int:
    """Normalize a single plan file. Returns count of fixed statuses."""
    with open(plan_path, "r") as f:
        plan = json.load(f)

    fixed = normalize_steps(plan.get("steps", []))

    # Also normalize overall_status
    if plan.get("overall_status") == "done":
        plan["overall_status"] = "completed"
        fixed += 1

    if fixed > 0:
        with open(plan_path, "w") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Fixed {fixed} status(es) in {plan_path.name}")

    return fixed


def main():
    stacks_dir = Path(__file__).parent.parent.parent / "stacks"

    if not stacks_dir.exists():
        print(f"Stacks directory not found: {stacks_dir}")
        sys.exit(1)

    total_fixed = 0
    total_files = 0

    for plan_file in sorted(stacks_dir.glob("*/.copilot-agents/plans/*.json")):
        total_files += 1
        try:
            fixed = normalize_plan(plan_file)
            total_fixed += fixed
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ERROR parsing {plan_file.name}: {e}")

    print(f"\nSummary: Scanned {total_files} plans, fixed {total_fixed} status values.")


if __name__ == "__main__":
    main()
