#!/usr/bin/env python3
"""Validate and update agent .agent.md files to match the current template.

Checks frontmatter for required/recommended fields and body for required sections.
Can auto-fix missing recommended frontmatter fields with sensible defaults.

Usage:
    python framework/scripts/update-agents.py --all
    python framework/scripts/update-agents.py --stack live-moafunk
    python framework/scripts/update-agents.py --all --fix
    python framework/scripts/update-agents.py --all --fix --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()

REQUIRED_FIELDS = {"name", "description"}
RECOMMENDED_FIELDS = {"version", "keywords", "scope", "mcp_servers"}

# Required body sections and their accepted aliases
REQUIRED_SECTIONS = {
    "role": {"role", "your role", "identity"},
    "scope": {"scope", "your expertise", "expertise"},
}


def parse_frontmatter(content: str) -> tuple[dict | None, str, int, int]:
    """Parse YAML frontmatter from agent markdown.

    Returns (frontmatter_dict, body, fm_start_offset, fm_end_offset).
    Offsets point to the content between the --- markers (exclusive).
    """
    if not content.startswith("---"):
        return None, content, -1, -1

    end = content.find("---", 3)
    if end == -1:
        return None, content, -1, -1

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
                    current_list = data[parent][key]
            continue

        # Top-level key-value
        match = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip().strip("'\"")
            current_key = key
            current_list = None

            if not value:
                data[key] = {}
            elif value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                data[key] = items
            else:
                data[key] = value

    return data, body, 3, end


def check_required_fields(fm: dict) -> list[str]:
    """Return list of missing required fields."""
    return [f for f in sorted(REQUIRED_FIELDS) if f not in fm]


def check_recommended_fields(fm: dict) -> list[str]:
    """Return list of missing recommended fields."""
    return [f for f in sorted(RECOMMENDED_FIELDS) if f not in fm]


def check_required_sections(body: str) -> list[str]:
    """Return list of missing required sections."""
    # Extract H1 and H2 headings
    headings = {h.strip().lower() for h in re.findall(r"^#{1,2}\s+(.+)$", body, re.MULTILINE)}

    missing = []
    for section_name, aliases in sorted(REQUIRED_SECTIONS.items()):
        found = False
        for heading in headings:
            for alias in aliases:
                if heading == alias or heading.startswith(alias):
                    found = True
                    break
            if found:
                break
        if not found:
            missing.append(section_name)

    return missing


def build_fix_lines(missing_recommended: list[str]) -> list[str]:
    """Build YAML lines to append for missing recommended fields."""
    lines = []
    for field in missing_recommended:
        if field == "version":
            lines.append('version: "1.0"')
        elif field == "keywords":
            lines.append("keywords: []")
        elif field == "scope":
            # scope is a complex object, skip auto-adding
            continue
        elif field == "mcp_servers":
            lines.append("mcp_servers:")
            lines.append("  - memento-knowledge")
    return lines


def apply_fix(content: str, missing_recommended: list[str]) -> tuple[str, list[str]]:
    """Apply fixes to content. Returns (new_content, list_of_changes)."""
    fix_lines = build_fix_lines(missing_recommended)
    if not fix_lines:
        return content, []

    # Find the closing --- of frontmatter
    end = content.find("---", 3)
    if end == -1:
        return content, []

    # Insert new fields before the closing ---
    insert_text = "\n".join(fix_lines) + "\n"
    # Ensure there's a newline before our insertion
    before = content[:end]
    if not before.endswith("\n"):
        before += "\n"

    new_content = before + insert_text + content[end:]

    changes = []
    for field in missing_recommended:
        if field == "version":
            changes.append('Added version: "1.0"')
        elif field == "keywords":
            changes.append("Added keywords: [] (fill in manually)")
        elif field == "mcp_servers":
            changes.append("Added mcp_servers: [memento-knowledge]")
        # scope is skipped

    return new_content, changes


def process_file(
    path: Path,
    fix: bool = False,
    dry_run: bool = False,
) -> tuple[bool, list[str]]:
    """Process a single agent file. Returns (has_issues, output_lines)."""
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path

    output = [f"Agent: {rel}"]

    try:
        content = path.read_text(encoding="utf-8")
    except (IOError, OSError) as e:
        output.append(f"  \u2717 Cannot read file: {e}")
        return True, output

    fm, body, _, _ = parse_frontmatter(content)

    if fm is None:
        output.append("  \u2717 No YAML frontmatter found (must start with ---)")
        return True, output

    has_issues = False

    # 1. Required fields
    missing_required = check_required_fields(fm)
    if missing_required:
        output.append(f"  \u2717 Missing required: {', '.join(missing_required)}")
        has_issues = True
    else:
        output.append("  \u2713 Required fields OK")

    # 2. Recommended fields
    missing_recommended = check_recommended_fields(fm)
    if missing_recommended:
        output.append(f"  \u26a0 Missing recommended: {', '.join(missing_recommended)}")
        has_issues = True

        if fix:
            new_content, changes = apply_fix(content, missing_recommended)
            if changes:
                if dry_run:
                    for change in changes:
                        output.append(f"    [dry-run] Would apply: {change}")
                else:
                    path.write_text(new_content, encoding="utf-8")
                    for change in changes:
                        output.append(f"    \u2713 Fixed: {change}")
    else:
        output.append("  \u2713 Recommended fields OK")

    # 3. Required sections
    missing_sections = check_required_sections(body)
    if missing_sections:
        labels = [REQUIRED_SECTIONS[s] for s in missing_sections]
        aliases_str = ", ".join(
            f"{s} (aliases: {', '.join(sorted(REQUIRED_SECTIONS[s]))})"
            for s in missing_sections
        )
        output.append(f"  \u26a0 Missing required sections: {aliases_str}")
        has_issues = True
    else:
        output.append("  \u2713 Required sections OK")

    return has_issues, output


def find_agent_files(stack: str | None = None) -> list[Path]:
    """Find all agent.md files in the standard locations."""
    files: list[Path] = []

    # .claude/agents/
    claude_agents = ROOT / ".claude" / "agents"
    if claude_agents.exists():
        files.extend(claude_agents.glob("*.agent.md"))

    # framework/core/common-agents/ and shared-agents/
    for subdir in ["common-agents", "shared-agents"]:
        agent_dir = ROOT / "framework" / "core" / subdir
        if agent_dir.exists():
            files.extend(agent_dir.glob("*.agent.md"))

    # stacks/*/agents/
    stacks_dir = ROOT / "stacks"
    if stacks_dir.exists():
        if stack:
            stack_agents = stacks_dir / stack / "agents"
            if stack_agents.exists():
                files.extend(stack_agents.glob("*.agent.md"))
        else:
            for stack_dir in sorted(stacks_dir.iterdir()):
                if stack_dir.is_dir():
                    agents_dir = stack_dir / "agents"
                    if agents_dir.exists():
                        files.extend(agents_dir.glob("*.agent.md"))

    # Deduplicate symlinks
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)

    return sorted(unique)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and update agent .agent.md files to match the current template."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Check all agent files")
    group.add_argument("--stack", metavar="STACKNAME", help="Check agents in one stack only")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-add missing recommended fields with sensible defaults",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what --fix would change without writing files",
    )

    args = parser.parse_args()

    if args.dry_run and not args.fix:
        parser.error("--dry-run requires --fix")

    files = find_agent_files(stack=args.stack)

    if not files:
        print("No agent files found.")
        sys.exit(1)

    total_issues = 0

    for path in files:
        has_issues, output = process_file(path, fix=args.fix, dry_run=args.dry_run)
        for line in output:
            print(line)
        print()
        if has_issues:
            total_issues += 1

    summary = f"Checked {len(files)} agent(s): {total_issues} with issues"
    if args.fix and not args.dry_run:
        summary += " (fixes applied where possible)"
    elif args.dry_run:
        summary += " (dry-run, no files modified)"
    print(summary)

    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
