#!/usr/bin/env python3
"""Token Telemetry — Collect and report token usage across plan executions.

Usage:
    python token-telemetry.py collect                     # Scan stacks/*/plans/, update telemetry DB
    python token-telemetry.py report [--format text|json]  # Generate usage report
    python token-telemetry.py dashboard                    # Show compact key metrics + sparkline
    python token-telemetry.py agent-stats [--agent @name]  # Per-agent statistics
    python token-telemetry.py budget-accuracy               # Estimated vs actual comparison

Telemetry is stored in framework/telemetry/token-usage.jsonl (one JSON object per line).
Records are deduplicated on (plan_id, step_id).
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent.parent.parent.resolve()


class TokenTelemetry:
    """Token telemetry collection and reporting system."""

    def __init__(self, root: Path | None = None):
        self.root = root or ROOT
        self.telemetry_dir = self.root / "framework" / "telemetry"
        self.db_path = self.telemetry_dir / "token-usage.jsonl"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_telemetry_db(self) -> list[dict[str, Any]]:
        """Load all records from the JSONL telemetry database."""
        records: list[dict[str, Any]] = []
        if not self.db_path.exists():
            return records
        with open(self.db_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def save_telemetry_record(self, record: dict[str, Any]) -> None:
        """Append a single telemetry record to the JSONL database."""
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "a") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    # ------------------------------------------------------------------
    # Plan scanning
    # ------------------------------------------------------------------

    def scan_plans(self) -> list[Path]:
        """Find all plan JSON files under ``stacks/*/plans/``."""
        stacks_dir = self.root / "stacks"
        if not stacks_dir.exists():
            return []
        return sorted(stacks_dir.glob("*/plans/*.json"))

    @staticmethod
    def _clean_json(content: str) -> str:
        """Remove trailing commas that break ``json.loads``."""
        return re.sub(r",(\s*[}\]])", r"\1", content)

    def _extract_steps(
        self,
        steps: list[dict[str, Any]],
        plan_id: str,
        stack: str,
        timestamp: str,
    ) -> list[dict[str, Any]]:
        """Recursively extract telemetry records from plan steps (handles sub_plan)."""
        records: list[dict[str, Any]] = []
        for step in steps:
            output = step.get("output") or {}
            if "tokens_used" in output:
                records.append(
                    {
                        "timestamp": timestamp,
                        "plan_id": plan_id,
                        "stack": stack,
                        "step_id": step.get("id", "unknown"),
                        "agent": step.get("agent", "unknown"),
                        "estimated_tokens": step.get("estimated_tokens"),
                        "actual_tokens": output.get("tokens_used"),
                        "duration_seconds": output.get("duration_seconds"),
                        "status": step.get("status", "unknown"),
                    }
                )
            # Recurse into sub-plans
            sub_plan = step.get("sub_plan")
            if sub_plan and "steps" in sub_plan:
                records.extend(
                    self._extract_steps(sub_plan["steps"], plan_id, stack, timestamp)
                )
        return records

    def extract_step_telemetry(self, plan_path: Path) -> list[dict[str, Any]]:
        """Extract token-usage telemetry records from a single plan file."""
        try:
            content = plan_path.read_text()
            content = self._clean_json(content)
            plan = json.loads(content)
        except (json.JSONDecodeError, OSError):
            return []

        plan_id = plan.get("plan_id", plan.get("id", plan_path.stem))
        stack = plan.get("stack", "unknown")
        timestamp = plan.get("created_at", plan.get("timestamp", datetime.now().isoformat()))

        return self._extract_steps(plan.get("steps", []), plan_id, stack, timestamp)

    # ------------------------------------------------------------------
    # Collect
    # ------------------------------------------------------------------

    def collect(self) -> tuple[int, int]:
        """Scan all plan files and append new telemetry records.

        Returns:
            (new_records_added, total_plans_scanned)
        """
        plans = self.scan_plans()
        existing = self.load_telemetry_db()
        existing_keys: set[tuple[str, str]] = {
            (r["plan_id"], r["step_id"]) for r in existing
        }

        new_count = 0
        for plan_path in plans:
            for record in self.extract_step_telemetry(plan_path):
                key = (record["plan_id"], record["step_id"])
                if key not in existing_keys:
                    self.save_telemetry_record(record)
                    existing_keys.add(key)
                    new_count += 1

        return new_count, len(plans)

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_tokens(n: int | None) -> str:
        if n is None:
            return "N/A"
        return f"{n:,}"

    @staticmethod
    def render_sparkline(values: list[float]) -> str:
        """Return a unicode sparkline for *values*."""
        if not values:
            return ""
        chars = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
        lo, hi = min(values), max(values)
        if lo == hi:
            return chars[4] * len(values)
        rng = hi - lo
        return "".join(
            chars[min(int((v - lo) / rng * (len(chars) - 1)), len(chars) - 1)]
            for v in values
        )

    # ------------------------------------------------------------------
    # Budget accuracy helper
    # ------------------------------------------------------------------

    @staticmethod
    def _budget_accuracy(records: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute budget-accuracy metrics from telemetry records."""
        step_accs: list[float] = []
        by_agent: dict[str, list[float]] = defaultdict(list)

        for r in records:
            est = r.get("estimated_tokens")
            act = r.get("actual_tokens")
            if est and act:
                pct = (act / est) * 100
                step_accs.append(pct)
                by_agent[r["agent"]].append(pct)

        return {
            "overall": (sum(step_accs) / len(step_accs)) if step_accs else 0.0,
            "by_agent": {
                agent: sum(vals) / len(vals) for agent, vals in by_agent.items()
            },
        }

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def report(self, output_format: str = "text") -> str:
        """Generate a full usage report (text or JSON)."""
        records = self.load_telemetry_db()
        if not records:
            return "No telemetry data available."

        total_tokens = sum(r.get("actual_tokens", 0) for r in records if r.get("actual_tokens"))

        tokens_by_stack: dict[str, int] = defaultdict(int)
        tokens_by_agent: dict[str, int] = defaultdict(int)
        steps_by_agent: dict[str, int] = defaultdict(int)
        tokens_by_plan: dict[str, int] = defaultdict(int)

        for r in records:
            act = r.get("actual_tokens")
            if act:
                tokens_by_stack[r["stack"]] += act
                tokens_by_agent[r["agent"]] += act
                steps_by_agent[r["agent"]] += 1
                tokens_by_plan[r["plan_id"]] += act

        top_plans = sorted(tokens_by_plan.items(), key=lambda x: x[1], reverse=True)[:5]

        valid = [r for r in records if r.get("actual_tokens")]
        avg_tokens = (sum(r["actual_tokens"] for r in valid) / len(valid)) if valid else 0

        accuracy = self._budget_accuracy(records)

        if output_format == "json":
            return json.dumps(
                {
                    "total_tokens": total_tokens,
                    "records_count": len(records),
                    "tokens_by_stack": dict(tokens_by_stack),
                    "tokens_by_agent": dict(tokens_by_agent),
                    "steps_by_agent": dict(steps_by_agent),
                    "avg_tokens_per_step": avg_tokens,
                    "top_plans": [
                        {"plan_id": pid, "tokens": t} for pid, t in top_plans
                    ],
                    "budget_accuracy": {
                        "overall_percent": accuracy["overall"],
                        "by_agent": accuracy["by_agent"],
                    },
                },
                indent=2,
            )

        lines: list[str] = []
        lines.append("TOKEN USAGE REPORT")
        lines.append("=" * 50)
        lines.append(f"Total tokens: {self.format_tokens(total_tokens)}")
        lines.append(f"Records: {len(records)}")
        lines.append(f"Average per step: {self.format_tokens(int(avg_tokens))}")
        lines.append("")

        lines.append("TOKENS BY STACK:")
        for stack in sorted(tokens_by_stack):
            lines.append(f"  {stack}: {self.format_tokens(tokens_by_stack[stack])}")
        lines.append("")

        lines.append("TOP AGENTS BY TOKEN USAGE:")
        sorted_agents = sorted(tokens_by_agent.items(), key=lambda x: x[1], reverse=True)
        for agent, tokens in sorted_agents[:10]:
            steps = steps_by_agent[agent]
            avg = tokens // steps if steps else 0
            lines.append(
                f"  {agent}: {self.format_tokens(tokens)} "
                f"({steps} steps, avg {self.format_tokens(avg)}/step)"
            )
        lines.append("")

        lines.append("TOP 5 MOST EXPENSIVE PLANS:")
        for plan_id, tokens in top_plans:
            lines.append(f"  {plan_id}: {self.format_tokens(tokens)}")
        lines.append("")

        lines.append("BUDGET ACCURACY:")
        lines.append(f"  Overall: {accuracy['overall']:.1f}%")
        if accuracy["by_agent"]:
            lines.append("  By agent (top 5):")
            sorted_acc = sorted(accuracy["by_agent"].items(), key=lambda x: x[1], reverse=True)
            for agent, pct in sorted_acc[:5]:
                lines.append(f"    {agent}: {pct:.1f}%")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def dashboard(self) -> str:
        """Compact dashboard: key metrics + sparkline."""
        records = self.load_telemetry_db()
        if not records:
            return "No telemetry data available."

        total_tokens = sum(r.get("actual_tokens", 0) for r in records if r.get("actual_tokens"))
        unique_plans = len({r["plan_id"] for r in records})

        tokens_by_agent: dict[str, int] = defaultdict(int)
        steps_by_agent: dict[str, int] = defaultdict(int)
        for r in records:
            act = r.get("actual_tokens")
            if act:
                tokens_by_agent[r["agent"]] += act
                steps_by_agent[r["agent"]] += 1

        accuracy = self._budget_accuracy(records)

        # Trend sparkline from last 7 plans
        plans_ordered = sorted({r["plan_id"] for r in records})[-7:]
        plan_tokens = [
            sum(r["actual_tokens"] for r in records if r["plan_id"] == pid and r.get("actual_tokens"))
            for pid in plans_ordered
        ]

        lines: list[str] = []
        lines.append("")
        lines.append("TOKEN TELEMETRY DASHBOARD")
        lines.append("\u2550" * 50)
        lines.append(f"Total tokens: {self.format_tokens(total_tokens)}")
        lines.append(f"Plans analyzed: {unique_plans}")
        lines.append(f"Steps executed: {len(records)}")
        lines.append("")

        lines.append("TOP AGENTS BY TOKEN USAGE:")
        sorted_agents = sorted(tokens_by_agent.items(), key=lambda x: x[1], reverse=True)
        for agent, tokens in sorted_agents[:5]:
            steps = steps_by_agent[agent]
            avg = tokens // steps if steps else 0
            lines.append(
                f"  {agent:.<35} {self.format_tokens(tokens):>8} tokens "
                f"(avg {self.format_tokens(avg)}/step)"
            )
        lines.append("")

        lines.append("BUDGET ACCURACY:")
        lines.append(f"  Overall: {accuracy['overall']:.0f}% (estimated vs actual)")
        if accuracy["by_agent"]:
            sorted_acc = sorted(accuracy["by_agent"].items(), key=lambda x: x[1], reverse=True)
            lines.append(f"  Best:  {sorted_acc[0][0]} at {sorted_acc[0][1]:.0f}%")
            lines.append(f"  Worst: {sorted_acc[-1][0]} at {sorted_acc[-1][1]:.0f}%")
        lines.append("")

        if plan_tokens:
            lines.append(f"TREND (last {len(plans_ordered)} plans):")
            lines.append(f"  {self.render_sparkline(plan_tokens)}")
            trend_avg = sum(plan_tokens) / len(plan_tokens)
            lines.append(f"  Average: {self.format_tokens(int(trend_avg))} tokens/plan")

        lines.append("\u2550" * 50)
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Agent stats
    # ------------------------------------------------------------------

    def agent_stats(self, agent_name: str | None = None) -> str:
        """Per-agent token usage, success rate, avg duration.

        If *agent_name* is given, show detailed breakdown for that agent.
        """
        records = self.load_telemetry_db()
        if not records:
            return "No telemetry data available."

        stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "total_tokens": 0,
                "total_steps": 0,
                "completed": 0,
                "failed": 0,
                "skipped": 0,
                "total_duration": 0.0,
                "steps": [],
            }
        )

        for r in records:
            agent = r["agent"]
            if r.get("actual_tokens"):
                stats[agent]["total_tokens"] += r["actual_tokens"]
            stats[agent]["total_steps"] += 1

            status = r.get("status", "unknown")
            if status == "completed":
                stats[agent]["completed"] += 1
            elif status in ("failed", "blocked"):
                stats[agent]["failed"] += 1
            elif status == "skipped":
                stats[agent]["skipped"] += 1

            dur = r.get("duration_seconds")
            if dur:
                stats[agent]["total_duration"] += dur

            stats[agent]["steps"].append(r)

        lines: list[str] = []
        lines.append("")
        lines.append("PER-AGENT STATISTICS")
        lines.append("=" * 70)

        if agent_name:
            if agent_name not in stats:
                return f"Agent {agent_name} not found in telemetry data."
            s = stats[agent_name]
            n = s["total_steps"]
            sr = (s["completed"] / n * 100) if n else 0
            avg_dur = (s["total_duration"] / n) if n else 0
            avg_tok = (s["total_tokens"] // n) if n else 0

            lines.append(f"\nAgent: {agent_name}")
            lines.append(f"  Total invocations: {n}")
            lines.append(f"  Total tokens: {self.format_tokens(s['total_tokens'])}")
            lines.append(f"  Average tokens/step: {self.format_tokens(avg_tok)}")
            lines.append(
                f"  Success rate: {sr:.1f}% "
                f"({s['completed']} completed, {s['failed']} failed, {s['skipped']} skipped)"
            )
            lines.append(f"  Average duration: {avg_dur:.2f}s")
            lines.append("")
            lines.append("  Recent steps:")
            for step in s["steps"][-10:]:
                tok = self.format_tokens(step.get("actual_tokens"))
                lines.append(
                    f"    {step['plan_id']} / {step['step_id']}: "
                    f"{tok} tokens ({step.get('status', 'unknown')})"
                )
        else:
            sorted_agents = sorted(stats.items(), key=lambda x: x[1]["total_tokens"], reverse=True)
            for agent, s in sorted_agents[:15]:
                n = s["total_steps"]
                avg_tok = (s["total_tokens"] // n) if n else 0
                sr = (s["completed"] / n * 100) if n else 0
                avg_dur = (s["total_duration"] / n) if n else 0
                lines.append(f"\n{agent}")
                lines.append(
                    f"  Invocations: {n} | Total tokens: {self.format_tokens(s['total_tokens'])} "
                    f"| Avg: {self.format_tokens(avg_tok)}"
                )
                lines.append(f"  Success: {sr:.0f}% | Avg duration: {avg_dur:.2f}s")

        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Budget accuracy
    # ------------------------------------------------------------------

    def budget_accuracy_report(self) -> str:
        """Estimated vs actual comparison per agent with recommendations."""
        records = self.load_telemetry_db()
        if not records:
            return "No telemetry data available."

        step_data = [
            r for r in records if r.get("estimated_tokens") and r.get("actual_tokens")
        ]
        if not step_data:
            return "No step-level budget data available (need both estimated_tokens and actual_tokens)."

        agent_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in step_data:
            pct = (r["actual_tokens"] / r["estimated_tokens"]) * 100
            agent_data[r["agent"]].append(
                {
                    "accuracy": pct,
                    "difference": r["actual_tokens"] - r["estimated_tokens"],
                    "plan_id": r["plan_id"],
                }
            )

        lines: list[str] = []
        lines.append("")
        lines.append("BUDGET ACCURACY ANALYSIS")
        lines.append("=" * 70)

        for agent in sorted(agent_data):
            entries = agent_data[agent]
            accs = [e["accuracy"] for e in entries]
            diffs = [e["difference"] for e in entries]
            avg_acc = sum(accs) / len(accs)
            avg_diff = sum(diffs) / len(diffs)
            over = sum(1 for d in diffs if d < 0)
            under = sum(1 for d in diffs if d > 0)

            lines.append(f"\n{agent}")
            lines.append(f"  Samples: {len(entries)}")
            lines.append(f"  Accuracy: {avg_acc:.1f}% (actual / estimated)")
            lines.append(f"  Avg difference: {int(avg_diff):+,} tokens")
            lines.append(f"  Overestimated: {over} | Underestimated: {under}")

            if avg_diff < 0:
                lines.append(
                    f"  Recommendation: Reduce estimate by ~{abs(int(avg_diff)):,} tokens"
                )
            elif avg_diff > 0:
                lines.append(
                    f"  Recommendation: Increase estimate by ~{int(avg_diff):,} tokens"
                )
            else:
                lines.append("  Recommendation: Estimates are on target")

        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Token telemetry collection and reporting for the agent framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # collect
    subparsers.add_parser("collect", help="Scan stacks/*/plans/ and update telemetry DB")

    # report
    report_p = subparsers.add_parser("report", help="Generate token-usage report")
    report_p.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format (default: text)"
    )

    # dashboard
    subparsers.add_parser("dashboard", help="Show compact key-metrics dashboard with sparkline")

    # agent-stats
    agent_p = subparsers.add_parser("agent-stats", help="Per-agent statistics")
    agent_p.add_argument("--agent", default=None, help="Show detailed stats for a specific agent (e.g. @vue-frontend)")

    # budget-accuracy
    subparsers.add_parser("budget-accuracy", help="Estimated vs actual budget comparison")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    telemetry = TokenTelemetry()

    try:
        if args.command == "collect":
            new, total = telemetry.collect()
            print(f"Scanned {total} plan(s), added {new} new telemetry record(s).")
            return 0

        if args.command == "report":
            print(telemetry.report(output_format=args.format))
            return 0

        if args.command == "dashboard":
            print(telemetry.dashboard())
            return 0

        if args.command == "agent-stats":
            print(telemetry.agent_stats(agent_name=args.agent))
            return 0

        if args.command == "budget-accuracy":
            print(telemetry.budget_accuracy_report())
            return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
