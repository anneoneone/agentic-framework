#!/usr/bin/env python3
"""Requirements Interview — Interactive requirements gathering for greenfield stack creation.

Asks structured questions (4 phases) and outputs a RequirementsProfile JSON that
can be passed to @analyzer to generate agent recommendations without a project path.

Usage:
    python framework/scripts/requirements-interview.py
    python framework/scripts/requirements-interview.py --output requirements-profile.json
    python framework/scripts/requirements-interview.py --dry-run
    python framework/scripts/requirements-interview.py --output profile.json --create-stack

Options:
    --output FILE       Write RequirementsProfile to FILE (default: stdout)
    --dry-run           Print questions without prompting (for testing)
    --create-stack      After interview, pipe profile to task-executor.py to run @analyzer
    --stack STACK       Stack name to use with --create-stack (default: derived from project_name)
    --verbose           Show phase headers and extra guidance
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()

# ──────────────────────────────────────────────────────────────────────
# Question definitions
# ──────────────────────────────────────────────────────────────────────

PHASES = [
    {
        "name": "Phase 1 — Project Identity",
        "required": True,
        "questions": [
            {
                "key": "project_name",
                "prompt": "Project name (slug, e.g. my-iot-gateway)",
                "type": "string",
                "required": True,
                "validate": lambda v: v.replace("-", "").replace("_", "").isalnum() and len(v) >= 2,
                "error": "Use only letters, numbers, and hyphens (min 2 chars)",
            },
            {
                "key": "description",
                "prompt": "In one sentence, what does this project do?",
                "type": "string",
                "required": True,
            },
            {
                "key": "repo_path",
                "prompt": "Existing repo path to link (leave blank for embedded/greenfield)",
                "type": "string",
                "required": False,
            },
            {
                "key": "domain",
                "prompt": "Primary domain",
                "type": "choice",
                "choices": ["backend", "frontend", "firmware", "data", "infra", "fullstack", "library", "cli", "other"],
                "required": True,
            },
        ],
    },
    {
        "name": "Phase 2 — Tech Stack",
        "required": True,
        "questions": [
            {
                "key": "languages",
                "prompt": "Language(s) — comma-separated (e.g. Rust, Python)",
                "type": "list",
                "required": True,
            },
            {
                "key": "frameworks",
                "prompt": "Frameworks / runtimes (e.g. Axum, Tokio, FastAPI) [Enter to skip]",
                "type": "list",
                "required": False,
            },
            {
                "key": "storage",
                "prompt": "Databases / storage (e.g. PostgreSQL, Redis) [Enter to skip]",
                "type": "list",
                "required": False,
            },
            {
                "key": "integrations",
                "prompt": "External protocols / APIs (e.g. OCPP 2.0, gRPC) [Enter to skip]",
                "type": "string",
                "required": False,
            },
        ],
    },
    {
        "name": "Phase 3 — Architecture  (recommended, press Enter to skip any)",
        "required": False,
        "questions": [
            {
                "key": "architecture",
                "prompt": "Architecture style",
                "type": "choice",
                "choices": ["microservice", "monolith", "library", "firmware", "cli", "event-driven", "other"],
                "required": False,
            },
            {
                "key": "workstreams",
                "prompt": "Main modules / workstreams — comma-separated (e.g. WebSocket handler, DB layer)",
                "type": "list",
                "required": False,
            },
            {
                "key": "testing",
                "prompt": "Testing strategy — comma-separated",
                "type": "multichoice",
                "choices": ["unit", "integration", "e2e", "property-based", "load", "manual"],
                "required": False,
            },
        ],
    },
    {
        "name": "Phase 4 — Team & Scale  (optional)",
        "required": False,
        "questions": [
            {
                "key": "team_size",
                "prompt": "Team size",
                "type": "choice",
                "choices": ["solo", "small", "medium", "large"],
                "required": False,
            },
            {
                "key": "shared_agents",
                "prompt": "Existing shared agents to reuse — comma-separated (e.g. @ocpp-protocol) [Enter to skip]",
                "type": "list",
                "required": False,
            },
        ],
    },
]

# ──────────────────────────────────────────────────────────────────────
# Prompt helpers
# ──────────────────────────────────────────────────────────────────────

def ask_string(prompt: str, required: bool) -> str | None:
    while True:
        value = input(f"  {prompt}: ").strip()
        if value:
            return value
        if not required:
            return None
        print("  ↳ This field is required.")


def ask_choice(prompt: str, choices: list[str], required: bool) -> str | None:
    display = " / ".join(choices)
    while True:
        value = input(f"  {prompt} [{display}]: ").strip().lower()
        if value in choices:
            return value
        if not value and not required:
            return None
        if not value and required:
            print(f"  ↳ Required. Choose one of: {display}")
            continue
        # Partial match
        matches = [c for c in choices if c.startswith(value)]
        if len(matches) == 1:
            return matches[0]
        print(f"  ↳ Unknown choice. Options: {display}")


def ask_list(prompt: str, required: bool) -> list[str] | None:
    value = input(f"  {prompt}: ").strip()
    if not value:
        if required:
            print("  ↳ This field is required.")
            return ask_list(prompt, required)
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def ask_multichoice(prompt: str, choices: list[str], required: bool) -> list[str] | None:
    display = ", ".join(choices)
    print(f"  Options: {display}")
    value = input(f"  {prompt} [comma-separated, Enter to skip]: ").strip().lower()
    if not value:
        return None
    selected = []
    for item in value.split(","):
        item = item.strip()
        if item in choices:
            selected.append(item)
        else:
            matches = [c for c in choices if c.startswith(item)]
            if len(matches) == 1:
                selected.append(matches[0])
    return selected or None


# ──────────────────────────────────────────────────────────────────────
# Interview runner
# ──────────────────────────────────────────────────────────────────────

def run_interview(dry_run: bool = False, verbose: bool = False) -> dict:
    profile: dict = {}

    print("\n🤖 Requirements Interview")
    print("   I'll ask a few questions to design the right agents for your stack.")
    print("   Press Enter to skip optional questions.\n")

    for phase in PHASES:
        if verbose or True:
            print(f"── {phase['name']} ──")

        for q in phase["questions"]:
            if dry_run:
                print(f"  [dry-run] Would ask: {q['prompt']}")
                continue

            qtype = q["type"]
            required = q.get("required", False)
            validate = q.get("validate")

            while True:
                if qtype == "string":
                    value = ask_string(q["prompt"], required)
                elif qtype == "choice":
                    value = ask_choice(q["prompt"], q["choices"], required)
                elif qtype == "list":
                    value = ask_list(q["prompt"], required)
                elif qtype == "multichoice":
                    value = ask_multichoice(q["prompt"], q["choices"], required)
                else:
                    value = ask_string(q["prompt"], required)

                if value is not None and validate and not validate(value):
                    print(f"  ↳ {q.get('error', 'Invalid value.')}")
                    continue
                break

            if value is not None:
                profile[q["key"]] = value

        print()

    # Derive stack_type from repo_path answer
    if profile.get("repo_path"):
        profile["stack_type"] = "linked"
    else:
        profile["stack_type"] = "embedded"

    return profile


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Interactive requirements interview for stack creation")
    parser.add_argument("--output", "-o", help="Write profile JSON to this file (default: stdout)")
    parser.add_argument("--dry-run", action="store_true", help="Print questions without prompting")
    parser.add_argument("--create-stack", action="store_true", help="Run @analyzer after interview via task-executor.py")
    parser.add_argument("--stack", help="Stack name for --create-stack (default: derived from project_name)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show extra guidance")
    args = parser.parse_args()

    profile = run_interview(dry_run=args.dry_run, verbose=args.verbose)

    if args.dry_run:
        print("(dry-run complete — no profile generated)")
        return

    output = json.dumps(profile, indent=2)

    if args.output:
        Path(args.output).write_text(output)
        print(f"✅ Requirements profile written to {args.output}")
    else:
        print("\n── RequirementsProfile ──")
        print(output)

    if args.create_stack:
        stack = args.stack or profile.get("project_name", "new-stack")
        profile_path = args.output or "requirements-profile.json"
        if not args.output:
            Path(profile_path).write_text(output)

        task_description = (
            f"--interview mode: analyze requirements profile and recommend agents. "
            f"Profile: {json.dumps(profile)}"
        )
        cmd = [
            sys.executable,
            str(ROOT / "framework" / "scripts" / "task-executor.py"),
            "--stack", stack,
            "--agent", "@analyzer",
            "--task", task_description,
        ]
        print(f"\n→ Running @analyzer via task-executor.py for stack '{stack}'...")
        subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
