#!/usr/bin/env python3
"""Validate .agent.md files against the frontmatter schema.

Checks:
1. YAML frontmatter presence and validity
2. Required fields (name, description, version)
3. Optional but recommended fields (keywords, scope)
4. Section structure (required markdown sections)
5. File naming consistency (name must match filename)
6. Line count range (80-200 recommended)

Usage:
    python validate-agent.py <path-to-agent.md>
    python validate-agent.py --all                  # Validate all agents
    python validate-agent.py --stack live-moafunk    # Validate one stack
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional


REQUIRED_SECTIONS = [
    "role",           # OR "identity" OR "your role" OR "expertise"
    "scope",          # OR "your expertise" OR "responsibilities"
    "key files",      # OR "primary code" OR "project context"
]

RECOMMENDED_SECTIONS = [
    "patterns",       # OR "common patterns"
    "failure modes",  # OR "typical failure modes"
    "output",         # OR "output format" OR "what you should output"
    "efficiency",     # OR "efficiency guidelines" OR "token efficiency"
]

ROLE_ALIASES = {
    "role": ["role", "your role", "identity"],
    "scope": ["scope", "your expertise", "expertise", "responsibilities"],
    "key files": ["key files", "primary code", "project context"],
}

VALID_STATUSES = {"pending", "in-progress", "completed", "blocked", "skipped"}


class ValidationResult:
    def __init__(self, path: str):
        self.path = path
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def print_report(self):
        name = Path(self.path).name
        if self.is_valid and not self.warnings:
            print(f"  ✅ {name}")
            return

        if self.errors:
            print(f"  ❌ {name}")
            for e in self.errors:
                print(f"     ERROR: {e}")
        else:
            print(f"  ⚠️  {name}")

        for w in self.warnings:
            print(f"     WARN:  {w}")

        for i in self.info:
            print(f"     INFO:  {i}")


def parse_frontmatter(content: str) -> tuple[Optional[dict], str]:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    frontmatter_text = content[3:end].strip()
    body = content[end + 3:].strip()

    # Simple YAML parser for flat frontmatter (no external deps)
    data = {}
    current_key = None
    current_list = None

    for line in frontmatter_text.split("\n"):
        line = line.rstrip()
        if not line:
            continue

        # List item
        if line.startswith("  - ") and current_key:
            if current_list is None:
                current_list = []
                data[current_key] = current_list
            current_list.append(line.strip("- ").strip().strip("'\""))
            continue

        # Key-value pair
        match = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if match:
            current_key = match.group(1)
            value = match.group(2).strip().strip("'\"")
            current_list = None

            if value.startswith("[") and value.endswith("]"):
                # Inline array: [item1, item2]
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                data[current_key] = items
            elif value:
                data[current_key] = value
            # If empty value, might be followed by list items
            continue

    return data, body


def validate_agent(path: Path) -> ValidationResult:
    """Validate a single agent file."""
    result = ValidationResult(str(path))

    content = path.read_text()
    lines = content.split("\n")
    line_count = len(lines)

    # 1. Check frontmatter
    frontmatter, body = parse_frontmatter(content)

    if frontmatter is None:
        result.error("Missing YAML frontmatter (--- block at top of file)")
        # Still check body structure
    else:
        # Required fields
        if "name" not in frontmatter:
            result.error("Missing required field: name")
        else:
            name = frontmatter["name"]
            expected_name = path.stem.replace(".agent", "")
            if name != expected_name:
                result.error(f"name '{name}' doesn't match filename '{expected_name}'")
            if not re.match(r"^[a-z][a-z0-9-]*$", name):
                result.error(f"name '{name}' must be lowercase kebab-case")

        if "description" not in frontmatter:
            result.error("Missing required field: description")
        elif len(frontmatter["description"]) < 10:
            result.warn("description is very short (< 10 chars)")
        elif len(frontmatter["description"]) > 200:
            result.warn("description exceeds 200 chars")

        if "version" not in frontmatter:
            result.error("Missing required field: version")
        elif not re.match(r"^\d+\.\d+$", str(frontmatter["version"])):
            result.error(f"version '{frontmatter['version']}' must be major.minor format (e.g., '1.0')")

        # Recommended fields
        if "keywords" not in frontmatter:
            result.warn("Missing recommended field: keywords (needed for agent discovery)")
        else:
            kw = frontmatter["keywords"]
            if isinstance(kw, list) and len(kw) < 3:
                result.warn(f"Only {len(kw)} keywords — recommend at least 3 for routing accuracy")

        if "scope" not in frontmatter:
            result.warn("Missing recommended field: scope (primary/out_of_scope)")

    # 2. Check section structure
    body_lower = body.lower() if body else ""
    headings = [line.strip().lower().lstrip("#").strip() for line in lines if line.strip().startswith("#")]

    for section_name, aliases in ROLE_ALIASES.items():
        found = any(alias in headings for alias in aliases)
        if not found:
            result.warn(f"Missing section: {section_name} (or aliases: {', '.join(aliases)})")

    for section in RECOMMENDED_SECTIONS:
        if section not in body_lower:
            result.info.append(f"Consider adding section: {section}")

    # 3. Check line count
    if line_count < 30:
        result.warn(f"File is short ({line_count} lines) — may be too vague")
    elif line_count > 250:
        result.warn(f"File is long ({line_count} lines) — consider using {{reference:}} to externalize content")

    # 4. Check for Key Files table
    if "key files" in body_lower or "primary code" in body_lower:
        if "|" not in body:
            result.warn("Key Files section exists but doesn't use a table format")

    return result


def find_agents(root: Path, stack: Optional[str] = None) -> list[Path]:
    """Find all .agent.md files."""
    agents = []

    if stack:
        pattern = f"stacks/{stack}/.github/agents/*.agent.md"
    else:
        pattern = "**/*.agent.md"

    for path in sorted(root.glob(pattern)):
        # Skip symlinks (they point to common agents validated separately)
        if not path.is_symlink():
            agents.append(path)

    return agents


def main():
    root = Path(__file__).parent.parent.parent  # copilot-agents/

    if len(sys.argv) < 2:
        print("Usage: validate-agent.py <path> | --all | --stack <name>")
        sys.exit(1)

    if sys.argv[1] == "--all":
        agents = find_agents(root)
        # Also include framework agents
        agents += list(root.glob("framework/core/**/*.agent.md"))
    elif sys.argv[1] == "--stack":
        stack = sys.argv[2] if len(sys.argv) > 2 else None
        if not stack:
            print("Usage: validate-agent.py --stack <stack-name>")
            sys.exit(1)
        agents = find_agents(root, stack)
    else:
        agents = [Path(sys.argv[1])]

    if not agents:
        print("No agent files found.")
        sys.exit(1)

    print(f"Validating {len(agents)} agent(s)...\n")

    total_errors = 0
    total_warnings = 0

    for agent_path in agents:
        result = validate_agent(agent_path)
        result.print_report()
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)

    print(f"\nSummary: {len(agents)} agents, {total_errors} errors, {total_warnings} warnings")

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
