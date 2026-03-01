#!/usr/bin/env python3
"""Post-step hook — Run after a plan step is marked completed.

Automates knowledge extraction and index updates after each step completion.
Designed to be called by @coordinator after `step N completed`.

Actions:
1. Extract knowledge from the completed step
2. Write to stack's extracted knowledge files (deduped)
3. Update step's output field if provided
4. Rebuild knowledge index for the stack
5. Optionally run artifact verification

Usage:
    python post-step-hook.py <plan.json> <step_id>                       # Basic
    python post-step-hook.py <plan.json> <step_id> --summary "text"      # With output
    python post-step-hook.py <plan.json> <step_id> --verify-artifacts    # Plus verification
    python post-step-hook.py <plan.json> <step_id> --tokens 1200         # With token count
"""

import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path


def parse_args():
    """Parse command-line arguments."""
    if len(sys.argv) < 3:
        print("Usage: post-step-hook.py <plan.json> <step_id> [options]")
        sys.exit(1)

    args = {
        "plan_path": Path(sys.argv[1]),
        "step_id": sys.argv[2],
        "summary": None,
        "tokens": None,
        "verify": False,
    }

    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--summary" and i + 1 < len(sys.argv):
            args["summary"] = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--tokens" and i + 1 < len(sys.argv):
            args["tokens"] = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--verify-artifacts":
            args["verify"] = True
            i += 1
        else:
            i += 1

    return args


def find_step(steps: list, step_id: str) -> dict | None:
    """Find a step by ID, including in sub-plans."""
    for step in steps:
        if step["id"] == step_id:
            return step
        if "sub_plan" in step and step["sub_plan"]:
            found = find_step(step["sub_plan"].get("steps", []), step_id)
            if found:
                return found
    return None


def extract_step_knowledge(step: dict) -> list[dict]:
    """Extract knowledge items from a single step."""
    items = []
    k = step.get("knowledge", {})

    for d in k.get("decisions", []):
        items.append({"type": "decision", "content": d})
    for l in k.get("learnings", []):
        items.append({"type": "learning", "content": l})
    for b in k.get("blockers_encountered", []):
        if isinstance(b, dict) and b.get("resolution"):
            items.append({"type": "blocker-resolution", "content": f"{b['issue']} → {b['resolution']}"})
        elif isinstance(b, str) and b:
            items.append({"type": "blocker-resolution", "content": b})

    notes = k.get("notes", "")
    if notes and len(notes) > 20:
        items.append({"type": "note", "content": notes})

    return items


def append_to_jsonl(path: Path, items: list[dict]) -> int:
    """Append items to a JSONL file, deduplicating by content."""
    existing = set()
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                try:
                    existing.add(json.loads(line).get("content", ""))
                except json.JSONDecodeError:
                    pass

    new_items = [i for i in items if i["content"] not in existing]
    if new_items:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            for item in new_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return len(new_items)


def verify_artifacts(step: dict) -> list[str]:
    """Check artifact file existence and return issues."""
    issues = []
    for artifact in step.get("artifacts", []):
        if artifact.get("verification") == "exists":
            path = Path(artifact.get("path", ""))
            # Check multiple possible locations
            if not path.exists():
                issues.append(f"Artifact not found: {artifact.get('path')}")
            elif not artifact.get("verified_at"):
                artifact["verified_at"] = datetime.now().isoformat()
                artifact["auto_verified"] = True
    return issues


def main():
    args = parse_args()
    plan_path = args["plan_path"]

    # Load plan
    content = plan_path.read_text()
    content = re.sub(r',(\s*[}\]])', r'\1', content)
    plan = json.loads(content)

    stack = plan.get("stack", "unknown")
    plan_id = plan.get("plan_id", plan_path.stem)

    # Find the step
    step = find_step(plan.get("steps", []), args["step_id"])
    if not step:
        print(f"❌ Step {args['step_id']} not found in plan")
        sys.exit(1)

    print(f"🔄 Post-step hook: plan={plan_id}, step={args['step_id']}, stack={stack}")

    # 1. Update step output if provided
    if args["summary"] or args["tokens"]:
        if step.get("output") is None:
            step["output"] = {}
        if args["summary"]:
            step["output"]["summary"] = args["summary"]
        if args["tokens"]:
            step["output"]["tokens_used"] = args["tokens"]
            # Update plan token budget
            budget = plan.get("token_budget") or {}
            current_actual = budget.get("actual_total") or 0
            budget["actual_total"] = current_actual + args["tokens"]
            plan["token_budget"] = budget

        print(f"  ✅ Updated step output")

    # 2. Extract knowledge
    items = extract_step_knowledge(step)
    if items:
        # Determine root for knowledge files
        # Navigate from plan path to copilot-agents root
        root = plan_path
        while root.name != "copilot-agents" and root.parent != root:
            root = root.parent

        knowledge_dir = root / "stacks" / stack / "docs" / "knowledge"

        decisions = [i for i in items if i["type"] == "decision"]
        learnings = [i for i in items if i["type"] == "learning"]
        notes = [i for i in items if i["type"] == "note"]
        blockers = [i for i in items if i["type"] == "blocker-resolution"]

        total_new = 0
        if decisions:
            enriched = [
                {**d, "step_id": args["step_id"], "agent": step.get("agent", "?"), "plan_id": plan_id}
                for d in decisions
            ]
            n = append_to_jsonl(knowledge_dir / "decisions" / "extracted-decisions.jsonl", enriched)
            total_new += n

        if learnings:
            enriched = [
                {**l, "step_id": args["step_id"], "agent": step.get("agent", "?"), "plan_id": plan_id}
                for l in learnings
            ]
            n = append_to_jsonl(knowledge_dir / "extracted-learnings.jsonl", enriched)
            total_new += n

        if notes:
            enriched = [
                {**n, "step_id": args["step_id"], "agent": step.get("agent", "?"), "plan_id": plan_id}
                for n in notes
            ]
            n = append_to_jsonl(knowledge_dir / "extracted-notes.jsonl", enriched)
            total_new += n

        if blockers:
            enriched = [
                {**b, "step_id": args["step_id"], "agent": step.get("agent", "?"), "plan_id": plan_id}
                for b in blockers
            ]
            n = append_to_jsonl(knowledge_dir / "extracted-blocker-resolutions.jsonl", enriched)
            total_new += n

        print(f"  ✅ Extracted {len(items)} knowledge items ({total_new} new)")
    else:
        print(f"  ℹ️  No knowledge to extract from step")

    # 3. Verify artifacts if requested
    if args["verify"]:
        issues = verify_artifacts(step)
        if issues:
            print(f"  ⚠️  Artifact issues: {len(issues)}")
            for issue in issues:
                print(f"     - {issue}")
        else:
            verified = len([a for a in step.get("artifacts", []) if a.get("verified_at")])
            print(f"  ✅ Artifacts verified: {verified}")

    # 4. Update plan JSON
    plan["updated_at"] = datetime.now().isoformat()
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(f"  ✅ Plan updated: {plan_path.name}")


if __name__ == "__main__":
    main()
