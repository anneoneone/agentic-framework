#!/usr/bin/env python3
"""Token Telemetry — Collect and report token usage across plan executions.

Usage:
    python token-telemetry.py collect <plans_dir>       # Scan plans, update telemetry DB
    python token-telemetry.py report [--format text|json]  # Generate usage report
    python token-telemetry.py dashboard                  # Show key metrics
    python token-telemetry.py agent-stats [--agent @name]  # Per-agent statistics
    python token-telemetry.py budget-accuracy             # Estimated vs actual comparison
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TokenTelemetry:
    """Token telemetry collection and reporting system."""

    def __init__(self, framework_root: Optional[Path] = None):
        """Initialize telemetry system.

        Args:
            framework_root: Root of framework directory. Defaults to script's parent.parent
        """
        if framework_root is None:
            framework_root = Path(__file__).parent.parent

        self.framework_root = framework_root
        self.telemetry_dir = framework_root / "telemetry"
        self.db_path = self.telemetry_dir / "token-usage.jsonl"
        self.telemetry_dir.mkdir(exist_ok=True)

    def load_telemetry_db(self) -> List[Dict[str, Any]]:
        """Load all records from telemetry database.

        Returns:
            List of telemetry records
        """
        records = []
        if not self.db_path.exists():
            return records

        with open(self.db_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return records

    def save_telemetry_record(self, record: Dict[str, Any]) -> None:
        """Append a telemetry record to the database.

        Args:
            record: Telemetry record to append
        """
        with open(self.db_path, 'a') as f:
            f.write(json.dumps(record) + '\n')

    def scan_plans(self, plans_dir: Path) -> List[Path]:
        """Recursively find all plan JSON files.

        Args:
            plans_dir: Directory to scan

        Returns:
            List of plan file paths
        """
        if not plans_dir.exists():
            return []

        return sorted(plans_dir.glob('**/*.json'))

    def _clean_json(self, content: str) -> str:
        """Clean JSON content by removing trailing commas.

        Args:
            content: Raw JSON content

        Returns:
            Cleaned JSON string
        """
        # Remove trailing commas before } and ]
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        return content

    def extract_step_telemetry(self, plan_path: Path) -> List[Dict[str, Any]]:
        """Extract token usage telemetry from a plan file.

        Args:
            plan_path: Path to plan JSON file

        Returns:
            List of telemetry records from this plan
        """
        records = []

        try:
            with open(plan_path, 'r') as f:
                content = f.read()

            # Clean JSON
            content = self._clean_json(content)
            plan = json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            return records

        # Extract plan-level metadata
        plan_id = plan.get('id', plan_path.stem)
        timestamp = plan.get('timestamp', datetime.now().isoformat())
        stack = plan.get('stack', 'unknown')
        token_budget = plan.get('token_budget', {})
        plan_estimated_tokens = token_budget.get('estimated_total', None)

        # Process steps
        steps = plan.get('steps', [])
        for step in steps:
            step_id = step.get('id', step.get('name', 'unknown'))
            output = step.get('output', {})

            # Only create record if there's actual token data
            if not output or 'tokens_used' not in output:
                continue

            actual_tokens = output.get('tokens_used')
            estimated_tokens = step.get('estimated_tokens')
            duration = output.get('duration_seconds')

            record = {
                'timestamp': timestamp,
                'plan_id': plan_id,
                'stack': stack,
                'step_id': step_id,
                'agent': step.get('agent', 'unknown'),
                'priority': step.get('priority', 'normal'),
                'estimated_tokens': estimated_tokens,
                'actual_tokens': actual_tokens,
                'duration_seconds': duration,
                'execution_mode': step.get('execution_mode', 'sequential'),
                'parallel_group': step.get('parallel_group'),
                'context_sources_count': len(step.get('context_sources', [])),
                'status': step.get('status', 'unknown'),
            }

            records.append(record)

        return records

    def collect(self, plans_dir: Path) -> Tuple[int, int]:
        """Collect telemetry from all plans in directory.

        Args:
            plans_dir: Directory containing plan files

        Returns:
            Tuple of (new_records_added, total_plans_scanned)
        """
        plans = self.scan_plans(plans_dir)
        new_count = 0
        plan_count = 0

        # Load existing records to avoid duplicates
        existing = self.load_telemetry_db()
        existing_keys = {(r['plan_id'], r['step_id']) for r in existing}

        for plan_path in plans:
            plan_count += 1
            records = self.extract_step_telemetry(plan_path)

            for record in records:
                key = (record['plan_id'], record['step_id'])
                if key not in existing_keys:
                    self.save_telemetry_record(record)
                    existing_keys.add(key)
                    new_count += 1

        return new_count, plan_count

    def format_tokens(self, n: Optional[int]) -> str:
        """Format token count with thousands separator.

        Args:
            n: Token count (or None)

        Returns:
            Formatted string
        """
        if n is None:
            return "N/A"
        return f"{n:,}"

    def render_sparkline(self, values: List[float]) -> str:
        """Render unicode sparkline from values.

        Args:
            values: List of numeric values

        Returns:
            Unicode sparkline string
        """
        if not values:
            return ""

        chars = "▁▂▃▄▅▆▇█"
        min_val = min(values)
        max_val = max(values)

        if min_val == max_val:
            return "".join([chars[4] for _ in values])

        range_val = max_val - min_val
        line = ""
        for val in values:
            normalized = (val - min_val) / range_val
            index = min(int(normalized * (len(chars) - 1)), len(chars) - 1)
            line += chars[index]

        return line

    def calculate_budget_accuracy(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate budget accuracy metrics.

        Args:
            records: List of telemetry records

        Returns:
            Dictionary with accuracy metrics
        """
        if not records:
            return {'overall': 0, 'by_agent': {}, 'by_plan': {}}

        # Per-step accuracy
        step_accuracies = []
        for record in records:
            if record['estimated_tokens'] and record['actual_tokens']:
                accuracy = (record['actual_tokens'] / record['estimated_tokens']) * 100
                step_accuracies.append(accuracy)

        # Per-agent accuracy
        agent_accuracy = defaultdict(list)
        for record in records:
            if record['estimated_tokens'] and record['actual_tokens']:
                accuracy = (record['actual_tokens'] / record['estimated_tokens']) * 100
                agent_accuracy[record['agent']].append(accuracy)

        agent_accuracy = {
            agent: sum(accs) / len(accs)
            for agent, accs in agent_accuracy.items()
        }

        # Per-plan accuracy
        plan_accuracy = defaultdict(list)
        for record in records:
            if record['estimated_tokens'] and record['actual_tokens']:
                accuracy = (record['actual_tokens'] / record['estimated_tokens']) * 100
                plan_accuracy[record['plan_id']].append(accuracy)

        plan_accuracy = {
            plan: sum(accs) / len(accs)
            for plan, accs in plan_accuracy.items()
        }

        overall = sum(step_accuracies) / len(step_accuracies) if step_accuracies else 0

        return {
            'overall': overall,
            'by_agent': agent_accuracy,
            'by_plan': plan_accuracy,
        }

    def report(self, output_format: str = 'text') -> str:
        """Generate usage report.

        Args:
            output_format: 'text' or 'json'

        Returns:
            Formatted report string
        """
        records = self.load_telemetry_db()

        if not records:
            return "No telemetry data available."

        # Calculate metrics
        total_tokens = sum(r.get('actual_tokens', 0) for r in records if r.get('actual_tokens'))

        # Tokens per stack
        tokens_by_stack = defaultdict(int)
        for r in records:
            if r.get('actual_tokens'):
                tokens_by_stack[r['stack']] += r['actual_tokens']

        # Tokens per agent
        tokens_by_agent = defaultdict(int)
        steps_by_agent = defaultdict(int)
        for r in records:
            if r.get('actual_tokens'):
                tokens_by_agent[r['agent']] += r['actual_tokens']
                steps_by_agent[r['agent']] += 1

        # Most expensive plans
        tokens_by_plan = defaultdict(int)
        for r in records:
            if r.get('actual_tokens'):
                tokens_by_plan[r['plan_id']] += r['actual_tokens']

        top_plans = sorted(tokens_by_plan.items(), key=lambda x: x[1], reverse=True)[:5]

        # Budget accuracy
        accuracy = self.calculate_budget_accuracy(records)

        # Average tokens per step
        valid_records = [r for r in records if r.get('actual_tokens')]
        avg_tokens = sum(r['actual_tokens'] for r in valid_records) / len(valid_records) if valid_records else 0

        if output_format == 'json':
            return json.dumps({
                'total_tokens': total_tokens,
                'records_count': len(records),
                'tokens_by_stack': tokens_by_stack,
                'tokens_by_agent': tokens_by_agent,
                'steps_by_agent': steps_by_agent,
                'avg_tokens_per_step': avg_tokens,
                'top_plans': [{'plan_id': pid, 'tokens': tokens} for pid, tokens in top_plans],
                'budget_accuracy': {
                    'overall_percent': accuracy['overall'],
                    'by_agent': accuracy['by_agent'],
                },
            }, indent=2)

        # Text format
        lines = []
        lines.append("TOKEN USAGE REPORT")
        lines.append("=" * 50)
        lines.append(f"Total tokens: {self.format_tokens(total_tokens)}")
        lines.append(f"Records: {len(records)}")
        lines.append(f"Average per step: {self.format_tokens(int(avg_tokens))}")
        lines.append("")

        lines.append("TOKENS BY STACK:")
        for stack in sorted(tokens_by_stack.keys()):
            lines.append(f"  {stack}: {self.format_tokens(tokens_by_stack[stack])}")
        lines.append("")

        lines.append("TOP AGENTS BY TOKEN USAGE:")
        sorted_agents = sorted(tokens_by_agent.items(), key=lambda x: x[1], reverse=True)
        for agent, tokens in sorted_agents[:10]:
            steps = steps_by_agent[agent]
            avg = tokens // steps if steps > 0 else 0
            lines.append(f"  {agent}: {self.format_tokens(tokens)} ({steps} steps, avg {self.format_tokens(avg)}/step)")
        lines.append("")

        lines.append("TOP 5 MOST EXPENSIVE PLANS:")
        for plan_id, tokens in top_plans:
            lines.append(f"  {plan_id}: {self.format_tokens(tokens)}")
        lines.append("")

        lines.append("BUDGET ACCURACY:")
        lines.append(f"  Overall: {accuracy['overall']:.1f}%")
        lines.append("  By agent (top 5):")
        sorted_accuracy = sorted(accuracy['by_agent'].items(), key=lambda x: x[1], reverse=True)
        for agent, pct in sorted_accuracy[:5]:
            lines.append(f"    {agent}: {pct:.1f}%")

        return "\n".join(lines)

    def dashboard(self) -> str:
        """Generate compact dashboard output.

        Returns:
            Dashboard string
        """
        records = self.load_telemetry_db()

        if not records:
            return "No telemetry data available."

        # Calculate metrics
        total_tokens = sum(r.get('actual_tokens', 0) for r in records if r.get('actual_tokens'))

        # Unique plans
        unique_plans = len(set(r['plan_id'] for r in records))

        # Tokens per agent
        tokens_by_agent = defaultdict(int)
        steps_by_agent = defaultdict(int)
        for r in records:
            if r.get('actual_tokens'):
                tokens_by_agent[r['agent']] += r['actual_tokens']
                steps_by_agent[r['agent']] += 1

        # Budget accuracy
        accuracy = self.calculate_budget_accuracy(records)

        # Trend: last 7 plans
        plans_ordered = sorted(set(r['plan_id'] for r in records))[-7:]
        plan_tokens = [
            sum(r['actual_tokens'] for r in records if r['plan_id'] == pid and r.get('actual_tokens'))
            for pid in plans_ordered
        ]

        lines = []
        lines.append("\nTOKEN TELEMETRY DASHBOARD")
        lines.append("═" * 50)
        lines.append(f"Total tokens: {self.format_tokens(total_tokens)}")
        lines.append(f"Plans analyzed: {unique_plans}")
        lines.append(f"Steps executed: {len(records)}")
        lines.append("")

        lines.append("TOP AGENTS BY TOKEN USAGE:")
        sorted_agents = sorted(tokens_by_agent.items(), key=lambda x: x[1], reverse=True)
        for agent, tokens in sorted_agents[:5]:
            steps = steps_by_agent[agent]
            avg = tokens // steps if steps > 0 else 0
            lines.append(f"  {agent:.<35} {self.format_tokens(tokens):>8} tokens (avg {self.format_tokens(avg)}/step)")
        lines.append("")

        lines.append("BUDGET ACCURACY:")
        lines.append(f"  Overall: {accuracy['overall']:.0f}% (estimated vs actual)")

        if accuracy['by_agent']:
            sorted_accuracy = sorted(accuracy['by_agent'].items(), key=lambda x: x[1], reverse=True)
            best = sorted_accuracy[0]
            worst = sorted_accuracy[-1]
            lines.append(f"  Best: {best[0]} at {best[1]:.0f}%")
            lines.append(f"  Worst: {worst[0]} at {worst[1]:.0f}%")
        lines.append("")

        if plan_tokens:
            lines.append(f"TREND (last {len(plans_ordered)} plans):")
            sparkline = self.render_sparkline(plan_tokens)
            lines.append(f"  {sparkline}")
            trend_avg = sum(plan_tokens) / len(plan_tokens)
            lines.append(f"  Average: {self.format_tokens(int(trend_avg))} tokens/plan")

        lines.append("═" * 50 + "\n")

        return "\n".join(lines)

    def agent_stats(self, agent_name: Optional[str] = None) -> str:
        """Generate per-agent statistics.

        Args:
            agent_name: Specific agent to detail (optional)

        Returns:
            Statistics string
        """
        records = self.load_telemetry_db()

        if not records:
            return "No telemetry data available."

        # Collect agent statistics
        agent_stats = defaultdict(lambda: {
            'total_tokens': 0,
            'total_steps': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0,
            'total_duration': 0.0,
            'steps': [],
        })

        for record in records:
            agent = record['agent']
            if record.get('actual_tokens'):
                agent_stats[agent]['total_tokens'] += record['actual_tokens']
            agent_stats[agent]['total_steps'] += 1

            status = record.get('status', 'unknown')
            if status == 'completed':
                agent_stats[agent]['completed'] += 1
            elif status == 'failed':
                agent_stats[agent]['failed'] += 1
            elif status == 'skipped':
                agent_stats[agent]['skipped'] += 1

            duration = record.get('duration_seconds')
            if duration:
                agent_stats[agent]['total_duration'] += duration

            agent_stats[agent]['steps'].append(record)

        lines = []
        lines.append("\nPER-AGENT STATISTICS")
        lines.append("=" * 70)

        if agent_name:
            # Detailed stats for one agent
            if agent_name not in agent_stats:
                return f"Agent {agent_name} not found."

            stats = agent_stats[agent_name]
            lines.append(f"\nAgent: {agent_name}")
            lines.append(f"  Total invocations: {stats['total_steps']}")
            lines.append(f"  Total tokens: {self.format_tokens(stats['total_tokens'])}")
            lines.append(f"  Average tokens/step: {self.format_tokens(int(stats['total_tokens'] / stats['total_steps']) if stats['total_steps'] > 0 else 0)}")

            success_rate = (stats['completed'] / stats['total_steps'] * 100) if stats['total_steps'] > 0 else 0
            lines.append(f"  Success rate: {success_rate:.1f}% ({stats['completed']} completed, {stats['failed']} failed, {stats['skipped']} skipped)")

            avg_duration = stats['total_duration'] / stats['total_steps'] if stats['total_steps'] > 0 else 0
            lines.append(f"  Average duration: {avg_duration:.2f}s")

            lines.append(f"\n  Recent steps:")
            for step in stats['steps'][-10:]:
                status = step.get('status', 'unknown')
                tokens = self.format_tokens(step.get('actual_tokens'))
                lines.append(f"    {step['plan_id']} / {step['step_id']}: {tokens} tokens ({status})")
        else:
            # Summary for all agents
            sorted_agents = sorted(agent_stats.items(), key=lambda x: x[1]['total_tokens'], reverse=True)

            for agent, stats in sorted_agents[:15]:
                avg_tokens = int(stats['total_tokens'] / stats['total_steps']) if stats['total_steps'] > 0 else 0
                success_rate = (stats['completed'] / stats['total_steps'] * 100) if stats['total_steps'] > 0 else 0
                lines.append(f"\n{agent}")
                lines.append(f"  Invocations: {stats['total_steps']} | Total tokens: {self.format_tokens(stats['total_tokens'])} | Avg: {self.format_tokens(avg_tokens)}")
                lines.append(f"  Success: {success_rate:.0f}% | Avg duration: {stats['total_duration'] / stats['total_steps']:.2f}s" if stats['total_steps'] > 0 else "  No data")

        lines.append("\n" + "=" * 70 + "\n")
        return "\n".join(lines)

    def budget_accuracy_report(self) -> str:
        """Generate budget accuracy comparison report.

        Returns:
            Report string
        """
        records = self.load_telemetry_db()

        if not records:
            return "No telemetry data available."

        # Per-step comparison
        step_data = [
            r for r in records
            if r.get('estimated_tokens') and r.get('actual_tokens')
        ]

        if not step_data:
            return "No step-level budget data available."

        # Per-agent accuracy
        agent_accuracy = defaultdict(list)
        for record in step_data:
            accuracy = (record['actual_tokens'] / record['estimated_tokens']) * 100
            agent_accuracy[record['agent']].append({
                'accuracy': accuracy,
                'difference': record['actual_tokens'] - record['estimated_tokens'],
                'plan_id': record['plan_id'],
            })

        lines = []
        lines.append("\nBUDGET ACCURACY ANALYSIS")
        lines.append("=" * 70)

        for agent in sorted(agent_accuracy.keys()):
            data = agent_accuracy[agent]
            accuracies = [d['accuracy'] for d in data]
            differences = [d['difference'] for d in data]

            avg_accuracy = sum(accuracies) / len(accuracies)
            avg_diff = sum(differences) / len(differences)

            overestimated = sum(1 for d in data if d['difference'] < 0)
            underestimated = sum(1 for d in data if d['difference'] > 0)

            lines.append(f"\n{agent}")
            lines.append(f"  Samples: {len(data)}")
            lines.append(f"  Accuracy: {avg_accuracy:.1f}% (estimated vs actual)")
            lines.append(f"  Avg difference: {int(avg_diff)} tokens")
            lines.append(f"  Overestimated: {overestimated} | Underestimated: {underestimated}")

            if avg_diff < 0:
                lines.append(f"  Recommendation: Reduce estimate by ~{abs(int(avg_diff))} tokens")
            else:
                lines.append(f"  Recommendation: Increase estimate by ~{int(avg_diff)} tokens")

        lines.append("\n" + "=" * 70 + "\n")
        return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Token telemetry collection and reporting system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Collect command
    collect_parser = subparsers.add_parser('collect', help='Collect telemetry from plans')
    collect_parser.add_argument('plans_dir', type=Path, help='Directory containing plan files')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate usage report')
    report_parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')

    # Dashboard command
    subparsers.add_parser('dashboard', help='Show dashboard')

    # Agent stats command
    agent_parser = subparsers.add_parser('agent-stats', help='Per-agent statistics')
    agent_parser.add_argument('--agent', help='Specific agent to detail')

    # Budget accuracy command
    subparsers.add_parser('budget-accuracy', help='Budget accuracy analysis')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    telemetry = TokenTelemetry()

    try:
        if args.command == 'collect':
            new, total = telemetry.collect(args.plans_dir)
            print(f"Collected {new} new records from {total} plans")
            return 0

        elif args.command == 'report':
            report = telemetry.report(args.format)
            print(report)
            return 0

        elif args.command == 'dashboard':
            dashboard = telemetry.dashboard()
            print(dashboard)
            return 0

        elif args.command == 'agent-stats':
            stats = telemetry.agent_stats(args.agent)
            print(stats)
            return 0

        elif args.command == 'budget-accuracy':
            report = telemetry.budget_accuracy_report()
            print(report)
            return 0

        else:
            parser.print_help()
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
