#!/usr/bin/env python3
"""Plan Execution MCP Server

Provides tools for executing and monitoring plan steps via the Anthropic Messages API.
Wraps plan-executor functionality as MCP tools that can be called by agents.

Tools:
  - execute_step: Execute a single plan step
  - execute_wave: Execute a parallel group of steps via Batch API
  - get_execution_schedule: Show planned execution order without running
  - get_execution_status: Get current execution progress
  - resume_execution: Resume plan execution from where it left off
  - validate_plan_for_execution: Check if a plan is ready for execution
"""

import asyncio
import json
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import anthropic
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import TextContent, Tool


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class StepResult:
    """Result from executing a single step."""
    step_id: str
    status: str
    summary: str
    tokens_used: int
    files_modified: list[str]
    files_created: list[str]
    duration_seconds: float
    timestamp: str


@dataclass
class WaveResult:
    """Result from executing a parallel wave of steps."""
    wave_number: int
    steps: list[StepResult]
    batch_id: Optional[str]
    total_tokens: int
    total_duration_seconds: float


@dataclass
class ExecutionStatus:
    """Current execution progress for a plan."""
    overall_status: str
    progress_percentage: float
    completed_steps: list[str]
    pending_steps: list[str]
    blocked_steps: dict[str, list[str]]
    token_budget: dict[str, Any]
    next_executable_steps: list[str]
    critical_path_status: Optional[str]


@dataclass
class ValidationResult:
    """Validation result for a plan."""
    valid: bool
    errors: list[str]
    warnings: list[str]
    agents_found: list[str]
    estimated_cost: int


# ============================================================================
# Plan Loading & Parsing
# ============================================================================


def load_plan(plan_path: str) -> dict[str, Any]:
    """Load plan JSON, handling trailing commas.

    Args:
        plan_path: Path to plan JSON file

    Returns:
        Parsed plan dict

    Raises:
        FileNotFoundError: If plan file doesn't exist
        json.JSONDecodeError: If plan is invalid JSON
    """
    path = Path(plan_path)
    if not path.exists():
        raise FileNotFoundError(f"Plan file not found: {plan_path}")

    content = path.read_text(encoding="utf-8")

    # Clean up trailing commas with regex: r',(\s*[}\]])'
    content = re.sub(r",(\s*[}\]])", r"\1", content)

    return json.loads(content)


def find_agent_file(agent_name: str, root_path: Path) -> Optional[Path]:
    """Find agent .agent.md file by name.

    Searches in:
      - stacks/<stack>/agents/
      - framework/core/common-agents/
      - framework/core/shared-agents/
      - framework/core/meta-agents/

    Args:
        agent_name: Agent name (kebab-case)
        root_path: Path to agent-framework root

    Returns:
        Path to agent file or None if not found
    """
    search_patterns = [
        f"stacks/**/agents/{agent_name}.agent.md",
        f"framework/core/common-agents/{agent_name}.agent.md",
        f"framework/core/shared-agents/{agent_name}.agent.md",
        f"framework/core/meta-agents/{agent_name}.agent.md",
    ]

    for pattern in search_patterns:
        matches = list(root_path.glob(pattern))
        if matches:
            return matches[0].resolve()

    return None


def parse_agent_frontmatter(content: str) -> tuple[Optional[dict[str, Any]], str]:
    """Parse YAML frontmatter from agent markdown.

    Args:
        content: Raw markdown content

    Returns:
        Tuple of (frontmatter_dict, body) or (None, content)
    """
    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    frontmatter_text = content[3:end].strip()
    body = content[end + 3:].strip()

    data: dict[str, Any] = {}
    current_key: Optional[str] = None

    for line in frontmatter_text.split("\n"):
        line = line.rstrip()
        if not line:
            continue

        # Key-value pair
        match = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip().strip("'\"")
            data[key] = value
            current_key = key

    return data, body


