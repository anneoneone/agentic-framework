#!/usr/bin/env python3
"""Plan Executor — Scaffold for parallel and batch plan execution.

Reads a v2.0 plan JSON, resolves dependencies, and executes steps
respecting parallel_group assignments and priority ordering.

Execution Modes:
- sequential: Execute steps one-by-one in dependency order (default)
- parallel: Execute steps in parallel groups after dependencies resolve
- batch: Submit step groups to Anthropic Batch API (requires API key)

Usage:
    python plan-executor.py <plan.json>                    # Sequential execution (dry-run)
    python plan-executor.py <plan.json> --mode parallel    # Parallel execution plan
    python plan-executor.py <plan.json> --mode batch       # Batch API execution plan
    python plan-executor.py <plan.json> --validate         # Validate plan only
    python plan-executor.py <plan.json> --schedule         # Show execution schedule

Note: This is a SCAFFOLD. Actual agent invocation requires MCP integration
or Anthropic API access. Currently outputs execution plans for review.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional


class ExecutionSchedule:
    """Represents the execution order of plan steps."""

    def __init__(self):
        self.waves: list[list[dict]] = []  # Each wave = parallel-safe group
        self.total_estimated_tokens = 0
        self.critical_path: list[str] = []

    def add_wave(self, steps: list[dict]):
        self.waves.append(steps)
        self.total_estimated_tokens += sum(
            s.get("estimated_tokens", 0) or 0 for s in steps
        )

    def display(self):
        print(f"\n{'='*60}")
        print(f"EXECUTION SCHEDULE ({len(self.waves)} waves)")
        print(f"{'='*60}")

        for i, wave in enumerate(self.waves):
            parallel = len(wave) > 1
            mode = "⚡ PARALLEL" if parallel else "→ SEQUENTIAL"
            group = wave[0].get("parallel_group") or "-"

            print(f"\n── Wave {i+1} ({mode}, group: {group}) ──")
            for step in wave:
                priority_icon = {
                    "critical": "🔴",
                    "high": "🟠",
                    "normal": "🟢",
                    "low": "⚪",
                }.get(step.get("priority", "normal"), "🟢")

                tokens = step.get("estimated_tokens") or "?"
                agent = step.get("agent", "?")
                deps = step.get("dependencies", [])
                mcp = step.get("mcp_tools", [])

                print(f"  {priority_icon} Step {step['id']}: {step['task'][:60]}...")
                print(f"     Agent: {agent} | Tokens: ~{tokens} | Deps: {deps}")
                if mcp:
                    print(f"     MCP tools: {mcp}")

        print(f"\n{'='*60}")
        print(f"Total estimated tokens: ~{self.total_estimated_tokens}")
        print(f"Waves: {len(self.waves)} | Steps: {sum(len(w) for w in self.waves)}")
        if self.critical_path:
            print(f"Critical path: {' → '.join(self.critical_path)}")
        print(f"{'='*60}")


def flatten_steps(steps: list[dict]) -> list[dict]:
    """Flatten hierarchical steps into a flat list, including sub_plan steps."""
    flat = []
    for step in steps:
        flat.append(step)
        if "sub_plan" in step and step["sub_plan"]:
            for sub in step["sub_plan"].get("steps", []):
                flat.append(sub)
                if "sub_plan" in sub and sub["sub_plan"]:
                    flat.extend(sub["sub_plan"].get("steps", []))
    return flat


def resolve_dependencies(steps: list[dict]) -> list[list[dict]]:
    """Topological sort with parallel group awareness.

    Returns waves of steps that can execute concurrently.
    """
    flat = flatten_steps(steps)
    step_map = {s["id"]: s for s in flat}
    completed = set()
    waves = []

    # Track which steps are already done
    for s in flat:
        if s.get("status") in ("completed", "skipped"):
            completed.add(s["id"])

    remaining = [s for s in flat if s["id"] not in completed and s.get("status") != "skipped"]

    max_iterations = len(remaining) + 1
    iteration = 0

    while remaining and iteration < max_iterations:
        iteration += 1

        # Find steps whose dependencies are all satisfied
        ready = []
        for s in remaining:
            deps = s.get("dependencies", [])
            if all(d in completed for d in deps):
                ready.append(s)

        if not ready:
            # Deadlock — circular dependency or missing step
            blocked_ids = [s["id"] for s in remaining]
            print(f"  ⚠️  Deadlock detected. Blocked steps: {blocked_ids}")
            break

        # Group ready steps by parallel_group
        groups = defaultdict(list)
        sequential = []

        for s in ready:
            pg = s.get("parallel_group")
            if pg:
                groups[pg].append(s)
            else:
                sequential.append(s)

        # Emit parallel groups as single waves
        for group_id, group_steps in sorted(groups.items()):
            # Sort by priority within group
            priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
            group_steps.sort(key=lambda s: priority_order.get(s.get("priority", "normal"), 2))
            waves.append(group_steps)
            for s in group_steps:
                completed.add(s["id"])

        # Emit sequential steps individually
        for s in sequential:
            waves.append([s])
            completed.add(s["id"])

        remaining = [s for s in remaining if s["id"] not in completed]

    return waves


def identify_critical_path(steps: list[dict]) -> list[str]:
    """Find the critical path (longest chain of critical/high priority steps)."""
    flat = flatten_steps(steps)
    step_map = {s["id"]: s for s in flat}

    critical = [s for s in flat if s.get("priority") in ("critical", "high")]
    if not critical:
        return []

    # Simple: return IDs of critical steps in dependency order
    return [s["id"] for s in critical]


def validate_plan(plan: dict) -> list[str]:
    """Validate plan structure for execution readiness."""
    errors = []

    if plan.get("schema_version") != "2.0":
        errors.append(f"Expected schema_version 2.0, got {plan.get('schema_version')}")

    if not plan.get("steps"):
        errors.append("Plan has no steps")
        return errors

    flat = flatten_steps(plan["steps"])
    step_ids = {s["id"] for s in flat}

    for step in flat:
        # Check dependencies reference valid steps
        for dep in step.get("dependencies", []):
            if dep not in step_ids:
                errors.append(f"Step {step['id']}: dependency '{dep}' not found")

        # Check agent format
        agent = step.get("agent", "")
        if not agent.startswith("@"):
            errors.append(f"Step {step['id']}: agent '{agent}' must start with @")

        # Check status is valid
        valid_statuses = {"pending", "in-progress", "completed", "blocked", "skipped"}
        if step.get("status") not in valid_statuses:
            errors.append(f"Step {step['id']}: invalid status '{step.get('status')}'")

    # Check for circular dependencies
    visited = set()
    path = set()

    def has_cycle(step_id: str) -> bool:
        if step_id in path:
            return True
        if step_id in visited:
            return False
        visited.add(step_id)
        path.add(step_id)
        step = next((s for s in flat if s["id"] == step_id), None)
        if step:
            for dep in step.get("dependencies", []):
                if has_cycle(dep):
                    return True
        path.discard(step_id)
        return False

    for step in flat:
        if has_cycle(step["id"]):
            errors.append(f"Circular dependency involving step {step['id']}")
            break

    return errors


def resolve_context_sources(
    sources: list[dict], plan: dict, root: Path
) -> list[dict]:
    """Resolve context_needed entries to actual content.

    Supports types: file, knowledge, plan_output.
    Returns list of resolved context items with content.
    """
    resolved = []
    stack = plan.get("stack", "")

    for source in sources:
        src_type = source.get("type", "")
        result = {"type": src_type, "reason": source.get("reason", "")}

        if src_type == "file":
            file_path = root / ".." / "stacks" / stack / source.get("path", "")
            if not file_path.exists():
                # Try relative to copilot-agents root
                file_path = root / source.get("path", "")
            try:
                content = file_path.read_text()
                # Truncate to 2000 chars for token efficiency
                if len(content) > 2000:
                    content = content[:2000] + f"\n... [truncated, {len(content)} chars total]"
                result["content"] = content
                result["path"] = source.get("path", "")
                result["tokens_est"] = len(content.split()) * 1.3  # rough estimate
            except Exception as e:
                result["error"] = f"Could not read {source.get('path')}: {e}"

        elif src_type == "knowledge":
            # Search knowledge files using simple grep (MCP not available in script)
            query = source.get("query", "")
            knowledge_dir = root / "stacks" / stack / "docs" / "knowledge"
            matches = []
            if knowledge_dir.exists():
                for kfile in knowledge_dir.rglob("*.jsonl"):
                    try:
                        for line in kfile.read_text().splitlines():
                            if query.lower() in line.lower():
                                matches.append(line.strip())
                                if len(matches) >= 5:
                                    break
                    except Exception:
                        pass
                    if len(matches) >= 5:
                        break
            result["content"] = "\n".join(matches) if matches else f"No results for: {query}"
            result["matches"] = len(matches)
            result["tokens_est"] = sum(len(m.split()) for m in matches) * 1.3

        elif src_type == "plan_output":
            step_id = source.get("step_id", "")
            flat = flatten_steps(plan.get("steps", []))
            target = next((s for s in flat if s["id"] == step_id), None)
            if target and target.get("output"):
                result["content"] = json.dumps(target["output"], indent=2)
                result["tokens_est"] = len(result["content"].split()) * 1.3
            else:
                result["error"] = f"Step {step_id} has no output yet"

        elif src_type == "mcp_query":
            result["content"] = f"[MCP query deferred: {source.get('query', '')} via {source.get('source', 'unknown')}]"
            result["tokens_est"] = 0

        resolved.append(result)

    return resolved


def display_context_summary(step: dict, resolved: list[dict]):
    """Display resolved context summary for a step."""
    if not resolved:
        return
    total_tokens = sum(r.get("tokens_est", 0) for r in resolved)
    print(f"     Context ({len(resolved)} sources, ~{int(total_tokens)} tokens):")
    for r in resolved:
        status = "✅" if "content" in r else "❌"
        reason = r.get("reason", "")[:40]
        print(f"       {status} {r['type']}: {reason}")


def generate_batch_request(step: dict, plan: dict) -> dict:
    """Generate an Anthropic Batch API request for a single step."""
    batch_config = plan.get("batch_config", {}) or {}

    return {
        "custom_id": f"plan_{plan['plan_id']}_step_{step['id']}",
        "params": {
            "model": batch_config.get("model", "claude-sonnet-4-5-20250929"),
            "max_tokens": 4096,
            "system": f"You are {step['agent']}. Execute the following task as part of plan '{plan['plan_id']}'.",
            "messages": [
                {
                    "role": "user",
                    "content": step["task"],
                }
            ],
        },
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: plan-executor.py <plan.json> [--mode sequential|parallel|batch] [--validate] [--schedule]")
        sys.exit(1)

    plan_path = Path(sys.argv[1])
    mode = "sequential"
    validate_only = "--validate" in sys.argv
    show_schedule = "--schedule" in sys.argv or True  # Default: show schedule

    for i, arg in enumerate(sys.argv):
        if arg == "--mode" and i + 1 < len(sys.argv):
            mode = sys.argv[i + 1]

    # Load plan
    content = plan_path.read_text()
    content = re.sub(r',(\s*[}\]])', r'\1', content)

    try:
        plan = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ JSON error: {e}")
        sys.exit(1)

    print(f"📋 Plan: {plan.get('plan_id', 'unknown')}")
    print(f"   Stack: {plan.get('stack', '?')}")
    print(f"   Schema: v{plan.get('schema_version', '?')}")
    print(f"   Status: {plan.get('overall_status', '?')}")
    print(f"   Mode: {plan.get('execution_mode', 'sequential')} (requested: {mode})")

    # Validate
    errors = validate_plan(plan)
    if errors:
        print(f"\n❌ Validation failed ({len(errors)} errors):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"\n✅ Validation passed")

    if validate_only:
        sys.exit(0)

    # Build execution schedule
    waves = resolve_dependencies(plan["steps"])
    schedule = ExecutionSchedule()
    for wave in waves:
        schedule.add_wave(wave)
    schedule.critical_path = identify_critical_path(plan["steps"])

    schedule.display()

    # Resolve context if requested
    if "--context" in sys.argv:
        print(f"\n── Context Resolution ──")
        root = plan_path.parent.parent.parent.parent  # Navigate up to copilot-agents/
        flat = flatten_steps(plan["steps"])

        # Plan-level context
        plan_ctx = plan.get("context_sources", [])
        if plan_ctx:
            resolved = resolve_context_sources(plan_ctx, plan, root)
            total_tokens = sum(r.get("tokens_est", 0) for r in resolved)
            print(f"\n  Plan-level context ({len(plan_ctx)} sources, ~{int(total_tokens)} tokens):")
            for r in resolved:
                status = "✅" if "content" in r else "❌"
                print(f"    {status} {r['type']}: {r.get('reason', r.get('path', ''))[:60]}")

        # Step-level context
        for step in flat:
            step_ctx = step.get("context_needed", [])
            if step_ctx:
                resolved = resolve_context_sources(step_ctx, plan, root)
                total_tokens = sum(r.get("tokens_est", 0) for r in resolved)
                print(f"\n  Step {step['id']} context ({len(step_ctx)} sources, ~{int(total_tokens)} tokens):")
                for r in resolved:
                    status = "✅" if "content" in r else "❌"
                    print(f"    {status} {r['type']}: {r.get('reason', r.get('path', ''))[:60]}")

    # For batch mode, show request structure
    if mode == "batch":
        print(f"\n── Batch API Requests ──")
        for wave in waves:
            for step in wave:
                req = generate_batch_request(step, plan)
                print(f"\n  Request: {req['custom_id']}")
                print(f"  Model: {req['params']['model']}")
                print(f"  Agent: {step['agent']}")
                print(f"  Task: {step['task'][:80]}...")

        batch_config = plan.get("batch_config", {}) or {}
        print(f"\n  Batch config:")
        print(f"    Max concurrent: {batch_config.get('max_concurrent', 5)}")
        print(f"    Timeout: {batch_config.get('timeout_seconds', 300)}s")
        print(f"    Approval required: {batch_config.get('approval_required', True)}")


if __name__ == "__main__":
    main()
