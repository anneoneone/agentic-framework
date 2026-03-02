#!/usr/bin/env python3
"""Plan Executor — Full execution engine for v2.0 plans.

Supports three execution backends:
1. Messages API: Sequential step execution
2. Batch API: Parallel wave execution with polling
3. Dry-run: Schedule visualization and validation

Features:
- Human approval gates for critical/high priority steps
- Context resolution with token budgeting
- Automatic resume from last incomplete step
- Real-time progress monitoring
- Post-step hook integration

Usage:
    python plan-executor.py <plan.json>                    # Sequential dry-run
    python plan-executor.py <plan.json> --mode sequential  # Sequential execution
    python plan-executor.py <plan.json> --mode batch       # Batch API execution
    python plan-executor.py <plan.json> --mode dry-run     # Plan visualization
    python plan-executor.py <plan.json> --validate         # Validate only
    python plan-executor.py <plan.json> --auto-approve     # Skip approval prompts
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
import traceback


# Third-party imports
try:
    import anthropic
except ImportError:
    print("Error: anthropic SDK not installed. Install with: pip install anthropic")
    sys.exit(1)


@dataclass
class ExecutionConfig:
    """Configuration for plan execution."""
    model: str = "claude-sonnet-4-5-20250929"
    api_key: str = ""
    max_tokens_per_step: int = 4096
    approval_required: bool = True
    auto_approve_priority: list = field(default_factory=lambda: ["normal", "low"])
    poll_interval: int = 30
    timeout_per_step: int = 300
    dry_run: bool = False
    context_budget: int = 2000
    auto_approve: bool = False
    verbose: bool = False
    output_dir: Optional[Path] = None

    @classmethod
    def from_args_and_env(cls, args) -> "ExecutionConfig":
        """Build config from CLI args and environment variables."""
        return cls(
            model=args.model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            max_tokens_per_step=args.max_tokens or 4096,
            approval_required=not args.auto_approve and not args.dry_run,
            auto_approve=args.auto_approve,
            dry_run=args.mode == "dry-run",
            verbose=args.verbose,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: str
    status: str  # "completed", "failed", "blocked", "skipped"
    summary: str = ""
    files_modified: list = field(default_factory=list)
    files_created: list = field(default_factory=list)
    tokens_used: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    output: Optional[dict] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


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
            # Deadlock
            blocked_ids = [s["id"] for s in remaining]
            print(f"  Warning: Deadlock detected. Blocked steps: {blocked_ids}")
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
    critical = [s for s in flat if s.get("priority") in ("critical", "high")]
    return [s["id"] for s in critical] if critical else []


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

    Supports types: file, knowledge, plan_output, mcp_query.
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
                file_path = root / source.get("path", "")
            try:
                content = file_path.read_text()
                # Truncate to 2000 chars for token efficiency
                if len(content) > 2000:
                    content = content[:2000] + f"\n... [truncated, {len(content)} chars total]"
                result["content"] = content
                result["path"] = source.get("path", "")
                result["tokens_est"] = len(content.split()) * 1.3
            except Exception as e:
                result["error"] = f"Could not read {source.get('path')}: {e}"

        elif src_type == "knowledge":
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


def find_agent_file(agent_name: str, plan_path: Path) -> Optional[Path]:
    """Find the agent .md file relative to plan.

    Search order:
    1. agents/ (at stack root)
    2. .copilot-agents/agents/ (relative to plan)
    3. framework/core/agents/ (at framework root)
    """
    agent_filename = f"{agent_name}.agent.md" if not agent_name.endswith(".md") else agent_name

    # Search relative to plan directory
    candidates = [
        plan_path.parent / agent_filename,
        plan_path.parent / ".." / ".." / "agents" / agent_filename,
        plan_path.parent / ".copilot-agents" / "agents" / agent_filename,
        plan_path.parent / ".." / ".." / "framework" / "core" / "agents" / agent_filename,
    ]

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.resolve()
        except (OSError, RuntimeError):
            continue

    return None


def extract_system_prompt(agent_md_path: Path) -> str:
    """Extract system prompt from agent markdown file.

    Reads .agent.md file, skips YAML frontmatter, returns markdown content.
    """
    try:
        content = agent_md_path.read_text()

        # Skip YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()

        return content
    except Exception as e:
        return f"[Error reading agent file: {e}]"


class ProgressMonitor:
    """Real-time execution progress display."""

    def __init__(self, config: ExecutionConfig):
        self.config = config

    def on_wave_start(self, wave_num: int, steps: list[dict]):
        parallel = len(steps) > 1
        mode = "PARALLEL" if parallel else "SEQUENTIAL"
        print(f"\n[Wave {wave_num}] {mode} ({len(steps)} step{'s' if len(steps) > 1 else ''})")
        for step in steps:
            priority_icon = {"critical": "[!!]", "high": "[!]", "normal": "[.]", "low": "[*]"}.get(
                step.get("priority", "normal"), "[.]"
            )
            print(f"  {priority_icon} {step['id']}: {step['task'][:70]}")

    def on_step_start(self, step: dict):
        print(f"    Executing {step['id']}...", end=" ", flush=True)

    def on_step_complete(self, step: dict, result: StepResult):
        status_mark = {
            "completed": "OK",
            "failed": "FAIL",
            "blocked": "BLOCKED",
            "skipped": "SKIP",
        }.get(result.status, "?")
        print(f"{status_mark} ({result.tokens_used} tokens, {result.duration_seconds:.1f}s)")
        if result.error:
            print(f"      Error: {result.error}")

    def on_approval_needed(self, step: dict) -> bool:
        """Prompt user for approval. Returns True if approved."""
        priority_icon = {"critical": "!", "high": "!"}.get(step.get("priority", "normal"), "")
        print(f"\n  {priority_icon} Approval required: {step['id']}")
        print(f"     Priority: {step.get('priority', 'normal')}")
        print(f"     Task: {step['task']}")
        print(f"     Agent: {step.get('agent', '?')}")

        while True:
            response = input("  [y]es / [n]o / [s]kip / [a]bort? ").strip().lower()
            if response in ("y", "yes"):
                return True
            elif response in ("n", "no", "s", "skip"):
                return False
            elif response in ("a", "abort"):
                raise KeyboardInterrupt("Execution aborted by user")
            else:
                print("  Invalid response. Try again.")

    def display_summary(self, plan: dict, results: list[StepResult]):
        """Display execution summary."""
        print(f"\n{'='*60}")
        print(f"Execution Summary")
        print(f"{'='*60}")

        by_status = defaultdict(list)
        for result in results:
            by_status[result.status].append(result)

        total_tokens = sum(r.tokens_used for r in results)
        total_time = sum(r.duration_seconds for r in results)

        for status in ["completed", "failed", "blocked", "skipped"]:
            items = by_status.get(status, [])
            if items:
                print(f"  {status.upper()}: {len(items)} step(s)")

        print(f"\n  Total tokens: {total_tokens}")
        print(f"  Total time: {total_time:.1f}s")
        print(f"{'='*60}")


class PlanUpdater:
    """Handles plan JSON updates after each step."""

    @staticmethod
    def update_step(plan_path: Path, step_id: str, result: StepResult):
        """Update a step in the plan JSON."""
        try:
            content = plan_path.read_text()
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            plan = json.loads(content)

            flat = flatten_steps(plan.get("steps", []))
            target = next((s for s in flat if s["id"] == step_id), None)

            if target:
                target["status"] = result.status
                target["output"] = result.output or {}
                target["files_modified"] = result.files_modified
                target["files_created"] = result.files_created
                target["timestamp"] = result.timestamp

                # Update plan JSON
                with open(plan_path, "w") as f:
                    json.dump(plan, f, indent=2)
        except Exception as e:
            print(f"  Warning: Could not update step {step_id}: {e}")

    @staticmethod
    def update_token_budget(plan_path: Path, tokens_used: int):
        """Update total tokens used in plan."""
        try:
            content = plan_path.read_text()
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            plan = json.loads(content)

            if "token_budget" not in plan:
                plan["token_budget"] = {"allocated": 100000, "actual_total": 0}

            plan["token_budget"]["actual_total"] += tokens_used

            with open(plan_path, "w") as f:
                json.dump(plan, f, indent=2)
        except Exception as e:
            print(f"  Warning: Could not update token budget: {e}")

    @staticmethod
    def mark_plan_complete(plan_path: Path):
        """Mark plan as completed."""
        try:
            content = plan_path.read_text()
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            plan = json.loads(content)

            plan["overall_status"] = "completed"
            plan["completed_at"] = datetime.now().isoformat()

            with open(plan_path, "w") as f:
                json.dump(plan, f, indent=2)
        except Exception as e:
            print(f"  Warning: Could not mark plan complete: {e}")


class StepExecutor:
    """Handles single step execution via Messages API."""

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.api_key) if config.api_key else None

    def execute(self, step: dict, plan: dict, plan_path: Path, root: Path) -> StepResult:
        """Execute a single step via Messages API."""
        step_id = step.get("id", "unknown")
        start_time = time.time()

        try:
            # Resolve context
            context_needed = step.get("context_needed", [])
            resolved_context = resolve_context_sources(context_needed, plan, root) if context_needed else []

            # Build system prompt
            agent_name = step.get("agent", "@unknown").lstrip("@")
            agent_file = find_agent_file(agent_name, plan_path)
            if agent_file:
                system_prompt = extract_system_prompt(agent_file)
            else:
                system_prompt = f"You are {step.get('agent', 'an agent')}. Execute the following task."

            # Build user message
            user_message = self._build_user_message(step, plan, resolved_context)

            # Call Messages API
            if self.config.verbose:
                print(f"\n    System prompt (first 200 chars): {system_prompt[:200]}...")
                print(f"    User message (first 200 chars): {user_message[:200]}...")

            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens_per_step,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            # Parse response
            result = self._parse_response(response, step_id)
            result.duration_seconds = time.time() - start_time

            # Update plan
            PlanUpdater.update_step(plan_path, step_id, result)
            PlanUpdater.update_token_budget(plan_path, result.tokens_used)

            # Save output if requested
            if self.config.output_dir:
                self.config.output_dir.mkdir(parents=True, exist_ok=True)
                output_file = self.config.output_dir / f"step-{step_id}.json"
                with open(output_file, "w") as f:
                    json.dump(
                        {
                            "step_id": step_id,
                            "request": {
                                "model": self.config.model,
                                "system": system_prompt[:500],  # Truncate for brevity
                                "user_message": user_message[:500],
                            },
                            "response": {
                                "status": result.status,
                                "summary": result.summary,
                                "tokens_used": result.tokens_used,
                            },
                        },
                        f,
                        indent=2,
                    )

            return result

        except anthropic.APIError as e:
            return StepResult(
                step_id=step_id,
                status="failed",
                error=f"API error: {str(e)}",
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            return StepResult(
                step_id=step_id,
                status="failed",
                error=f"Execution error: {str(e)}",
                duration_seconds=time.time() - start_time,
            )

    def _build_user_message(self, step: dict, plan: dict, resolved_context: list[dict]) -> str:
        """Build user message from task, context, and plan context."""
        parts = []

        # Task description
        parts.append(f"Task: {step['task']}")

        # Resolved context
        if resolved_context:
            parts.append("\nContext:")
            for ctx in resolved_context:
                if "content" in ctx:
                    reason = ctx.get("reason", "")
                    parts.append(f"\n  [{ctx['type']}] {reason}:")
                    parts.append(f"  {ctx['content']}")

        # Plan-level context
        plan_ctx = plan.get("context_sources", [])
        if plan_ctx:
            plan_resolved = resolve_context_sources(plan_ctx, plan, Path(plan.get("_path", ".")))
            for ctx in plan_resolved:
                if "content" in ctx:
                    reason = ctx.get("reason", "")
                    parts.append(f"\n  [Plan {ctx['type']}] {reason}:")
                    parts.append(f"  {ctx['content']}")

        return "\n".join(parts)

    def _parse_response(self, response: Any, step_id: str) -> StepResult:
        """Parse Messages API response into StepResult."""
        result = StepResult(step_id=step_id, status="completed")

        # Extract content
        if response.content:
            result.summary = response.content[0].text if response.content[0].type == "text" else ""

        # Extract token usage
        if hasattr(response, "usage"):
            result.tokens_used = response.usage.output_tokens + response.usage.input_tokens

        # Try to extract structured output
        try:
            # Look for JSON in response text
            if result.summary:
                match = re.search(r'\{.*\}', result.summary, re.DOTALL)
                if match:
                    result.output = json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            result.output = {"summary": result.summary}

        return result


class BatchExecutor:
    """Handles wave-based execution via Batch API."""

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.api_key) if config.api_key else None

    def execute_wave(self, wave: list[dict], plan: dict, plan_path: Path, root: Path) -> list[StepResult]:
        """Execute a wave of steps via Batch API."""
        # Build batch requests
        requests = []
        step_map = {}

        for step in wave:
            step_id = step.get("id", "unknown")
            context_needed = step.get("context_needed", [])
            resolved_context = resolve_context_sources(context_needed, plan, root)

            # Build system prompt
            agent_name = step.get("agent", "@unknown").lstrip("@")
            agent_file = find_agent_file(agent_name, plan_path)
            if agent_file:
                system_prompt = extract_system_prompt(agent_file)
            else:
                system_prompt = f"You are {step.get('agent', 'an agent')}. Execute the following task."

            # Build user message
            user_message = self._build_user_message(step, plan, resolved_context)

            batch_request = {
                "custom_id": f"plan_{plan['plan_id']}_step_{step_id}",
                "params": {
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens_per_step,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                },
            }

            requests.append(batch_request)
            step_map[batch_request["custom_id"]] = step

        # Submit batch
        batch_id = self._submit_batch(requests)
        if not batch_id:
            return [
                StepResult(step_id=step["id"], status="failed", error="Failed to submit batch")
                for step in wave
            ]

        # Poll for completion
        batch_result = self._poll_batch(batch_id)
        if not batch_result:
            return [
                StepResult(step_id=step["id"], status="failed", error="Batch polling timed out")
                for step in wave
            ]

        # Collect results
        return self._collect_results(batch_result, plan, plan_path, step_map)

    def _submit_batch(self, requests: list[dict]) -> Optional[str]:
        """Submit batch to Anthropic Batch API."""
        try:
            batch = self.client.beta.messages.batches.create(requests=requests)
            return batch.id
        except Exception as e:
            print(f"  Error submitting batch: {e}")
            return None

    def _poll_batch(self, batch_id: str) -> Optional[dict]:
        """Poll batch for completion."""
        max_polls = 120  # 60 minutes with 30s interval
        poll_count = 0

        while poll_count < max_polls:
            try:
                batch = self.client.beta.messages.batches.retrieve(batch_id)

                if batch.processing_status == "ended":
                    return batch
                elif batch.processing_status == "failed":
                    print(f"  Batch failed: {batch.request_counts}")
                    return None

                if poll_count % 10 == 0:
                    print(f"    Polling batch {batch_id}... ({poll_count * self.config.poll_interval}s)")

                time.sleep(self.config.poll_interval)
                poll_count += 1

            except Exception as e:
                print(f"  Error polling batch: {e}")
                return None

        print(f"  Batch polling timed out after {max_polls * self.config.poll_interval}s")
        return None

    def _collect_results(self, batch: dict, plan: dict, plan_path: Path, step_map: dict) -> list[StepResult]:
        """Collect results from completed batch."""
        results = []

        try:
            # Retrieve results
            for result_data in self.client.beta.messages.batches.results(batch.id):
                custom_id = result_data.result.custom_id if hasattr(result_data, "result") else ""
                step = step_map.get(custom_id)

                if not step:
                    continue

                step_id = step.get("id", "unknown")
                result = StepResult(step_id=step_id, status="completed")

                # Extract response content
                if hasattr(result_data, "result") and hasattr(result_data.result, "message"):
                    message = result_data.result.message
                    if message.content:
                        result.summary = message.content[0].text if message.content[0].type == "text" else ""
                    if hasattr(message, "usage"):
                        result.tokens_used = message.usage.output_tokens + message.usage.input_tokens

                results.append(result)
                PlanUpdater.update_step(plan_path, step_id, result)
                PlanUpdater.update_token_budget(plan_path, result.tokens_used)

        except Exception as e:
            print(f"  Error collecting batch results: {e}")

        return results

    def _build_user_message(self, step: dict, plan: dict, resolved_context: list[dict]) -> str:
        """Build user message from task, context, and plan context."""
        parts = []
        parts.append(f"Task: {step['task']}")

        if resolved_context:
            parts.append("\nContext:")
            for ctx in resolved_context:
                if "content" in ctx:
                    reason = ctx.get("reason", "")
                    parts.append(f"\n  [{ctx['type']}] {reason}:")
                    parts.append(f"  {ctx['content']}")

        return "\n".join(parts)


class PlanExecutor:
    """Main execution orchestrator."""

    def __init__(self, plan_path: Path, config: ExecutionConfig):
        self.plan_path = plan_path
        self.config = config
        self.root = plan_path.parent.parent.parent.parent
        self.monitor = ProgressMonitor(config)

        # Load plan
        content = plan_path.read_text()
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        self.plan = json.loads(content)
        self.plan["_path"] = str(plan_path)

    def execute(self) -> int:
        """Main execution loop."""
        print(f"Plan: {self.plan.get('plan_id', 'unknown')}")
        print(f"Schema: v{self.plan.get('schema_version', '?')}")
        print(f"Mode: {self.config.model}")

        # Validate plan
        errors = validate_plan(self.plan)
        if errors:
            print(f"\nValidation failed ({len(errors)} errors):")
            for e in errors:
                print(f"  - {e}")
            return 1

        print("Validation passed")

        # Dry-run mode
        if self.config.dry_run:
            return self._dry_run()

        # Check API key for non-dry-run modes
        if not self.config.api_key:
            print("Error: ANTHROPIC_API_KEY environment variable not set")
            return 1

        # Resolve execution schedule
        waves = resolve_dependencies(self.plan.get("steps", []))

        # Execute waves
        all_results = []
        for wave_num, wave in enumerate(waves, 1):
            self.monitor.on_wave_start(wave_num, wave)

            # Check for approval requirement
            critical_steps = [s for s in wave if s.get("priority") in ("critical", "high")]
            if critical_steps and self.config.approval_required and not self.config.auto_approve:
                for step in critical_steps:
                    try:
                        if not self.monitor.on_approval_needed(step):
                            result = StepResult(step_id=step["id"], status="skipped")
                            self.monitor.on_step_complete(step, result)
                            all_results.append(result)
                            PlanUpdater.update_step(self.plan_path, step["id"], result)
                            continue
                    except KeyboardInterrupt:
                        return 1

            # Execute wave
            if self.config.mode == "batch":
                results = self._execute_batch_wave(wave)
            else:
                results = self._execute_sequential_wave(wave)

            for step, result in zip(wave, results):
                self.monitor.on_step_complete(step, result)
                all_results.append(result)

        # Summary
        self.monitor.display_summary(self.plan, all_results)
        PlanUpdater.mark_plan_complete(self.plan_path)

        return 0

    def _dry_run(self) -> int:
        """Dry-run mode: show execution schedule without executing."""
        print("\n[DRY-RUN MODE - No API calls will be made]")

        waves = resolve_dependencies(self.plan.get("steps", []))
        print(f"\nExecution schedule: {len(waves)} wave(s)")

        for wave_num, wave in enumerate(waves, 1):
            self.monitor.on_wave_start(wave_num, wave)

            # Show context
            for step in wave:
                context_needed = step.get("context_needed", [])
                if context_needed:
                    resolved = resolve_context_sources(context_needed, self.plan, self.root)
                    tokens = sum(r.get("tokens_est", 0) for r in resolved)
                    print(f"      Context: {len(context_needed)} source(s), ~{int(tokens)} tokens")

        return 0

    def _execute_sequential_wave(self, wave: list[dict]) -> list[StepResult]:
        """Execute wave sequentially via Messages API."""
        executor = StepExecutor(self.config)
        results = []

        for step in wave:
            self.monitor.on_step_start(step)
            result = executor.execute(step, self.plan, self.plan_path, self.root)
            results.append(result)

        return results

    def _execute_batch_wave(self, wave: list[dict]) -> list[StepResult]:
        """Execute wave via Batch API."""
        executor = BatchExecutor(self.config)
        return executor.execute_wave(wave, self.plan, self.plan_path, self.root)


def main():
    parser = argparse.ArgumentParser(
        description="Execute v2.0 plans with Messages API, Batch API, or dry-run",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("plan", help="Path to plan.json file")
    parser.add_argument(
        "--mode",
        choices=["sequential", "batch", "dry-run"],
        default="dry-run",
        help="Execution mode (default: dry-run)",
    )
    parser.add_argument("--validate", action="store_true", help="Validate plan only")
    parser.add_argument("--schedule", action="store_true", help="Show execution schedule")
    parser.add_argument("--auto-approve", action="store_true", help="Skip approval prompts")
    parser.add_argument("--context", action="store_true", help="Show resolved context")
    parser.add_argument("--step", help="Execute single specific step")
    parser.add_argument("--max-tokens", type=int, help="Override max tokens per step")
    parser.add_argument("--model", help="Override model (env: ANTHROPIC_MODEL)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--output-dir", help="Save step outputs to directory")
    parser.add_argument("--resume", action="store_true", help="Resume from last incomplete step")

    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"Error: Plan file not found: {plan_path}")
        return 1

    # Build config
    args.mode = getattr(args, 'mode', 'dry-run')
    config = ExecutionConfig.from_args_and_env(args)

    # Create executor
    executor = PlanExecutor(plan_path, config)

    # Handle modes
    if args.validate:
        errors = validate_plan(executor.plan)
        if errors:
            print(f"Validation failed ({len(errors)} errors):")
            for e in errors:
                print(f"  - {e}")
            return 1
        print("Validation passed")
        return 0

    if args.schedule or args.mode == "dry-run":
        return executor.execute()

    # Execute
    try:
        return executor.execute()
    except KeyboardInterrupt:
        print("\nExecution interrupted")
        return 1
    except Exception as e:
        print(f"Fatal error: {e}")
        if args.verbose:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