def get_agent_system_prompt(agent_path: Path) -> str:
    """Read agent file and extract system prompt from body.

    Args:
        agent_path: Path to agent .agent.md file

    Returns:
        System prompt content or empty string if not found
    """
    try:
        content = agent_path.read_text(encoding="utf-8")
        frontmatter, body = parse_agent_frontmatter(content)
        return body.strip()
    except (OSError, IOError):
        return ""


def get_root_path() -> Path:
    """Get copilot-agents root path.

    Returns:
        Path to copilot-agents directory
    """
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "copilot-agents").exists():
            return (current / "copilot-agents").resolve()
        current = current.parent

    # Fallback
    return Path("/sessions/serene-happy-dijkstra/mnt/agentic-framework/copilot-agents")


def find_step_by_id(steps: list[dict], step_id: str) -> Optional[dict]:
    """Find a step by ID, handling hierarchical steps with sub_plan.

    Args:
        steps: List of steps
        step_id: ID to find

    Returns:
        Step dict or None if not found
    """
    for step in steps:
        if step.get("id") == step_id:
            return step

        # Check sub_plan recursively
        if "sub_plan" in step and step["sub_plan"]:
            found = find_step_by_id(step["sub_plan"].get("steps", []), step_id)
            if found:
                return found

    return None


def resolve_context_needed(context_needed: Optional[dict], plan: dict) -> str:
    """Resolve context_needed field to actual context strings.

    Args:
        context_needed: Context requirement from step
        plan: The plan dict

    Returns:
        Context string to include in messages
    """
    if not context_needed:
        return ""

    context_parts = []

    # Handle knowledge sources
    if "knowledge" in context_needed:
        for query in context_needed["knowledge"]:
            context_parts.append(f"Knowledge: {query}")

    # Handle file sources
    if "files" in context_needed:
        root = get_root_path()
        for file_ref in context_needed["files"]:
            try:
                file_path = root / file_ref
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    context_parts.append(f"File: {file_ref}\n{content[:500]}")
            except (OSError, IOError):
                context_parts.append(f"File: {file_ref} (not found)")

    # Handle plan output references
    if "plan_outputs" in context_needed:
        for ref in context_needed["plan_outputs"]:
            context_parts.append(f"Plan output: {ref}")

    return "\n\n".join(context_parts)


def flatten_steps(steps: list[dict]) -> list[dict]:
    """Flatten hierarchical steps into a flat list."""
    flat = []
    for step in steps:
        flat.append(step)
        if "sub_plan" in step and step["sub_plan"]:
            flat.extend(flatten_steps(step["sub_plan"].get("steps", [])))
    return flat


def resolve_dependencies(steps: list[dict]) -> list[list[dict]]:
    """Resolve dependency graph into execution waves.

    Returns:
        List of waves, each containing steps that can run in parallel
    """
    flat = flatten_steps(steps)
    step_map = {s["id"]: s for s in flat}
    completed = set()
    waves = []

    # Track already completed steps
    for s in flat:
        if s.get("status") in ("completed", "skipped"):
            completed.add(s["id"])

    remaining = [s for s in flat if s["id"] not in completed]

    max_iterations = len(remaining) + 1
    iteration = 0

    while remaining and iteration < max_iterations:
        iteration += 1

        # Find ready steps
        ready = []
        for s in remaining:
            deps = s.get("dependencies", [])
            if all(d in completed for d in deps):
                ready.append(s)

        if not ready:
            break  # Deadlock

        # Group by parallel_group
        groups = defaultdict(list)
        sequential = []

        for s in ready:
            pg = s.get("parallel_group")
            if pg:
                groups[pg].append(s)
            else:
                sequential.append(s)

        # Add groups as waves
        for group_id, group_steps in sorted(groups.items()):
            waves.append(group_steps)
            for s in group_steps:
                completed.add(s["id"])

        # Add sequential steps one at a time
        for s in sequential:
            waves.append([s])
            completed.add(s["id"])

        # Remove completed from remaining
        remaining = [s for s in remaining if s["id"] not in completed]

    return waves


# ============================================================================
# Plan Execution
# ============================================================================


