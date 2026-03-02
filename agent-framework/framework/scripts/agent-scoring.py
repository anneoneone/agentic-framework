#!/usr/bin/env python3
"""Agent Performance Scoring — Track success rates, token efficiency, and task patterns.

Usage:
    python agent-scoring.py collect <plans_dir>         # Scan plans, build performance DB
    python agent-scoring.py report                      # Show performance report
    python agent-scoring.py leaderboard                 # Ranked agent leaderboard
    python agent-scoring.py agent <@name>               # Detailed agent profile
    python agent-scoring.py recommendations             # Suggest improvements
"""

import argparse
import json
import statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional


class AgentPerformanceScorer:
    """Track and score agent performance from execution history."""

    def __init__(self, telemetry_path: Path = None):
        """Initialize scorer with telemetry database path."""
        if telemetry_path is None:
            telemetry_path = Path(__file__).parent.parent / "telemetry" / "agent-performance.jsonl"
        self.telemetry_path = telemetry_path
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    def load_performance_db(self) -> List[Dict[str, Any]]:
        """Load all performance records from JSONL database."""
        if not self.telemetry_path.exists():
            return []

        records = []
        try:
            with open(self.telemetry_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"Error loading telemetry: {e}")
        return records

    def save_performance_record(self, record: Dict[str, Any]) -> None:
        """Append a performance record to the JSONL database."""
        try:
            with open(self.telemetry_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            print(f"Error saving record: {e}")

    def collect_from_plans(self, plans_dir: Path) -> int:
        """Scan plan JSONs and extract agent performance data."""
        existing_records = self.load_performance_db()
        existing_keys = {(r.get("plan_id"), r.get("step_id")) for r in existing_records}

        plans_dir = Path(plans_dir)
        if not plans_dir.exists():
            print(f"Plans directory not found: {plans_dir}")
            return 0

        new_count = 0
        agent_set = set()

        for plan_file in plans_dir.glob("*.json"):
            try:
                with open(plan_file, "r") as f:
                    content = f.read()
                    # Handle trailing commas
                    content = content.replace(",\n}", "\n}").replace(",\n]", "\n]")
                    plan_data = json.loads(content)

                plan_id = plan_data.get("id", plan_file.stem)
                steps = plan_data.get("steps", [])

                for step_idx, step in enumerate(steps):
                    step_id = step.get("id", f"step-{step_idx}")
                    key = (plan_id, step_id)

                    if key in existing_keys:
                        continue

                    agent = step.get("agent")
                    if not agent:
                        continue

                    agent_set.add(agent)

                    record = {
                        "timestamp": datetime.now().isoformat(),
                        "agent": agent,
                        "plan_id": plan_id,
                        "stack": step.get("stack", "unknown"),
                        "step_id": step_id,
                        "task_summary": (step.get("task", "")[:100]),
                        "status": step.get("status", "unknown"),
                        "estimated_tokens": step.get("estimated_tokens", 0),
                        "actual_tokens": step.get("actual_tokens", 0),
                        "duration_seconds": step.get("duration_seconds", 0.0),
                        "priority": step.get("priority", "normal"),
                        "had_context": step.get("had_context", False),
                        "context_sources": step.get("context_sources", 0),
                    }
                    self.save_performance_record(record)
                    new_count += 1

            except (json.JSONDecodeError, KeyError, IOError) as e:
                print(f"Warning: Could not process {plan_file.name}: {e}")
                continue

        print(f"Collected {new_count} new records for {len(agent_set)} agents")
        return new_count

    def calculate_agent_scores(self, records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Calculate composite scores for each agent."""
        agent_stats = defaultdict(lambda: {
            "completed": 0,
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
            "total": 0,
            "token_estimates": [],
            "token_actuals": [],
            "durations": [],
            "invocations": [],
        })

        # Aggregate stats
        for record in records:
            agent = record.get("agent")
            if not agent:
                continue

            stats = agent_stats[agent]
            status = record.get("status", "unknown")

            stats[status] = stats.get(status, 0) + 1
            stats["total"] += 1
            stats["invocations"].append(record)

            estimated = record.get("estimated_tokens", 0) or 0
            actual = record.get("actual_tokens", 0) or 0
            duration = record.get("duration_seconds", 0) or 0

            if estimated > 0:
                stats["token_estimates"].append(estimated)
            if actual > 0:
                stats["token_actuals"].append(actual)
            if duration > 0:
                stats["durations"].append(duration)

        # Calculate scores
        scores = {}
        for agent, stats in agent_stats.items():
            total = stats["total"]
            completed = stats.get("completed", 0)

            # Success rate (40% weight)
            success_rate = (completed / total * 100) if total > 0 else 0

            # Token efficiency (30% weight)
            efficiency_score = 100.0
            if stats["token_actuals"] and stats["token_estimates"]:
                avg_estimated = statistics.mean(stats["token_estimates"])
                avg_actual = statistics.mean(stats["token_actuals"])
                if avg_actual > 0:
                    efficiency_score = min(100, (avg_estimated / avg_actual) * 100)

            # Consistency (20% weight)
            consistency_score = 100.0
            if len(stats["token_actuals"]) > 1:
                mean_tokens = statistics.mean(stats["token_actuals"])
                stdev = statistics.stdev(stats["token_actuals"])
                if mean_tokens > 0:
                    cv = (stdev / mean_tokens) * 100  # Coefficient of variation
                    consistency_score = max(0, 100 - cv)

            # Speed (10% weight)
            speed_score = 100.0
            if stats["durations"]:
                avg_duration = statistics.mean(stats["durations"])
                baseline_duration = 60.0  # 60 seconds baseline
                speed_score = max(0, 100 - (avg_duration / baseline_duration * 50))

            # Composite score
            composite = (
                success_rate * 0.4 +
                efficiency_score * 0.3 +
                consistency_score * 0.2 +
                speed_score * 0.1
            )

            scores[agent] = {
                "composite": round(composite, 1),
                "success_rate": round(success_rate, 1),
                "efficiency": round(efficiency_score, 1),
                "consistency": round(consistency_score, 1),
                "speed": round(speed_score, 1),
                "total_invocations": total,
                "completed": completed,
                "failed": stats.get("failed", 0),
                "blocked": stats.get("blocked", 0),
                "skipped": stats.get("skipped", 0),
                "avg_tokens_estimated": round(statistics.mean(stats["token_estimates"]), 0) if stats["token_estimates"] else 0,
                "avg_tokens_actual": round(statistics.mean(stats["token_actuals"]), 0) if stats["token_actuals"] else 0,
                "avg_duration": round(statistics.mean(stats["durations"]), 2) if stats["durations"] else 0,
                "stats": stats,
            }

        return scores

    def render_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """Render a formatted text table."""
        if not rows:
            return ""

        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Header
        header_line = "  ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers))
        separator = "  ".join("-" * w for w in col_widths)

        # Rows
        result = [header_line, separator]
        for row in rows:
            result.append("  ".join(f"{str(cell):<{col_widths[i]}}" for i, cell in enumerate(row)))

        return "\n".join(result)

    def render_sparkline(self, values: List[float]) -> str:
        """Render a Unicode sparkline from values."""
        if not values or len(values) == 0:
            return "━"

        # Normalize to 0-8 range for Unicode block characters
        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val if max_val > min_val else 1

        blocks = "▁▂▃▄▅▆▇█"
        sparkline = ""
        for val in values[-10:]:  # Last 10 values
            normalized = (val - min_val) / range_val if range_val > 0 else 0.5
            index = int(normalized * (len(blocks) - 1))
            sparkline += blocks[index]

        return sparkline

    def classify_failure(self, record: Dict[str, Any]) -> str:
        """Classify failure type from a record."""
        if record.get("status") == "failed":
            task = record.get("task_summary", "").lower()
            if "timeout" in task or "timeout" in str(record):
                return "timeout"
            if "error" in task:
                return "error"
            if "network" in task or "connection" in task:
                return "network"
            return "unknown"
        return "not_failed"

    def report(self) -> None:
        """Print comprehensive performance report."""
        records = self.load_performance_db()
        if not records:
            print("No performance data available. Run 'collect' first.")
            return

        scores = self.calculate_agent_scores(records)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]["composite"], reverse=True)

        # Summary
        total_invocations = sum(s["total_invocations"] for s in scores.values())
        total_completed = sum(s["completed"] for s in scores.values())
        overall_success = (total_completed / total_invocations * 100) if total_invocations > 0 else 0

        print("\nAGENT PERFORMANCE REPORT")
        print("═" * 90)
        print(f"Agents tracked: {len(scores)}")
        print(f"Total invocations: {total_invocations}")
        print(f"Overall success rate: {overall_success:.1f}%\n")

        # Agent scores table
        print("AGENT SCORES (sorted by composite):")
        headers = ["Agent", "Score", "Success", "Efficiency", "Consistency", "Speed"]
        rows = []
        for agent, score in sorted_scores:
            rows.append([
                agent,
                f"{score['composite']}",
                f"{score['success_rate']:.0f}%",
                f"{score['efficiency']:.0f}%",
                f"{score['consistency']:.0f}%",
                f"{score['speed']:.0f}%",
            ])

        print(self.render_table(headers, rows))

        # Alerts
        print("\nALERTS:")
        alerts_shown = 0
        for agent, score in sorted_scores:
            if score["efficiency"] < 80:
                print(f"  ⚠️  {agent}: {score['efficiency']:.0f}% token efficiency (over budget)")
                alerts_shown += 1
            if score["success_rate"] < 90:
                failed = score["failed"]
                print(f"  ⚠️  {agent}: {score['success_rate']:.0f}% success rate ({failed} failures)")
                alerts_shown += 1
            if score["speed"] < 70:
                print(f"  ⚠️  {agent}: {score['speed']:.0f}% speed score (slow)")
                alerts_shown += 1

        if alerts_shown == 0:
            print("  ✓ No alerts")

        print("═" * 90)

    def leaderboard(self) -> None:
        """Print ranked agent leaderboard with trends."""
        records = self.load_performance_db()
        if not records:
            print("No performance data available.")
            return

        scores = self.calculate_agent_scores(records)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]["composite"], reverse=True)

        print("\nAGENT LEADERBOARD")
        print("═" * 70)

        headers = ["Rank", "Agent", "Score", "Success", "Trend"]
        rows = []

        for rank, (agent, score) in enumerate(sorted_scores, 1):
            # Calculate trend (last 5 invocations)
            recent = score["stats"]["invocations"][-5:]
            recent_successes = sum(1 for r in recent if r.get("status") == "completed")
            trend = f"{recent_successes}/5"

            sparkline = self.render_sparkline([
                1.0 if r.get("status") == "completed" else 0.0
                for r in score["stats"]["invocations"][-10:]
            ])

            rows.append([
                str(rank),
                agent,
                f"{score['composite']}",
                f"{score['success_rate']:.0f}%",
                sparkline,
            ])

        print(self.render_table(headers, rows))
        print("═" * 70)

    def agent_profile(self, agent_name: str) -> None:
        """Print detailed profile for a specific agent."""
        records = self.load_performance_db()
        agent_records = [r for r in records if r.get("agent") == agent_name]

        if not agent_records:
            print(f"No data found for agent: {agent_name}")
            return

        scores = self.calculate_agent_scores(records)
        agent_score = scores.get(agent_name)

        if not agent_score:
            print(f"Could not calculate score for {agent_name}")
            return

        print(f"\nAGENT PROFILE: {agent_name}")
        print("═" * 70)

        # All-time stats
        print("\nALL-TIME STATS:")
        print(f"  Composite Score: {agent_score['composite']}")
        print(f"  Success Rate: {agent_score['success_rate']:.1f}%")
        print(f"  Token Efficiency: {agent_score['efficiency']:.1f}%")
        print(f"  Consistency: {agent_score['consistency']:.1f}%")
        print(f"  Speed Score: {agent_score['speed']:.1f}%")
        print(f"  Total Invocations: {agent_score['total_invocations']}")
        print(f"    - Completed: {agent_score['completed']}")
        print(f"    - Failed: {agent_score['failed']}")
        print(f"    - Blocked: {agent_score['blocked']}")
        print(f"    - Skipped: {agent_score['skipped']}")
        print(f"  Avg Estimated Tokens: {agent_score['avg_tokens_estimated']}")
        print(f"  Avg Actual Tokens: {agent_score['avg_tokens_actual']}")
        print(f"  Avg Duration: {agent_score['avg_duration']}s")

        # Recent invocations
        print("\nRECENT 10 INVOCATIONS:")
        headers = ["Date", "Status", "Task", "Tokens", "Duration"]
        rows = []
        for record in agent_records[-10:]:
            ts = record.get("timestamp", "")[:10]
            status = record.get("status", "?")[:4]
            task = record.get("task_summary", "")[:30]
            tokens = record.get("actual_tokens", 0)
            duration = f"{record.get('duration_seconds', 0):.1f}s"
            rows.append([ts, status, task, str(tokens), duration])

        print(self.render_table(headers, rows))

        # Task patterns
        print("\nCOMMON TASK PATTERNS:")
        task_counts = defaultdict(int)
        for r in agent_records:
            task = r.get("task_summary", "")[:30]
            if task:
                task_counts[task] += 1

        for task, count in sorted(task_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {count}x {task}")

        # Failure analysis
        failures = [r for r in agent_records if r.get("status") == "failed"]
        if failures:
            print("\nFAILURE ANALYSIS:")
            failure_types = defaultdict(int)
            for f in failures:
                ftype = self.classify_failure(f)
                failure_types[ftype] += 1

            for ftype, count in sorted(failure_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  {count}x {ftype}")

        print("═" * 70)

    def recommendations(self) -> None:
        """Print recommendations for improvement."""
        records = self.load_performance_db()
        if not records:
            print("No performance data available.")
            return

        scores = self.calculate_agent_scores(records)

        print("\nAGENT IMPROVEMENT RECOMMENDATIONS")
        print("═" * 70)

        recommendations = []

        for agent, score in scores.items():
            # Token budget issues
            if score["efficiency"] < 75:
                recommendations.append({
                    "priority": "high",
                    "agent": agent,
                    "issue": "Token Budget Overshoot",
                    "detail": f"{score['efficiency']:.0f}% efficiency - consider simplifying prompts",
                })

            # Success rate issues
            if score["success_rate"] < 85:
                recommendations.append({
                    "priority": "high",
                    "agent": agent,
                    "issue": "Low Success Rate",
                    "detail": f"{score['success_rate']:.0f}% success - review agent scope",
                })

            # Speed issues
            if score["speed"] < 60 and score["total_invocations"] > 5:
                recommendations.append({
                    "priority": "medium",
                    "agent": agent,
                    "issue": "Slow Execution",
                    "detail": f"{score['avg_duration']:.1f}s avg - consider context preloading",
                })

            # Consistency issues
            if score["consistency"] < 70:
                recommendations.append({
                    "priority": "medium",
                    "agent": agent,
                    "issue": "Inconsistent Performance",
                    "detail": f"High variance in token usage - stabilize behavior",
                })

            # Low utilization
            if score["total_invocations"] < 3:
                recommendations.append({
                    "priority": "low",
                    "agent": agent,
                    "issue": "Low Utilization",
                    "detail": f"Only {score['total_invocations']} invocations - consider deprecation",
                })

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: (priority_order[x["priority"]], x["agent"]))

        if not recommendations:
            print("✓ All agents performing well!")
        else:
            for rec in recommendations:
                priority_marker = "🔴" if rec["priority"] == "high" else "🟡" if rec["priority"] == "medium" else "🟢"
                print(f"\n{priority_marker} {rec['agent']}: {rec['issue']}")
                print(f"   {rec['detail']}")

        print("\n" + "═" * 70)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Performance Scoring — Track and analyze agent performance."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Collect command
    collect_parser = subparsers.add_parser("collect", help="Scan plans and build performance DB")
    collect_parser.add_argument("plans_dir", help="Directory containing plan JSON files")

    # Report command
    subparsers.add_parser("report", help="Show performance report")

    # Leaderboard command
    subparsers.add_parser("leaderboard", help="Ranked agent leaderboard")

    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Detailed agent profile")
    agent_parser.add_argument("name", help="Agent name (e.g., @rust-expert)")

    # Recommendations command
    subparsers.add_parser("recommendations", help="Suggest improvements")

    args = parser.parse_args()

    scorer = AgentPerformanceScorer()

    if args.command == "collect":
        scorer.collect_from_plans(args.plans_dir)
    elif args.command == "report":
        scorer.report()
    elif args.command == "leaderboard":
        scorer.leaderboard()
    elif args.command == "agent":
        scorer.agent_profile(args.name)
    elif args.command == "recommendations":
        scorer.recommendations()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
