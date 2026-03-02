#!/usr/bin/env python3
"""Adaptive Cache Manager — Tune cache TTLs based on resource change frequency.

Monitors file modification times and access patterns to recommend
optimal TTL values for MCP server caches (agent-registry, knowledge-search).

Usage:
    python adaptive-cache.py analyze                     # Analyze current cache targets
    python adaptive-cache.py recommend                   # Suggest TTL adjustments
    python adaptive-cache.py apply                       # Apply recommended TTLs
    python adaptive-cache.py monitor --interval 3600     # Continuous monitoring
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


class AdaptiveCacheManager:
    """Manages adaptive TTL configuration for MCP server caches."""

    # TTL recommendation thresholds (changes per day)
    HOT_THRESHOLD = 1.0  # >1 change/day => 1h TTL
    WARM_THRESHOLD = 1.0 / 7  # 1 change/week => 6h TTL
    COLD_THRESHOLD = 1.0 / 30  # <1 change/week => 24h TTL
    # Frozen: no changes in 30 days => 168h (1 week)

    TTL_HOT = 1  # hours
    TTL_WARM = 6  # hours
    TTL_COLD = 24  # hours
    TTL_FROZEN = 168  # hours (1 week)

    def __init__(self, framework_root: Path):
        """Initialize cache manager with framework root."""
        self.framework_root = Path(framework_root)
        self.cache_dir = self.framework_root / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.frequency_db_path = self.cache_dir / "change-frequency.jsonl"
        self.ttl_config_path = self.cache_dir / "ttl-config.json"
        self.snapshot_path = self.cache_dir / "mtime-snapshot.json"

        self.frequency_db: Dict[str, dict] = {}
        self.load_frequency_db()

    def load_frequency_db(self):
        """Load existing change frequency database."""
        if not self.frequency_db_path.exists():
            self.frequency_db = {}
            return

        try:
            with open(self.frequency_db_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        self.frequency_db[entry["path"]] = entry
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load frequency DB: {e}", file=sys.stderr)
            self.frequency_db = {}

    def save_frequency_db(self):
        """Save change frequency database."""
        try:
            with open(self.frequency_db_path, "w") as f:
                for path in sorted(self.frequency_db.keys()):
                    entry = self.frequency_db[path]
                    f.write(json.dumps(entry) + "\n")
        except IOError as e:
            print(f"Error saving frequency DB: {e}", file=sys.stderr)

    def get_cache_targets(self) -> List[Path]:
        """Get all cache target files from framework and stacks."""
        targets = []

        # Framework cache targets
        framework_globs = [
            "core/*/agents/*.agent.md",
            "core/*/knowledge/*.jsonl",
            "knowledge/*.jsonl",
        ]

        for glob_pattern in framework_globs:
            targets.extend(self.framework_root.glob(glob_pattern))

        # Stack cache targets
        stacks_root = self.framework_root.parent.parent / "stacks"
        if stacks_root.exists():
            stack_globs = [
                ".github/agents/*.agent.md",
                "docs/knowledge/*.jsonl",
                ".copilot-agents/plans/*.json",
            ]

            for stack_dir in stacks_root.iterdir():
                if stack_dir.is_dir():
                    for glob_pattern in stack_globs:
                        targets.extend(stack_dir.glob(glob_pattern))

        return targets

    def analyze(self) -> Dict[str, dict]:
        """Analyze cache targets and collect modification data."""
        targets = self.get_cache_targets()
        analyzed = {}

        for target in targets:
            if not target.is_file():
                continue

            try:
                stat = target.stat()
                mtime = stat.st_mtime
                last_modified = datetime.fromtimestamp(mtime).isoformat()
                rel_path = self._get_relative_path(target)

                # Determine file type
                file_type = self._classify_file_type(rel_path)

                # Get existing entry or create new
                if rel_path in self.frequency_db:
                    entry = self.frequency_db[rel_path].copy()
                    old_mtime = datetime.fromisoformat(
                        entry["last_modified"]
                    ).timestamp()

                    # Check if file changed since last record
                    if mtime > old_mtime:
                        entry["change_count"] = entry.get("change_count", 0) + 1
                else:
                    entry = {
                        "path": rel_path,
                        "type": file_type,
                        "first_seen": datetime.now().isoformat(),
                        "change_count": 0,
                    }

                entry["last_modified"] = last_modified

                # Calculate change frequency
                first_seen = datetime.fromisoformat(entry["first_seen"])
                last_mod = datetime.fromisoformat(entry["last_modified"])
                days_tracked = max(1, (last_mod - first_seen).days)

                entry["avg_changes_per_day"] = round(
                    entry["change_count"] / days_tracked, 4
                )
                entry["current_ttl_hours"] = self._get_current_ttl(rel_path)

                analyzed[rel_path] = entry

            except (OSError, ValueError) as e:
                print(f"Error analyzing {target}: {e}", file=sys.stderr)

        self.frequency_db.update(analyzed)
        return analyzed

    def recommend(self) -> Dict[str, int]:
        """Generate TTL recommendations based on change frequency."""
        # Re-analyze to get current data
        self.analyze()

        recommendations = {
            "generated_at": datetime.now().isoformat(),
            "default_ttl_hours": self.TTL_COLD,
            "overrides": {},
            "per_file": {},
        }

        for path, entry in self.frequency_db.items():
            avg_changes = entry.get("avg_changes_per_day", 0)

            # Classify based on change frequency
            if avg_changes >= self.HOT_THRESHOLD:
                ttl = self.TTL_HOT
                category = "hot"
            elif avg_changes >= self.WARM_THRESHOLD:
                ttl = self.TTL_WARM
                category = "warm"
            elif avg_changes >= self.COLD_THRESHOLD:
                ttl = self.TTL_COLD
                category = "cold"
            else:
                # Check if frozen (no changes in 30 days)
                last_modified = datetime.fromisoformat(entry["last_modified"])
                days_since_change = (datetime.now() - last_modified).days
                if days_since_change >= 30:
                    ttl = self.TTL_FROZEN
                    category = "frozen"
                else:
                    ttl = self.TTL_COLD
                    category = "cold"

            entry["recommended_ttl_hours"] = ttl
            entry["recommendation_category"] = category

            # Add to per-file recommendations
            recommendations["per_file"][path] = ttl

        self.frequency_db = {
            k: v for k, v in self.frequency_db.items() if k in recommendations["per_file"]
        }

        return recommendations

    def apply(self) -> bool:
        """Apply recommended TTLs to config file."""
        recommendations = self.recommend()

        try:
            with open(self.ttl_config_path, "w") as f:
                json.dump(recommendations, f, indent=2)
            print(f"TTL config written to {self.ttl_config_path}")
            return True
        except IOError as e:
            print(f"Error writing TTL config: {e}", file=sys.stderr)
            return False

    def monitor(self, interval: int = 3600):
        """Monitor cache targets and update recommendations periodically."""
        print(f"Starting continuous monitoring (interval: {interval}s)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                print(f"\n[{datetime.now().isoformat()}] Running analysis...")
                self.analyze()
                self.save_frequency_db()

                recommendations = self.recommend()
                print(f"  Found {len(recommendations['per_file'])} cache targets")

                hot_count = sum(
                    1
                    for e in self.frequency_db.values()
                    if e.get("recommendation_category") == "hot"
                )
                warm_count = sum(
                    1
                    for e in self.frequency_db.values()
                    if e.get("recommendation_category") == "warm"
                )
                print(f"  Hot files: {hot_count}, Warm files: {warm_count}")

                self.apply()
                print(f"  Next analysis in {interval}s...")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nMonitoring stopped")
            self.save_frequency_db()

    def _get_relative_path(self, path: Path) -> str:
        """Get path relative to framework root or nearest parent."""
        try:
            return str(path.relative_to(self.framework_root.parent.parent))
        except ValueError:
            return str(path.relative_to(self.framework_root))

    def _classify_file_type(self, path: str) -> str:
        """Classify file type based on extension and location."""
        if ".agent.md" in path:
            return "agent"
        elif path.endswith(".jsonl"):
            return "knowledge"
        elif path.endswith(".json") and "plans" in path:
            return "plan"
        elif path.endswith(".json"):
            return "config"
        else:
            return "other"

    def _get_current_ttl(self, path: str) -> int:
        """Get current TTL for a file from config if it exists."""
        if not self.ttl_config_path.exists():
            return self.TTL_COLD

        try:
            with open(self.ttl_config_path, "r") as f:
                config = json.load(f)
                return config.get("per_file", {}).get(path, config.get("default_ttl_hours", self.TTL_COLD))
        except (IOError, json.JSONDecodeError):
            return self.TTL_COLD

    def print_analysis(self, analysis: Dict[str, dict]):
        """Pretty print analysis results."""
        print("\nCache Target Analysis")
        print("=" * 80)

        categories = {"hot": [], "warm": [], "cold": [], "frozen": []}

        for path, entry in sorted(analysis.items()):
            category = entry.get("recommendation_category", "unknown")
            if category in categories:
                categories[category].append((path, entry))

        for category in ["hot", "warm", "cold", "frozen"]:
            files = categories[category]
            if files:
                print(f"\n{category.upper()} FILES ({len(files)})")
                print("-" * 80)
                for path, entry in files:
                    changes_per_day = entry.get("avg_changes_per_day", 0)
                    recommended_ttl = entry.get("recommended_ttl_hours", 0)
                    print(f"  {path}")
                    print(
                        f"    Changes/day: {changes_per_day:.4f}, "
                        f"Recommended TTL: {recommended_ttl}h"
                    )

    def print_summary(self):
        """Print summary of current cache configuration."""
        if not self.ttl_config_path.exists():
            print("No TTL config generated yet")
            return

        try:
            with open(self.ttl_config_path, "r") as f:
                config = json.load(f)

            print(f"\nTTL Configuration (generated: {config.get('generated_at')})")
            print("=" * 80)
            print(f"Default TTL: {config.get('default_ttl_hours')}h")

            per_file = config.get("per_file", {})
            print(f"Per-file overrides: {len(per_file)}")

            # Group by TTL value
            by_ttl = {}
            for path, ttl in per_file.items():
                if ttl not in by_ttl:
                    by_ttl[ttl] = []
                by_ttl[ttl].append(path)

            for ttl in sorted(by_ttl.keys(), reverse=True):
                files = by_ttl[ttl]
                print(f"\n  TTL {ttl}h: {len(files)} files")
                for path in sorted(files)[:3]:
                    print(f"    - {path}")
                if len(files) > 3:
                    print(f"    ... and {len(files) - 3} more")

        except (IOError, json.JSONDecodeError) as e:
            print(f"Error reading TTL config: {e}", file=sys.stderr)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Adaptive Cache Manager for MCP Server caches"
    )
    parser.add_argument(
        "command",
        choices=["analyze", "recommend", "apply", "monitor"],
        help="Command to execute",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Monitoring interval in seconds (default: 3600)",
    )
    parser.add_argument(
        "--framework-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Framework root directory",
    )

    args = parser.parse_args()

    manager = AdaptiveCacheManager(args.framework_root)

    if args.command == "analyze":
        analysis = manager.analyze()
        manager.save_frequency_db()
        manager.print_analysis(analysis)
        print(f"\nAnalyzed {len(analysis)} cache targets")

    elif args.command == "recommend":
        recommendations = manager.recommend()
        manager.save_frequency_db()
        manager.print_analysis(manager.frequency_db)
        print(f"\nGenerated recommendations for {len(recommendations['per_file'])} files")

    elif args.command == "apply":
        if manager.apply():
            manager.print_summary()
            print("\nTTL recommendations applied successfully")

    elif args.command == "monitor":
        manager.monitor(args.interval)


if __name__ == "__main__":
    main()