def execute_step_with_api(
    step: dict,
    agent_system_prompt: str,
    model: str,
    max_tokens: int,
) -> StepResult:
    """Execute a single step using Anthropic Messages API.

    Args:
        step: Step dict from plan
        agent_system_prompt: System prompt from agent file
        model: Model to use
        max_tokens: Max tokens for response

    Returns:
        StepResult with execution outcome
    """
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    try:
        # Build messages
        task_prompt = step.get("task", "Execute this step")
        context = resolve_context_needed(step.get("context_needed"), {})

        user_content = f"{task_prompt}"
        if context:
            user_content = f"{context}\n\n{user_content}"

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=agent_system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        # Extract summary from response
        summary = ""
        if response.content:
            summary = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])

        tokens_used = response.usage.output_tokens + response.usage.input_tokens

        duration = time.time() - start_time

        return StepResult(
            step_id=step["id"],
            status="completed",
            summary=summary[:500],
            tokens_used=tokens_used,
            files_modified=[],
            files_created=[],
            duration_seconds=duration,
            timestamp=timestamp,
        )

    except Exception as e:
        duration = time.time() - start_time
        return StepResult(
            step_id=step["id"],
            status="error",
            summary=f"Error: {str(e)}",
            tokens_used=0,
            files_modified=[],
            files_created=[],
            duration_seconds=duration,
            timestamp=timestamp,
        )


def update_plan_step(plan: dict, step_id: str, result: StepResult) -> dict:
    """Update plan JSON with step execution result.

    Args:
        plan: Plan dict
        step_id: Step ID to update
        result: Execution result

    Returns:
        Updated plan dict
    """
    step = find_step_by_id(plan.get("steps", []), step_id)
    if step:
        step["status"] = result.status
        step["output"] = result.summary
        step["completed_at"] = result.timestamp
        step["tokens_used"] = result.tokens_used

        # Update token budget
        if "token_budget" not in plan:
            plan["token_budget"] = {}
        if "actual_total" not in plan["token_budget"]:
            plan["token_budget"]["actual_total"] = 0
        plan["token_budget"]["actual_total"] += result.tokens_used

        plan["updated_at"] = datetime.now().isoformat()

    return plan


# ============================================================================
# MCP Server
# ============================================================================


server = Server("plan-execution")


