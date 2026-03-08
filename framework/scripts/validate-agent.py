#!/usr/bin/env python3
"""Validate agent .agent.md files against the frontmatter schema.

Usage:
    python framework/scripts/validate-agent.py --all
    python framework/scripts/validate-agent.py --stack live-moafunk
    python framework/scripts/validate-agent.py path/to/agent.agent.md
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()
SCHEMA_PATH = ROOT / "framework" / "schemas" / "agent-frontmatter.schema.json"

# Required markdown sections (H2 headings)
REQUIRED_SECTIONS = {"role", "scope", "boundaries"}


def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from agent markdown."""
    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    fm_text = content[3:end].strip()
    body = content[end + 3:].strip()

    data = {}
    current_key = None
    current_list = None

    for line in fm_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # List item under current key
        if stripped.startswith("- ") and current_key:
            if current_list is None:
                current_list = []
                data[current_key] = current_list
            current_list.append(stripped[2:].strip().strip("'\""))
            continue

        # Nested key (indented)
        indent_match = re.match(r"^(\s+)(\w[\w-]*):\s*(.*)$", line)
        if indent_match:
            parent = current_key
            key = indent_match.group(2)
            value = indent_match.group(3).strip().strip("'\"")

            if isinstance(data.get(parent), dict):
                if value:
                    data[parent][key] = value
                else:
                    data[parent][key] = []
                    current_key = parent  # keep parent for nested lists
                    current_list = data[parent][key] if not value else None
            continue

        # Top-level key-value
        match = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip().strip("'\"")
            current_key = key
            current_list = None

            if not value:
                # Could be a map or list — next lines will tell
                data[key] = {}
            elif value.startswith("[") and value.endswith("]"):
                # Inline list
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                data[key] = items
            else:
                data[key] = value

    return data, body


def validate_frontmatter(fm: dict, schema: dict) -> list[str]:
    """Validate frontmatter against schema. Returns list of error messages."""
    errors = []

    # Check required fields
    for field in schema.get("required", []):
        if field not in fm:
            errors.append(f"Missing required field: {field}")

    props = schema.get("properties", {})

    for key, value in fm.items():
        if key not in props:
            errors.append(f"Unknown field: {key}")
            continue

        prop_schema = props[key]
        expected_type = prop_schema.get("type")

        # Type check
        if expected_type == "string" and not isinstance(value, str):
            errors.append(f"{key}: expected string, got {type(value).__name__}")
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(f"{key}: expected array, got {type(value).__name__}")
        elif expected_type == "integer" and not isinstance(value, int):
            try:
                int(value)
            except (ValueError, TypeError):
                errors.append(f"{key}: expected integer, got {type(value).__name__}")
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(f"{key}: expected object, got {type(value).__name__}")

        # Pattern check for strings
        if expected_type == "string" and isinstance(value, str):
            pattern = prop_schema.get("pattern")
            if pattern and not re.match(pattern, value):
                errors.append(f"{key}: '{value}' doesn't match pattern {pattern}")

            min_len = prop_schema.get("minLength")
            if min_len and len(value) < min_len:
                errors.append(f"{key}: too short (min {min_len} chars)")

            max_len = prop_schema.get("maxLength")
            if max_len and len(value) > max_len:
                errors.append(f"{key}: too long (max {max_len} chars)")

        # Array checks
        if expected_type == "array" and isinstance(value, list):
            min_items = prop_schema.get("minItems")
            if min_items and len(value) < min_items:
                errors.append(f"{key}: needs at least {min_items} items, got {len(value)}")

            max_items = prop_schema.get("maxItems")
            if max_items and len(value) > max_items:
                errors.append(f"{key}: max {max_items} items, got {len(value)}")

    return errors


def validate_body(body: str) -> list[str]:
    """Check that required markdown sections exist."""
    warnings = []

    # Extract H2 headings
    headings = {h.strip().lower() for h in re.findall(r"^##\s+(.+)$", body, re.MULTILINE)}

    # Also check for headings that start with the required word
    found = set()
    for required in REQUIRED_SECTIONS:
        for heading in headings:
            if heading.startswith(required) or required in heading:
                found.add(required)
                break

    missing = REQUIRED_SECTIONS - found
    for section in missing:
        warnings.append(f"Missing recommended section: ## {section.title()}")

    return warnings


def validate_file(path: Path, schema: dict) -> tuple[list[str], list[str]]:
    """Validate a single agent file. Returns (errors, warnings)."""
    errors = []
    warnings = []

    try:
        content = path.read_text(encoding="utf-8")
    except (IOError, OSError) as e:
        return [f"Cannot read file: {e}"], []

    fm, body = parse_frontmatter(content)

    if fm is None:
        errors.append("No YAML frontmatter found (must start with ---)")
        return errors, warnings

    # Check name matches filename
    expected_name = path.stem.replace(".agent", "")
    if fm.get("name") and fm["name"] != expected_name:
        warnings.append(f"name '{fm['name']}' doesn't match filename '{expected_name}'")

    errors.extend(validate_frontmatter(fm, schema))
    warnings.extend(validate_body(body))

    return errors, warnings


def find_agent_files(stack: str = None) -> list[Path]:
    """Find all agent.md files."""
    files = []

    # Framework agents
    for subdir in ["common-agents", "shared-agents"]:
        agent_dir = ROOT / "framework" / "core" / subdir
        if agent_dir.exists():
            files.extend(agent_dir.glob("*.agent.md"))

    # Claude Code agents
    claude_agents = ROOT / ".claude" / "agents"
    if claude_agents.exists():
        files.extend(claude_agents.glob("*.agent.md"))

    # Stack agents
    stacks_dir = ROOT / "stacks"
    if stacks_dir.exists():
        if stack:
            stack_agents = stacks_dir / stack / "agents"
            if stack_agents.exists():
                files.extend(stack_agents.glob("*.agent.md"))
        else:
            for stack_dir in stacks_dir.iterdir():
                if stack_dir.is_dir():
                    agents_dir = stack_dir / "agents"
                    if agents_dir.exists():
                        files.extend(agents_dir.glob("*.agent.md"))

    # Deduplicate (symlinks)
    seen = set()
    unique = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)

    return sorted(unique)


def main():
    schema = load_schema()

    # Parse args
    if len(sys.argv) < 2:
        print("Usage: validate-agent.py [--all | --stack NAME | FILE]")
        sys.exit(1)

    if sys.argv[1] == "--all":
        files = find_agent_files()
    elif sys.argv[1] == "--stack":
        if len(sys.argv) < 3:
            print("Missing stack name")
            sys.exit(1)
        files = find_agent_files(stack=sys.argv[2])
    else:
        files = [Path(sys.argv[1])]

    if not files:
        print("No agent files found")
        sys.exit(1)

    total_errors = 0
    total_warnings = 0

    for path in files:
        rel_path = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        errors, warnings = validate_file(path, schema)

        if errors or warnings:
            print(f"\n{rel_path}")
            for e in errors:
                print(f"  ERROR: {e}")
                total_errors += 1
            for w in warnings:
                print(f"  WARN:  {w}")
                total_warnings += 1
        else:
            print(f"  OK: {rel_path}")

    print(f"\nValidated {len(files)} agents: {total_errors} errors, {total_warnings} warnings")

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
