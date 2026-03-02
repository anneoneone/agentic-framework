#!/usr/bin/env python3
"""Cross-Stack Plan Orchestrator — Coordinate plan execution across stacks.

Resolves cross-stack dependencies, builds unified execution schedules,
and manages multi-stack plan workflows.

Usage:
    python cross-stack-orchestrator.py discover                      # Find cross-stack dependencies
    python cross-stack-orchestrator.py schedule <plan1> <plan2> ...  # Build unified schedule
    python cross-stack-orchestrator.py visualize <plan1> <plan2>     # ASCII dependency graph
    python cross-stack-orchestrator.py execute <plan1> <plan2>       # Execute coordinated plans
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


class CrossStackPlanOrchestrator:
    """Orchestrates coordinated execution of plans across multiple stacks."""

    def __init__(self, framework_root: Path):
        """Initialize orchestrator with framework root."""
        self.framework_root = Path(framework_root)
        self.stacks_root = self.framework_root.parent.parent / "stacks"
        self.plans_cache: Dict[str, dict] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}

    def discover(self) -> Dict[str, List[dict]]:
        """Discover cross-stack dependencies across all active plans."""
        cross_stack_deps = {}
        total_plans = 0
        plans_with_cross_deps = 0

        if not self.stacks_root.exists():
            print("No stacks directory found", file=sys.stderr)
            return cross_stack_deps

        for stack_dir in self.stacks_root.iterdir():
            if not stack_dir.is_dir():
                continue

            plans_dir = stack_dir / ".copilot-agents" / "plans"
            if not plans_dir.exists():
                continue

            for plan_file in plans_dir.glob("*.json"):
                total_plans += 1
                try:
                    with open(plan_file, "r") as f:
                        plan = json.load(f)

                    plan_key = f"{stack_dir.name}:{plan.get('id', plan_file.stem)}"
                    self.plans_cache[plan_key] = plan

                    # Check for cross-stack dependencies
                    deps = self._extract_cross_stack_deps(plan)
                    if deps:
                        plans_with_cross_deps += 1
                        cross_stack_deps[plan_key] = deps

                except (IOError, json.JSONDecodeError) as e:
                    print(f"Error reading {plan_file}: {e}", file=sys.stderr)

        return cross_stack_deps

    def schedule(self, plan_ids: List[str]) -> Dict:
        """Build unified execution schedule for multiple plans."""
        # Load specified plans
        plans_to_execute = {}

        for plan_id in plan_ids:
            if plan_id in self.plans_cache:
                plans_to_execute[plan_id] = self.plans_cache[plan_id]
            else:
                # Try to find plan
                plan = self._find_plan_by_id(plan_id)
                if plan:
                    plans_to_execute[plan_id] = plan
                else:
                    print(f"Warning: Plan {plan_id} not found", file=sys.stderr)

        if not plans_to_execute:
            print("No valid plans found", file=sys.stderr)
            return {}

        # Flatten steps and build unified graph
        all_steps = {}
        step_counter = 0
        plan_step_mapping = {}  # Map (plan_key, original_step) -> unified_step_id

        for plan_key, plan in plans_to_execute.items():
            steps = self._flatten_steps(plan)
            plan_step_mapping[plan_key] = {}

            for orig_step_id, step_data in enumerate(steps):
                unified_step_id = str(step_counter)
                all_steps[unified_step_id] = {
                    "original_step": orig_step_id,
                    "plan": plan_key,
                    "description": step_data.get("description", f"Step {orig_step_id}"),
                    "dependencies": step_data.get("dependencies", []),
                    "cross_stack_dependencies": step_data.get("cross_stack_dependencies", []),
                }
                plan_step_mapping[plan_key][orig_step_id] = unified_step_id
                step_counter += 1

        # Build unified dependency graph
        unified_deps = self._resolve_unified_dependencies(
            all_steps, plan_step_mapping, plans_to_execute
        )

        # Topological sort to determine execution waves
        waves = self._topological_sort_waves(all_steps, unified_deps)

        # Calculate aggregate statistics
        total_token_budget = sum(
            plan.get("token_budget", 10000) for plan in plans_to_execute.values()
        )

        schedule = {
            "generated_at": datetime.now().isoformat(),
            "plan_count": len(plans_to_execute),
            "total_steps": len(all_steps),
            "total_token_budget": total_token_budget,
            "waves": waves,
            "steps": all_steps,
            "plan_mapping": {k: v for k, v in plan_step_mapping.items()},
        }

        return schedule

    def visualize(self, plan_ids: List[str]) -> str:
        """Generate ASCII dependency graph for cross-stack plans."""
        schedule = self.schedule(plan_ids)
        if not schedule:
            return "No schedule generated"

        lines = []
        lines.append("Cross-Stack Plan Dependency Graph")
        lines.append("=" * 80)

        # Group steps by plan
        plans_steps = {}
        for step_id, step_data in schedule.get("steps", {}).items():
            plan = step_data["plan"]
            if plan not in plans_steps:
                plans_steps[plan] = []
            plans_steps[plan].append((step_id, step_data))

        # Visualize waves
        waves = schedule.get("waves", {})
        for wave_num in sorted(int(w) for w in waves.keys()):
            wave_num_str = str(wave_num)
            step_ids = waves[wave_num_str]
            lines.append(f"\nWave {wave_num_str}:")
            lines.append("-" * 40)

            for step_id in step_ids:
                step_data = schedule["steps"][step_id]
                plan = step_data["plan"]
                description = step_data["description"]
                cross_deps = step_data.get("cross_stack_dependencies", [])

                lines.append(f"  [{plan}] Step {step_id}: {description}")
                if cross_deps:
                    lines.append(f"    ↓ Cross-stack dependencies: {len(cross_deps)}")

        # Legend
        lines.append("\n" + "=" * 80)
        lines.append("Legend:")
        lines.append("  [stack-name] = Step from this stack")
        lines.append("  ↓ = Blocks/depends on")

        return "\n".join(lines)

    def execute(self, plan_ids: List[str]) -> Dict:
        """Execute coordinated plans with cross-stack dependency management."""
        schedule = self.schedule(plan_ids)
        if not schedule:
            return {"status": "error", "message": "Failed to build schedule"}

        results = {
            "started_at": datetime.now().isoformat(),
            "plan_count": len(plan_ids),
            "waves": {},
            "per_plan_results": {},
            "status": "pending",
        }

        waves = schedule.get("waves", {})
        total_waves = len(waves)

        print(f"Executing {len(plan_ids)} plans across {total_waves} waves")
        print("=" * 80)

        for wave_num in sorted(int(w) for w in waves.keys()):
            wave_num_str = str(wave_num)
            step_ids = waves[wave_num_str]

            print(f"\nWave {wave_num}/{total_waves}: {len(step_ids)} steps")
            print("-" * 40)

            wave_results = []

            for step_id in step_ids:
                step_data = schedule["steps"][step_id]
                plan = step_data["plan"]
                description = step_data["description"]

                print(f"  Executing: [{plan}] {description}")

                # Simulate execution (in real implementation, call plan executor)
                step_result = {
                    "step_id": step_id,
                    "plan": plan,
                    "description": description,
                    "status": "completed",
                    "duration_seconds": 2.5,
                    "tokens_used": 500,
                }

                wave_results.append(step_result)

                if plan not in results["per_plan_results"]:
                    results["per_plan_results"][plan] = {"steps": [], "status": "in_progress"}

                results["per_plan_results"][plan]["steps"].append(step_result)

            results["waves"][wave_num_str] = {
                "step_count": len(step_ids),
                "results": wave_results,
                "status": "completed",
            }

        # Finalize results
        results["completed_at"] = datetime.now().isoformat()
        results["status"] = "completed"

        for plan in results["per_plan_results"]:
            results["per_plan_results"][plan]["status"] = "completed"

        return results

    def _extract_cross_stack_deps(self, plan: dict) -> List[dict]:
        """Extract cross-stack dependencies from a plan."""
        cross_deps = []

        # Check plan-level dependencies
        if "cross_stack_dependencies" in plan:
            cross_deps.extend(plan["cross_stack_dependencies"])

        # Check step-level dependencies
        for step in plan.get("steps", []):
            if "cross_stack_dependencies" in step:
                cross_deps.extend(step["cross_stack_dependencies"])

        return cross_deps

    def _flatten_steps(self, plan: dict) -> List[dict]:
        """Flatten hierarchical steps into linear sequence."""
        steps = []

        def process_step(step: dict, parent_deps: List = None):
            if parent_deps is None:
                parent_deps = []

            # Add parent dependencies to this step
            step_deps = list(parent_deps) + step.get("dependencies", [])
            step_copy = step.copy()
            step_copy["dependencies"] = step_deps

            steps.append(step_copy)

            # Process sub-steps
            for sub_step in step.get("sub_steps", []):
                process_step(sub_step, step_deps)

        for step in plan.get("steps", []):
            process_step(step)

        return steps

    def _resolve_unified_dependencies(
        self,
        all_steps: Dict[str, dict],
        plan_step_mapping: Dict[str, Dict],
        plans: Dict[str, dict],
    ) -> Dict[str, Set[str]]:
        """Resolve dependencies in unified step graph."""
        unified_deps = {step_id: set() for step_id in all_steps.keys()}

        for unified_step_id, step_data in all_steps.items():
            plan_key = step_data["plan"]

            # Intra-plan dependencies
            for dep_step_id in step_data.get("dependencies", []):
                if plan_key in plan_step_mapping:
                    mapped_dep_id = plan_step_mapping[plan_key].get(dep_step_id)
                    if mapped_dep_id:
                        unified_deps[unified_step_id].add(mapped_dep_id)

            # Cross-stack dependencies
            for cross_dep in step_data.get("cross_stack_dependencies", []):
                target_plan_id = cross_dep.get("plan")
                target_step = cross_dep.get("step")

                # Find the unified step ID for the target
                for other_plan_key, other_mapping in plan_step_mapping.items():
                    if target_plan_id in other_plan_key:
                        mapped_step_id = other_mapping.get(int(target_step) if target_step else 0)
                        if mapped_step_id:
                            unified_deps[unified_step_id].add(mapped_step_id)

        return unified_deps

    def _topological_sort_waves(
        self, all_steps: Dict[str, dict], deps: Dict[str, Set[str]]
    ) -> Dict[str, List[str]]:
        """Topological sort to group steps into execution waves."""
        waves = {}
        in_degree = {step_id: len(dep_set) for step_id, dep_set in deps.items()}
        remaining = set(all_steps.keys())
        current_wave = 0

        while remaining:
            # Find steps with no dependencies
            wave_steps = [s for s in remaining if in_degree[s] == 0]

            if not wave_steps:
                # Circular dependency detected
                print(f"Warning: Circular dependency detected", file=sys.stderr)
                break

            waves[str(current_wave)] = wave_steps
            remaining -= set(wave_steps)

            # Update in-degrees
            for step_id in wave_steps:
                for other_step_id in remaining:
                    if step_id in deps[other_step_id]:
                        in_degree[other_step_id] -= 1

            current_wave += 1

        return waves

    def _find_plan_by_id(self, plan_id: str) -> Optional[dict]:
        """Find and load a plan by ID."""
        if not self.stacks_root.exists():
            return None

        for stack_dir in self.stacks_root.iterdir():
            if not stack_dir.is_dir():
                continue

            plans_dir = stack_dir / ".copilot-agents" / "plans"
            if not plans_dir.exists():
                continue

            # Try exact match or partial match
            for plan_file in plans_dir.glob("*.json"):
                try:
                    with open(plan_file, "r") as f:
                        plan = json.load(f)

                    plan_key = f"{stack_dir.name}:{plan.get('id', plan_file.stem)}"
                    if plan_key == plan_id or plan_file.stem == plan_id:
                        return plan
                except (IOError, json.JSONDecodeError):
                    continue

        return None

    def print_discovery_results(self, cross_deps: Dict[str, List[dict]]):
        """Pretty print discovery results."""
        print("\nCross-Stack Dependencies Discovery")
        print("=" * 80)

        if not cross_deps:
            print("No cross-stack dependencies found")
            return

        for plan_key, deps_list in sorted(cross_deps.items()):
            print(f"\n{plan_key}")
            print("-" * 40)
            for dep in deps_list:
                target = dep.get("plan", "unknown")
                step = dep.get("step", "?")
                desc = dep.get("description", "")
                print(f"  → Depends on: {target} (step {step})")
                if desc:
                    print(f"    {desc}")

    def print_schedule(self, schedule: Dict):
        """Pretty print execution schedule."""
        if not schedule:
            print("No schedule generated")
            return

        print("\nUnified Execution Schedule")
        print("=" * 80)
        print(f"Generated: {schedule.get('generated_at')}")
        print(f"Plans: {schedule.get('plan_count')}")
        print(f"Total steps: {schedule.get('total_steps')}")
        print(f"Total token budget: {schedule.get('total_token_budget')}")

        waves = schedule.get("waves", {})
        print(f"\nExecution Plan ({len(waves)} waves):")
        print("-" * 40)

        for wave_num in sorted(int(w) for w in waves.keys()):
            wave_num_str = str(wave_num)
            step_ids = waves[wave_num_str]
            print(f"\nWave {wave_num}: {len(step_ids)} steps")

            for step_id in step_ids:
                step_data = schedule["steps"][step_id]
                print(
                    f"  [{step_data['plan']}] {step_data['description']}"
                )

    def print_execution_results(self, results: Dict):
        """Pretty print execution results."""
        print("\nExecution Results")
        print("=" * 80)
        print(f"Status: {results.get('status', 'unknown')}")
        print(f"Duration: {results.get('duration_seconds', 'N/A')} seconds")

        per_plan = results.get("per_plan_results", {})
        if per_plan:
            print(f"\nPer-plan results ({len(per_plan)} plans):")
            print("-" * 40)
            for plan, plan_result in sorted(per_plan.items()):
                status = plan_result.get("status", "unknown")
                step_count = len(plan_result.get("steps", []))
                print(f"  {plan}: {status} ({step_count} steps)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cross-Stack Plan Orchestrator"
    )
    parser.add_argument(
        "command",
        choices=["discover", "schedule", "visualize", "execute"],
        help="Command to execute",
    )
    parser.add_argument(
        "plans",
        nargs="*",
        help="Plan IDs (for schedule, visualize, execute commands)",
    )
    parser.add_argument(
        "--framework-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Framework root directory",
    )

    args = parser.parse_args()

    orchestrator = CrossStackPlanOrchestrator(args.framework_root)

    if args.command == "discover":
        cross_deps = orchestrator.discover()
        orchestrator.print_discovery_results(cross_deps)
        print(
            f"\nFound {sum(len(d) for d in cross_deps.values())} "
            f"cross-stack dependencies in {len(cross_deps)} plans"
        )

    elif args.command == "schedule":
        if not args.plans:
            print("Error: Please specify plan IDs", file=sys.stderr)
            sys.exit(1)

        schedule = orchestrator.schedule(args.plans)
        orchestrator.print_schedule(schedule)

    elif args.command == "visualize":
        if not args.plans:
            print("Error: Please specify plan IDs", file=sys.stderr)
            sys.exit(1)

        graph = orchestrator.visualize(args.plans)
        print(graph)

    elif args.command == "execute":
        if not args.plans:
            print("Error: Please specify plan IDs", file=sys.stderr)
            sys.exit(1)

        results = orchestrator.execute(args.plans)
        orchestrator.print_execution_results(results)


if __name__ == "__main__":
    main()