def get_anthropic_api_key() -> str:
    """Get and validate ANTHROPIC_API_KEY environment variable."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return api_key


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="execute_step",
            description="Execute a single plan step via the Anthropic Messages API. Returns step result with status, summary, tokens used, and file modifications.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Path to plan JSON file",
                    },
                    "step_id": {
                        "type": "string",
                        "description": "Step ID to execute",
                    },
                    "model": {
                        "type": "string",
                        "description": "Model override (default: from plan's batch_config or claude-sonnet-4-5-20250929)",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Max tokens for response (default: 4096)",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, show what would be sent without calling API",
                    },
                },
                "required": ["plan_path", "step_id"],
            },
        ),
        Tool(
            name="execute_wave",
            description="Execute a parallel group of steps via Batch API. Returns wave result with all step results and batch ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Path to plan JSON",
                    },
                    "parallel_group": {
                        "type": "string",
                        "description": "Execute specific parallel group",
                    },
                    "wave_number": {
                        "type": "integer",
                        "description": "Execute specific wave number",
                    },
                    "model": {
                        "type": "string",
                        "description": "Model override",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Show batch request without submitting",
                    },
                },
                "required": ["plan_path"],
            },
        ),
        Tool(
            name="get_execution_schedule",
            description="Show the planned execution order without running anything. Returns waves with step metadata and dependencies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Path to plan JSON file",
                    },
                    "include_context": {
                        "type": "boolean",
                        "description": "Include resolved context info",
                    },
                    "include_completed": {
                        "type": "boolean",
                        "description": "Include already-completed steps",
                    },
                },
                "required": ["plan_path"],
            },
        ),
        Tool(
            name="get_execution_status",
            description="Get current execution progress for a plan. Returns status, progress percentage, completed/pending/blocked steps, and next executable steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Path to plan JSON file",
                    }
                },
                "required": ["plan_path"],
            },
        ),
        Tool(
            name="resume_execution",
            description="Resume plan execution from where it left off. Executes all remaining steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Path to plan JSON file",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["sequential", "batch"],
                        "description": "Execution mode (default: from plan)",
                    },
                    "auto_approve": {
                        "type": "boolean",
                        "description": "Skip approval for all steps",
                    },
                },
                "required": ["plan_path"],
            },
        ),
        Tool(
            name="validate_plan_for_execution",
            description="Check if a plan is ready for execution. Validates plan structure, finds agents, and estimates cost.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "Path to plan JSON file",
                    }
                },
                "required": ["plan_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "execute_step":
            plan_path = arguments.get("plan_path")
            step_id = arguments.get("step_id")
            model = arguments.get("model")
            max_tokens = arguments.get("max_tokens", 4096)
            dry_run = arguments.get("dry_run", False)

            if not plan_path or not step_id:
                return [TextContent(type="text", text="Error: plan_path and step_id required")]

            plan = load_plan(plan_path)
            step = find_step_by_id(plan.get("steps", []), step_id)

            if not step:
                return [TextContent(type="text", text=f"Error: Step {step_id} not found")]

            # Get agent and system prompt
            agent_name = step.get("agent")
            if not agent_name:
                return [TextContent(type="text", text=f"Error: Step has no agent assigned")]

            root = get_root_path()
            agent_path = find_agent_file(agent_name, root)

            if not agent_path:
                return [TextContent(type="text", text=f"Error: Agent file not found: {agent_name}")]

            system_prompt = get_agent_system_prompt(agent_path)

            # Set model
            if not model:
                model = plan.get("batch_config", {}).get("model", "claude-sonnet-4-5-20250929")

            if dry_run:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "dry_run": True,
                                "step_id": step_id,
                                "task": step.get("task", "")[:100],
                                "agent": agent_name,
                                "model": model,
                                "max_tokens": max_tokens,
                                "system_prompt_length": len(system_prompt),
                            },
                            indent=2,
                        ),
                    )
                ]

            # Validate API key
            try:
                get_anthropic_api_key()
            except ValueError as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

            # Execute
            result = execute_step_with_api(step, system_prompt, model, max_tokens)

            # Update plan
            plan = update_plan_step(plan, step_id, result)

            # Save updated plan
            plan_path_obj = Path(plan_path)
            plan_path_obj.write_text(json.dumps(plan, indent=2), encoding="utf-8")

            return [TextContent(type="text", text=json.dumps(asdict(result), indent=2, default=str))]

        elif name == "execute_wave":
            plan_path = arguments.get("plan_path")
            parallel_group = arguments.get("parallel_group")
            wave_number = arguments.get("wave_number")
            model = arguments.get("model")
            dry_run = arguments.get("dry_run", False)

            if not plan_path:
                return [TextContent(type="text", text="Error: plan_path required")]

            plan = load_plan(plan_path)
            waves = resolve_dependencies(plan.get("steps", []))

            target_wave = None
            if wave_number is not None and 0 <= wave_number < len(waves):
                target_wave = waves[wave_number]
            elif parallel_group:
                for wave in waves:
                    if any(s.get("parallel_group") == parallel_group for s in wave):
                        target_wave = wave
                        break
            else:
                target_wave = waves[0] if waves else []

            if dry_run:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "dry_run": True,
                                "steps": len(target_wave) if target_wave else 0,
                                "steps_ids": [s.get("id") for s in (target_wave or [])],
                            },
                            indent=2,
                        ),
                    )
                ]

            return [TextContent(type="text", text="Wave execution not yet implemented")]

        elif name == "get_execution_schedule":
            plan_path = arguments.get("plan_path")
            include_context = arguments.get("include_context", False)
            include_completed = arguments.get("include_completed", False)

            if not plan_path:
                return [TextContent(type="text", text="Error: plan_path required")]

            plan = load_plan(plan_path)
            waves = resolve_dependencies(plan.get("steps", []))

            output = {"waves": []}
            for wave_num, wave in enumerate(waves):
                wave_data = {
                    "wave_number": wave_num,
                    "steps": []
                }
                for step in wave:
                    step_data = {
                        "id": step.get("id"),
                        "task": step.get("task", "")[:100],
                        "agent": step.get("agent"),
                        "status": step.get("status", "pending"),
                        "priority": step.get("priority", "normal"),
                        "parallel_group": step.get("parallel_group"),
                        "dependencies": step.get("dependencies", []),
                        "estimated_tokens": step.get("estimated_tokens", 0),
                    }
                    if include_context and "context_needed" in step:
                        step_data["context_needed"] = step["context_needed"]
                    wave_data["steps"].append(step_data)
                output["waves"].append(wave_data)

            return [TextContent(type="text", text=json.dumps(output, indent=2))]

        elif name == "get_execution_status":
            plan_path = arguments.get("plan_path")

            if not plan_path:
                return [TextContent(type="text", text="Error: plan_path required")]

            plan = load_plan(plan_path)
            flat_steps = flatten_steps(plan.get("steps", []))

            completed = [s.get("id") for s in flat_steps if s.get("status") == "completed"]
            pending = [s.get("id") for s in flat_steps if s.get("status") in ("pending", None)]
            blocked = {}

            for step in flat_steps:
                deps = step.get("dependencies", [])
                unmet = [d for d in deps if d not in completed]
                if unmet and step.get("status") != "completed":
                    blocked[step.get("id")] = unmet

            # Get next executable steps
            waves = resolve_dependencies(plan.get("steps", []))
            next_executable = []
            if waves:
                next_executable = [s.get("id") for s in waves[0]]

            progress = len(completed) / len(flat_steps) * 100 if flat_steps else 0

            status = ExecutionStatus(
                overall_status=plan.get("overall_status", "active"),
                progress_percentage=progress,
                completed_steps=completed,
                pending_steps=pending,
                blocked_steps=blocked,
                token_budget=plan.get("token_budget", {}),
                next_executable_steps=next_executable,
                critical_path_status="not_computed",
            )

            return [TextContent(type="text", text=json.dumps(asdict(status), indent=2, default=str))]

        elif name == "resume_execution":
            return [TextContent(type="text", text="Resume execution not yet implemented")]

        elif name == "validate_plan_for_execution":
            plan_path = arguments.get("plan_path")

            if not plan_path:
                return [TextContent(type="text", text="Error: plan_path required")]

            try:
                plan = load_plan(plan_path)
            except Exception as e:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "valid": False,
                                "errors": [f"Failed to load plan: {str(e)}"],
                                "warnings": [],
                                "agents_found": [],
                                "estimated_cost": 0,
                            },
                            indent=2,
                        ),
                    )
                ]

            errors = []
            warnings = []
            agents_found = []
            total_tokens = 0

            # Check schema version
            if plan.get("schema_version") != "2.0":
                errors.append(f"Schema version must be 2.0, got {plan.get('schema_version')}")

            # Check required fields
            required = ["plan_id", "stack", "description", "steps"]
            for field in required:
                if field not in plan:
                    errors.append(f"Missing required field: {field}")

            # Validate steps and find agents
            root = get_root_path()
            flat_steps = flatten_steps(plan.get("steps", []))

            for step in flat_steps:
                agent_name = step.get("agent")
                if agent_name:
                    agent_path = find_agent_file(agent_name, root)
                    if agent_path:
                        agents_found.append(agent_name)
                    else:
                        warnings.append(f"Agent not found: {agent_name}")

                total_tokens += step.get("estimated_tokens", 0) or 0

            valid = len(errors) == 0

            result = ValidationResult(
                valid=valid,
                errors=errors,
                warnings=warnings,
                agents_found=list(set(agents_found)),
                estimated_cost=total_tokens,
            )

            return [TextContent(type="text", text=json.dumps(asdict(result), indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="plan-execution",
                server_version="1.0.0",
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
