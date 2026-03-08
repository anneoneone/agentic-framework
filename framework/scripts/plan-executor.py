#!/usr/bin/env python3
"""Plan Executor — CLI for executing plan steps.

Drives plan execution with pre/post knowledge hooks,
dependency resolution, and progress tracking.

Usage:
    python framework/scripts/plan-executor.py PLAN_FILE [OPTIONS]

Options:
    --dry-run           Show execution schedule without running
    --step STEP_ID      Execute only a specific step
    --mode MODE         Execution mode: sequential (default), validate-only, batch
    --model MODEL       Override model (default: from plan or config)
    --max-tokens N      Max tokens per step (default: 4096)
    --auto-approve      Skip confirmation prompts
    --verbose           Show detailed output
    --batch             Use Anthropic Message Batches API for parallel execution
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT / "framework" / "mcp-servers" / "plan-execution"))


def load_config() -> dict:
    """Load framework config."""
    config_path = ROOT / "framework" / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"model": "claude-sonnet-4-5-20250929", "max_tokens": 4096}


def load_plan(plan_path: str) -> dict:
    """Load and parse plan JSON, handling trailing commas."""
    path = Path(plan_path)
    if not path.exists():
        print(f"Error: Plan file not found: {plan_path}")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    content = re.sub(r",(\s*[}\]])", r"\1", content)
    return json.loads(content)


def save_plan(plan: dict, plan_path: str) -> None:
    """Save plan JSON."""
    Path(plan_path).write_text(
        json.dumps(plan, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def flatten_steps(steps: list) -> list:
    """Flatten hierarchical steps."""
    flat = []
    for step in steps:
        flat.append(step)
        if step.get("sub_plan") and step["sub_plan"].get("steps"):
            flat.extend(flatten_steps(step["sub_plan"]["steps"]))
    return flat


def find_step(steps: list, step_id: str) -> dict | None:
    """Find step by ID in hierarchy."""
    for step in steps:
        if step.get("id") == step_id:
            return step
        if step.get("sub_plan") and step["sub_plan"].get("steps"):
            found = find_step(step["sub_plan"]["steps"], step_id)
            if found:
                return found
    return None


def resolve_waves(steps: list) -> list[list[dict]]:
    """Resolve dependency graph into execution waves."""
    flat = flatten_steps(steps)
    step_map = {s["id"]: s for s in flat}
    completed = {s["id"] for s in flat if s.get("status") in ("completed", "skipped")}
    remaining = [s for s in flat if s["id"] not in completed]
    waves = []

    max_iter = len(remaining) + 1
    iteration = 0

    while remaining and iteration < max_iter:
        iteration += 1

        ready = [
            s for s in remaining
            if all(d in completed for d in s.get("dependencies", []))
        ]

        if not ready:
            break

        groups = defaultdict(list)
        sequential = []

        for s in ready:
            pg = s.get("parallel_group")
            if pg:
                groups[pg].append(s)
            else:
                sequential.append(s)

        for group_id, group_steps in sorted(groups.items()):
            waves.append(group_steps)
            for s in group_steps:
                completed.add(s["id"])

        for s in sequential:
            waves.append([s])
            completed.add(s["id"])

        remaining = [s for s in remaining if s["id"] not in completed]

    return waves


def find_agent_file(agent_name: str) -> Path | None:
    """Find agent .agent.md file."""
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


def display_schedule(plan: dict) -> None:
    """Display execution schedule."""
    waves = resolve_waves(plan.get("steps", []))
    flat = flatten_steps(plan.get("steps", []))
    completed = sum(1 for s in flat if s.get("status") == "completed")
    total = len(flat)
    pct = int(completed / total * 100) if total else 0

    print(f"\nPlan: {plan.get('plan_id', 'unknown')} ({pct}% complete)")
    print(f"Stack: {plan.get('stack', 'unknown')}")
    print(f"Mode: {plan.get('execution_mode', 'sequential')}")
    print(f"Token budget: {plan.get('token_budget', {}).get('estimated_total', '?')} estimated")
    print()

    for wave_num, wave in enumerate(waves):
        if len(wave) > 1:
            print(f"  Wave {wave_num} (parallel):")
            for step in wave:
                status_icon = _status_icon(step.get("status"))
                print(f"    {status_icon} {step['id']}. {step.get('task', '')[:70]} ({step.get('agent', '?')})")
        else:
            step = wave[0]
            status_icon = _status_icon(step.get("status"))
            print(f"  {status_icon} {step['id']}. {step.get('task', '')[:70]} ({step.get('agent', '?')})")

    print()


def _status_icon(status: str) -> str:
    return {
        "completed": "✓",
        "in-progress": "→",
        "blocked": "✗",
        "skipped": "○",
        "pending": " ",
    }.get(status, "?")


def validate_plan(plan: dict) -> tuple[list, list]:
    """Validate plan. Returns (errors, warnings)."""
    errors = []
    warnings = []

    if plan.get("schema_version") != "2.0":
        errors.append(f"Schema version must be 2.0, got {plan.get('schema_version')}")

    for field in ("plan_id", "stack", "description", "steps"):
        if field not in plan:
            errors.append(f"Missing required field: {field}")

    flat = flatten_steps(plan.get("steps", []))
    step_ids = {s["id"] for s in flat}

    for step in flat:
        agent = step.get("agent")
        if agent:
            agent_path = find_agent_file(agent)
            if not agent_path:
                warnings.append(f"Agent not found: {agent}")

        for dep in step.get("dependencies", []):
            if dep not in step_ids:
                errors.append(f"Step {step['id']}: dependency '{dep}' not found")

    # Circular dependency check
    def has_cycle(step_id, visited, rec_stack):
        visited.add(step_id)
        rec_stack.add(step_id)
        step = find_step(plan.get("steps", []), step_id)
        if step:
            for dep in step.get("dependencies", []):
                if dep not in visited:
                    if has_cycle(dep, visited, rec_stack):
                        return True
                elif dep in rec_stack:
                    return True
        rec_stack.discard(step_id)
        return False

    visited = set()
    for s in flat:
        if s["id"] not in visited:
            if has_cycle(s["id"], visited, set()):
                errors.append(f"Circular dependency detected involving step {s['id']}")

    return errors, warnings


def execute_step_api(step: dict, agent_system_prompt: str, model: str, max_tokens: int) -> dict:
    """Execute a single step via Anthropic Messages API."""
    try:
        import anthropic
    except ImportError:
        return {
            "step_id": step["id"],
            "status": "error",
            "summary": "anthropic package not installed",
            "tokens_used": 0,
            "duration_seconds": 0,
        }

    start = time.time()
    task = step.get("task", "Execute this step")

    # Build context
    context_parts = []
    for ctx in step.get("context_needed", []):
        if ctx.get("type") == "file" and ctx.get("path"):
            file_path = ROOT / ctx["path"]
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")[:2000]
                context_parts.append(f"File {ctx['path']}:\n{content}")
        elif ctx.get("type") == "knowledge" and ctx.get("query"):
            context_parts.append(f"Knowledge context: {ctx['query']}")

    user_content = task
    if context_parts:
        user_content = "\n\n".join(context_parts) + "\n\n" + task

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=agent_system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        summary = ""
        if response.content:
            summary = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])

        tokens = response.usage.input_tokens + response.usage.output_tokens
        duration = time.time() - start

        return {
            "step_id": step["id"],
            "status": "completed",
            "summary": summary[:500],
            "tokens_used": tokens,
            "duration_seconds": round(duration, 1),
        }
    except Exception as e:
        return {
            "step_id": step["id"],
            "status": "error",
            "summary": str(e),
            "tokens_used": 0,
            "duration_seconds": round(time.time() - start, 1),
        }


def build_step_request(step: dict, agent_system_prompt: str, model: str, max_tokens: int) -> dict:
    """Build a Messages API request dict for a step (used by batch mode)."""
    task = step.get("task", "Execute this step")

    context_parts = []
    for ctx in step.get("context_needed", []):
        if ctx.get("type") == "file" and ctx.get("path"):
            file_path = ROOT / ctx["path"]
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")[:2000]
                context_parts.append(f"File {ctx['path']}:\n{content}")
        elif ctx.get("type") == "knowledge" and ctx.get("query"):
            context_parts.append(f"Knowledge context: {ctx['query']}")

    user_content = task
    if context_parts:
        user_content = "\n\n".join(context_parts) + "\n\n" + task

    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": agent_system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }


def execute_batch(steps: list[dict], plan: dict, plan_path: str,
                  model: str, max_tokens: int, verbose: bool = False) -> int:
    """Execute steps using the Anthropic Message Batches API.

    Submits all steps as a batch, polls for completion, then updates the plan.
    Returns total tokens used.
    """
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed")
        return 0

    client = anthropic.Anthropic()

    # Build batch requests
    requests = []
    for step in steps:
        agent_name = step.get("agent", "unknown")
        agent_path = find_agent_file(agent_name)
        system_prompt = ""
        if agent_path:
            content = agent_path.read_text(encoding="utf-8")
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    system_prompt = content[end + 3:].strip()

        req_params = build_step_request(step, system_prompt, model, max_tokens)

        requests.append({
            "custom_id": step["id"],
            "params": req_params,
        })

        step["status"] = "in-progress"

    plan["updated_at"] = datetime.now().isoformat()
    save_plan(plan, plan_path)

    print(f"\nSubmitting batch of {len(requests)} steps...")

    try:
        batch = client.messages.batches.create(requests=requests)
        batch_id = batch.id
        print(f"Batch created: {batch_id}")

        # Poll for completion
        while True:
            batch = client.messages.batches.retrieve(batch_id)
            status = batch.processing_status

            counts = batch.request_counts
            total = counts.processing + counts.succeeded + counts.errored + counts.canceled + counts.expired
            done = counts.succeeded + counts.errored + counts.canceled + counts.expired

            print(f"  Status: {status} ({done}/{total} done)", end="\r")

            if status == "ended":
                print(f"\n  Batch completed: {counts.succeeded} succeeded, {counts.errored} errored")
                break

            time.sleep(5)

        # Process results
        total_tokens = 0
        step_map = {s["id"]: s for s in steps}

        for result in client.messages.batches.results(batch_id):
            step_id = result.custom_id
            step = step_map.get(step_id)
            if not step:
                continue

            if result.result.type == "succeeded":
                message = result.result.message
                summary = ""
                if message.content:
                    summary = message.content[0].text if hasattr(message.content[0], "text") else str(message.content[0])

                tokens = message.usage.input_tokens + message.usage.output_tokens
                total_tokens += tokens

                step["status"] = "completed"
                step["output"] = {
                    "summary": summary[:500],
                    "files_modified": [],
                    "files_created": [],
                    "tokens_used": tokens,
                    "duration_seconds": 0,
                    "batch_id": batch_id,
                }

                print(f"  ✓ {step_id}: {tokens} tokens")
                if verbose:
                    print(f"    {summary[:150]}")
            else:
                error_msg = str(result.result.error) if hasattr(result.result, "error") else "Unknown error"
                step["status"] = "error"
                step["output"] = {
                    "summary": error_msg[:500],
                    "files_modified": [],
                    "files_created": [],
                    "tokens_used": 0,
                    "duration_seconds": 0,
                    "batch_id": batch_id,
                }
                print(f"  ✗ {step_id}: {error_msg[:100]}")

        # Update plan
        if "token_budget" not in plan:
            plan["token_budget"] = {"estimated_total": 0, "actual_total": 0}
        plan["token_budget"]["actual_total"] = (
            (plan["token_budget"].get("actual_total") or 0) + total_tokens
        )
        plan["updated_at"] = datetime.now().isoformat()
        save_plan(plan, plan_path)

        return total_tokens

    except Exception as e:
        print(f"\nBatch execution failed: {e}")
        print("Falling back to sequential execution...")
        return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print(__doc__)
        sys.exit(0)

    plan_path = sys.argv[1]
    args = sys.argv[2:]

    dry_run = "--dry-run" in args
    verbose = "--verbose" in args
    auto_approve = "--auto-approve" in args
    batch_mode = "--batch" in args
    validate_only = "--mode" in args and args[args.index("--mode") + 1] == "validate-only" if "--mode" in args else False

    step_id = None
    if "--step" in args:
        idx = args.index("--step")
        step_id = args[idx + 1] if idx + 1 < len(args) else None

    model_override = None
    if "--model" in args:
        idx = args.index("--model")
        model_override = args[idx + 1] if idx + 1 < len(args) else None

    max_tokens = 4096
    if "--max-tokens" in args:
        idx = args.index("--max-tokens")
        max_tokens = int(args[idx + 1]) if idx + 1 < len(args) else 4096

    # Load plan
    plan = load_plan(plan_path)
    config = load_config()

    model = model_override or plan.get("batch_config", {}).get("model") or config.get("model", "claude-sonnet-4-5-20250929")

    # Validate
    print("Validating plan...")
    errors, warnings = validate_plan(plan)

    for e in errors:
        print(f"  ERROR: {e}")
    for w in warnings:
        print(f"  WARN:  {w}")

    if errors:
        print(f"\nValidation failed: {len(errors)} errors")
        sys.exit(1)

    print(f"  Validation passed ({len(warnings)} warnings)")

    if validate_only:
        sys.exit(0)

    # Display schedule
    display_schedule(plan)

    if dry_run:
        print("Dry run — no steps will be executed.")
        sys.exit(0)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    # Determine steps to execute
    waves = resolve_waves(plan.get("steps", []))

    if not waves:
        print("No pending steps to execute.")
        sys.exit(0)

    if step_id:
        step = find_step(plan.get("steps", []), step_id)
        if not step:
            print(f"Error: Step {step_id} not found")
            sys.exit(1)
        steps_to_run = [step]
    else:
        steps_to_run = waves[0]  # Next wave

    # Batch mode: submit all steps in this wave as a batch
    if batch_mode and len(steps_to_run) > 1:
        print(f"\nBatch mode: submitting {len(steps_to_run)} steps as a batch...")
        total_tokens = execute_batch(steps_to_run, plan, plan_path, model, max_tokens, verbose)
    elif batch_mode:
        print("Only 1 step in wave — using sequential execution instead of batch.")
        batch_mode = False

    # Sequential execution (default or single-step batch fallback)
    if not batch_mode:
        total_tokens = 0

        for step in steps_to_run:
            agent_name = step.get("agent", "unknown")
            print(f"\n{'='*60}")
            print(f"Step {step['id']}: {step.get('task', '')[:80]}")
            print(f"Agent: {agent_name} | Priority: {step.get('priority', 'normal')}")
            print(f"{'='*60}")

            if not auto_approve:
                response = input("\nExecute this step? [y/n/s(kip)] ").strip().lower()
                if response == "n":
                    print("Aborted.")
                    sys.exit(0)
                elif response == "s":
                    step["status"] = "skipped"
                    save_plan(plan, plan_path)
                    print(f"Step {step['id']} skipped.")
                    continue

            # Find agent
            agent_path = find_agent_file(agent_name)
            system_prompt = ""
            if agent_path:
                content = agent_path.read_text(encoding="utf-8")
                # Extract body after frontmatter
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end != -1:
                        system_prompt = content[end + 3:].strip()
            else:
                print(f"  Warning: Agent file not found for {agent_name}")

            # Update status
            step["status"] = "in-progress"
            plan["updated_at"] = datetime.now().isoformat()
            save_plan(plan, plan_path)

            # Execute
            print(f"  Executing with model {model}...")
            result = execute_step_api(step, system_prompt, model, max_tokens)

            # Update plan
            step["status"] = result["status"]
            step["output"] = {
                "summary": result["summary"],
                "files_modified": [],
                "files_created": [],
                "tokens_used": result["tokens_used"],
                "duration_seconds": result["duration_seconds"],
            }

            total_tokens += result["tokens_used"]

            if "token_budget" not in plan:
                plan["token_budget"] = {"estimated_total": 0, "actual_total": 0}
            plan["token_budget"]["actual_total"] = (
                (plan["token_budget"].get("actual_total") or 0) + result["tokens_used"]
            )
            plan["updated_at"] = datetime.now().isoformat()
            save_plan(plan, plan_path)

            # Show result
            if result["status"] == "completed":
                print(f"\n  ✓ Completed ({result['tokens_used']} tokens, {result['duration_seconds']}s)")
                if verbose:
                    print(f"\n  Summary: {result['summary'][:200]}")
            else:
                print(f"\n  ✗ {result['status']}: {result['summary'][:200]}")

    # Summary
    flat = flatten_steps(plan.get("steps", []))
    completed = sum(1 for s in flat if s.get("status") == "completed")
    total = len(flat)

    print(f"\n{'='*60}")
    print(f"Progress: {completed}/{total} steps ({int(completed/total*100)}%)")
    print(f"Tokens used this run: {total_tokens}")
    print(f"Total tokens: {plan.get('token_budget', {}).get('actual_total', 0)}")

    if completed == total:
        plan["overall_status"] = "completed"
        save_plan(plan, plan_path)
        print("\nAll steps completed! Run /finalize to lint, test, and commit.")
    else:
        remaining = resolve_waves(plan.get("steps", []))
        if remaining:
            next_ids = [s["id"] for s in remaining[0]]
            print(f"Next: steps {', '.join(next_ids)}")


if __name__ == "__main__":
    main()
