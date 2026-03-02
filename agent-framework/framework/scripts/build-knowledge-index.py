#!/usr/bin/env python3
"""Build a cross-stack knowledge index from all stack knowledge files.

Scans all stacks' docs/knowledge/ directories and creates:
1. A unified cross-stack index at framework/knowledge/cross-stack-index.jsonl
2. Updated index.md files for each stack with extracted knowledge stats
3. A knowledge manifest for the Knowledge MCP server

Usage:
    python build-knowledge-index.py                    # Build everything
    python build-knowledge-index.py --stack live-moafunk  # Single stack only
    python build-knowledge-index.py --stats            # Show stats only
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime


def count_jsonl_entries(path: Path) -> int:
    """Count non-empty lines in a JSONL file."""
    try:
        return sum(1 for line in path.read_text().splitlines() if line.strip())
    except Exception:
        return 0


def count_md_sections(path: Path) -> int:
    """Count H2 sections in a markdown file."""
    try:
        return sum(1 for line in path.read_text().splitlines() if line.startswith("## "))
    except Exception:
        return 0


def scan_knowledge_dir(knowledge_dir: Path) -> list[dict]:
    """Scan a knowledge directory and return file metadata."""
    entries = []
    if not knowledge_dir.exists():
        return entries

    for path in sorted(knowledge_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.name.startswith("."):
            continue

        rel_path = str(path.relative_to(knowledge_dir))
        size = path.stat().st_size
        modified = datetime.fromtimestamp(path.stat().st_mtime).isoformat()

        entry = {
            "file": rel_path,
            "size_bytes": size,
            "modified": modified,
        }

        if path.suffix == ".jsonl":
            entry["type"] = "jsonl"
            entry["entries"] = count_jsonl_entries(path)
        elif path.suffix == ".md":
            entry["type"] = "markdown"
            entry["sections"] = count_md_sections(path)
        else:
            entry["type"] = path.suffix.lstrip(".")

        entries.append(entry)

    return entries


def build_cross_stack_index(root: Path, stacks: list[str]) -> list[dict]:
    """Build a cross-stack knowledge index."""
    index = []

    for stack in stacks:
        knowledge_dir = root / "stacks" / stack / "docs" / "knowledge"
        entries = scan_knowledge_dir(knowledge_dir)

        for entry in entries:
            entry["stack"] = stack
            index.append(entry)

    return index


def extract_topics_from_jsonl(path: Path) -> list[str]:
    """Extract unique topics/categories from a JSONL file."""
    topics = set()
    try:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                # Common fields that indicate topic
                for key in ("type", "category", "method", "agent"):
                    if key in obj and isinstance(obj[key], str):
                        topics.add(obj[key])
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    return sorted(topics)[:20]  # Max 20 topics


def generate_stack_index(
    root: Path, stack: str, entries: list[dict]
) -> str:
    """Generate an updated index.md for a stack."""
    knowledge_dir = root / "stacks" / stack / "docs" / "knowledge"

    # Split by type
    jsonl_files = [e for e in entries if e.get("type") == "jsonl" and not e["file"].startswith("extracted-")]
    md_files = [e for e in entries if e.get("type") == "markdown" and e["file"] != "index.md"]
    extracted = [e for e in entries if e["file"].startswith("extracted-")]
    decision_files = [e for e in entries if e["file"].startswith("decisions/")]

    lines = [f"# Knowledge Index — {stack}", ""]

    # Stats
    total_entries = sum(e.get("entries", 0) for e in entries if e.get("type") == "jsonl")
    total_sections = sum(e.get("sections", 0) for e in entries if e.get("type") == "markdown")
    total_size = sum(e.get("size_bytes", 0) for e in entries)

    lines.append(f"**Stats**: {len(entries)} files, {total_entries} JSONL entries, {total_sections} markdown sections, {total_size:,} bytes total")
    lines.append("")

    # Structured Data
    if jsonl_files:
        lines.append("## Structured Data (JSONL)")
        lines.append("")
        lines.append("| File | Entries | Size |")
        lines.append("|------|---------|------|")
        for e in jsonl_files:
            lines.append(f"| `{e['file']}` | {e.get('entries', '?')} | {e['size_bytes']:,} B |")
        lines.append("")

    # Domain Knowledge
    if md_files:
        lines.append("## Domain Knowledge (Markdown)")
        lines.append("")
        lines.append("| File | Sections |")
        lines.append("|------|----------|")
        for e in md_files:
            lines.append(f"| `{e['file']}` | {e.get('sections', '?')} |")
        lines.append("")

    # Extracted Knowledge
    if extracted or decision_files:
        lines.append("## Extracted Knowledge (Auto-Generated)")
        lines.append("")
        lines.append("Automatically extracted from completed plan steps by `extract-knowledge.py`.")
        lines.append("")
        lines.append("| File | Entries | Size |")
        lines.append("|------|---------|------|")
        for e in extracted + decision_files:
            count = e.get("entries", "?")
            lines.append(f"| `{e['file']}` | {count} | {e['size_bytes']:,} B |")
        lines.append("")

    # MCP Access
    lines.append("## Querying Knowledge")
    lines.append("")
    lines.append("Use the `knowledge-search` MCP server for semantic search:")
    lines.append("```")
    lines.append(f'knowledge-search.search_knowledge(query="...", stack="{stack}")')
    lines.append(f'knowledge-search.search_decisions(query="...", stack="{stack}")')
    lines.append("knowledge-search.search_cross_stack(query=\"...\")")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def find_stacks(root: Path) -> list[str]:
    """Find all stacks with knowledge directories."""
    stacks = []
    stacks_dir = root / "stacks"
    if not stacks_dir.exists():
        return stacks
    for d in sorted(stacks_dir.iterdir()):
        if d.is_dir() and (d / "docs" / "knowledge").exists():
            stacks.append(d.name)
    return stacks


def main():
    root = Path(__file__).parent.parent.parent  # copilot-agents/

    stats_only = "--stats" in sys.argv
    target_stack = None
    for i, arg in enumerate(sys.argv):
        if arg == "--stack" and i + 1 < len(sys.argv):
            target_stack = sys.argv[i + 1]

    stacks = [target_stack] if target_stack else find_stacks(root)

    if not stacks:
        print("No stacks with knowledge directories found.")
        sys.exit(1)

    print(f"Building knowledge index for {len(stacks)} stack(s): {', '.join(stacks)}")

    all_entries = []
    for stack in stacks:
        knowledge_dir = root / "stacks" / stack / "docs" / "knowledge"
        entries = scan_knowledge_dir(knowledge_dir)
        all_entries.extend([{**e, "stack": stack} for e in entries])

        total = sum(e.get("entries", 0) for e in entries if e.get("type") == "jsonl")
        total += sum(e.get("sections", 0) for e in entries if e.get("type") == "markdown")
        size = sum(e.get("size_bytes", 0) for e in entries)

        print(f"  📚 {stack}: {len(entries)} files, {total} entries/sections, {size:,} bytes")

        if not stats_only:
            # Update stack index.md
            index_content = generate_stack_index(root, stack, entries)
            index_path = knowledge_dir / "index.md"
            index_path.write_text(index_content)
            print(f"     Updated {index_path.relative_to(root)}")

    if stats_only:
        return

    # Write cross-stack index
    cross_index_dir = root / "framework" / "knowledge"
    cross_index_dir.mkdir(parents=True, exist_ok=True)

    cross_index_path = cross_index_dir / "cross-stack-index.jsonl"
    with open(cross_index_path, "w") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n  ✅ Cross-stack index: {cross_index_path.relative_to(root)} ({len(all_entries)} entries)")

    # Write manifest
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "stacks": stacks,
        "total_files": len(all_entries),
        "total_size_bytes": sum(e.get("size_bytes", 0) for e in all_entries),
        "by_type": {},
    }

    for entry in all_entries:
        t = entry.get("type", "unknown")
        if t not in manifest["by_type"]:
            manifest["by_type"][t] = {"count": 0, "entries": 0}
        manifest["by_type"][t]["count"] += 1
        manifest["by_type"][t]["entries"] += entry.get("entries", entry.get("sections", 0))

    manifest_path = cross_index_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"  ✅ Manifest: {manifest_path.relative_to(root)}")

    print(f"\nDone. Total: {len(all_entries)} knowledge files across {len(stacks)} stacks.")


if __name__ == "__main__":
    main()
