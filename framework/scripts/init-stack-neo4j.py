#!/usr/bin/env python3
"""Init Stack Neo4j — Initialize a stack's knowledge graph presence.

Creates the Stack node, Agent nodes, initial relationships, and optionally
imports existing knowledge files. Idempotent (safe to run multiple times).

For fresh stacks, a --profile flag converts RequirementsProfile data into
seed knowledge nodes (decisions, learnings, env vars).

Usage:
    python framework/scripts/init-stack-neo4j.py --stack STACKNAME
    python framework/scripts/init-stack-neo4j.py --stack STACKNAME --profile path/to/profile.json
    python framework/scripts/init-stack-neo4j.py --all
    python framework/scripts/init-stack-neo4j.py --check
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()
STACKS_DIR = ROOT / "stacks"
MEMENTO_DIR = ROOT / "framework" / "mcp-servers" / "memento-knowledge"

# Add memento-knowledge to path for imports
sys.path.insert(0, str(MEMENTO_DIR))


def ok(msg: str):
    print(f"  \033[32m✓\033[0m  {msg}")


def warn(msg: str):
    print(f"  \033[33m⚠\033[0m  {msg}")


def fail(msg: str):
    print(f"  \033[31m✗\033[0m  {msg}")


def step(msg: str):
    print(f"\n\033[1m── {msg} ──\033[0m")


def load_stack_config(stack_dir: Path) -> dict:
    """Load .stack.json metadata. Returns empty dict if not present."""
    config_path = stack_dir / ".stack.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def parse_agents(stack_dir: Path) -> list[dict]:
    """Parse agent files from a stack's agents/ directory."""
    agents_dir = stack_dir / "agents"
    if not agents_dir.exists():
        return []

    agents = []
    for f in sorted(agents_dir.glob("*.agent.md")):
        agent_name = f.stem.replace(".agent", "")
        description = ""

        try:
            content = f.read_text()
            if content.startswith("---"):
                end = content.index("---", 3)
                frontmatter = content[3:end]
                for line in frontmatter.split("\n"):
                    if line.strip().startswith("description:"):
                        description = line.split(":", 1)[1].strip().strip("\"'")
                        break
        except Exception:
            pass

        agents.append({
            "name": agent_name,
            "description": description,
            "source_file": f.name,
        })

    return agents


def connect_neo4j():
    """Connect to Neo4j. Returns (GraphManager, import_stack) or (None, None)."""
    try:
        from graph import GraphManager
        from import_knowledge import import_stack

        graph = GraphManager(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )
        return graph, import_stack
    except Exception as e:
        return None, None


def create_pending_marker(stack_dir: Path):
    """Create .neo4j-init-pending marker file."""
    marker = stack_dir / ".neo4j-init-pending"
    marker.touch()


def remove_pending_marker(stack_dir: Path):
    """Remove .neo4j-init-pending marker file if it exists."""
    marker = stack_dir / ".neo4j-init-pending"
    if marker.exists():
        marker.unlink()


def has_pending_marker(stack_dir: Path) -> bool:
    return (stack_dir / ".neo4j-init-pending").exists()


def seed_from_profile(graph, stack: str, profile: dict) -> dict:
    """Convert RequirementsProfile into seed knowledge nodes."""
    from graph import generate_id

    stats = {"decisions": 0, "learnings": 0, "env_vars": 0}
    now = datetime.now(timezone.utc).isoformat()
    stack_id = f"stack_{stack}"

    # Decision: tech stack
    languages = profile.get("languages", [])
    frameworks = profile.get("frameworks", [])
    if languages:
        tech_parts = []
        if languages:
            tech_parts.append(", ".join(languages))
        if frameworks:
            tech_parts.append(", ".join(frameworks))
        content = f"Stack '{stack}' tech stack: {' + '.join(tech_parts)}"
        node_id = generate_id("Decision", stack)
        graph.create_node("Decision", {
            "id": node_id,
            "content": content,
            "stack": stack,
            "agent": "@analyzer",
            "created_at": now,
        })
        graph.create_relationship(node_id, stack_id, "BELONGS_TO")
        stats["decisions"] += 1

    # Decision: architecture and domain
    architecture = profile.get("architecture", "")
    domain = profile.get("domain", "")
    if architecture or domain:
        parts = []
        if domain:
            parts.append(f"domain: {domain}")
        if architecture:
            parts.append(f"architecture: {architecture}")
        content = f"Stack '{stack}' — {', '.join(parts)}"
        node_id = generate_id("Decision", stack)
        graph.create_node("Decision", {
            "id": node_id,
            "content": content,
            "stack": stack,
            "agent": "@analyzer",
            "created_at": now,
        })
        graph.create_relationship(node_id, stack_id, "BELONGS_TO")
        stats["decisions"] += 1

    # Learning: storage and integrations
    storage = profile.get("storage", [])
    integrations = profile.get("integrations", "")
    if storage or integrations:
        parts = []
        if storage:
            parts.append(f"storage: {', '.join(storage)}")
        if integrations:
            parts.append(f"integrations: {integrations}")
        content = f"Stack '{stack}' infrastructure — {'; '.join(parts)}"
        node_id = generate_id("Learning", stack)
        graph.create_node("Learning", {
            "id": node_id,
            "content": content,
            "category": "architecture",
            "stack": stack,
            "agent": "@analyzer",
            "created_at": now,
        })
        graph.create_relationship(node_id, stack_id, "BELONGS_TO")
        stats["learnings"] += 1

    # Learning: testing strategy
    testing = profile.get("testing", [])
    if testing:
        content = f"Stack '{stack}' testing strategy: {', '.join(testing)}"
        node_id = generate_id("Learning", stack)
        graph.create_node("Learning", {
            "id": node_id,
            "content": content,
            "category": "testing",
            "stack": stack,
            "agent": "@analyzer",
            "created_at": now,
        })
        graph.create_relationship(node_id, stack_id, "BELONGS_TO")
        stats["learnings"] += 1

    # EnvVar nodes for known databases
    db_env_map = {
        "PostgreSQL": ("DATABASE_URL", "PostgreSQL connection string"),
        "MySQL": ("DATABASE_URL", "MySQL connection string"),
        "Redis": ("REDIS_URL", "Redis connection URL"),
        "MongoDB": ("MONGODB_URI", "MongoDB connection URI"),
        "SQLite": ("DATABASE_PATH", "SQLite database file path"),
    }
    for db in storage:
        if db in db_env_map:
            var_name, purpose = db_env_map[db]
            node_id = generate_id("EnvVar", stack)
            graph.create_node("EnvVar", {
                "id": node_id,
                "name": var_name,
                "purpose": purpose,
                "value": "",
                "stack": stack,
                "content": f"{var_name}: {purpose}",
                "created_at": now,
            })
            graph.create_relationship(node_id, stack_id, "BELONGS_TO")
            stats["env_vars"] += 1

    return stats


def init_stack(stack_name: str, profile_path: str = None, verbose: bool = False) -> dict:
    """Initialize a stack's Neo4j knowledge graph presence.

    Returns stats dict with results or error info.
    """
    stack_dir = STACKS_DIR / stack_name
    if not stack_dir.is_dir():
        fail(f"Stack directory not found: {stack_dir}")
        return {"status": "error", "reason": "stack_not_found"}

    # Load metadata
    config = load_stack_config(stack_dir)
    metadata = {
        "description": config.get("description", ""),
        "type": config.get("type", ""),
        "repo_path": config.get("repo_path", ""),
        "created_at": config.get("created_at", ""),
    }

    # Parse agents
    agents = parse_agents(stack_dir)
    if verbose:
        ok(f"Found {len(agents)} agents: {', '.join(a['name'] for a in agents)}")

    # Connect to Neo4j
    graph, import_stack_fn = connect_neo4j()
    if graph is None:
        warn(f"Neo4j unavailable — creating .neo4j-init-pending marker")
        create_pending_marker(stack_dir)
        return {"status": "deferred", "reason": "neo4j_unavailable"}

    try:
        # Initialize stack graph
        stats = graph.init_stack_graph(stack_name, metadata, agents)
        if stats["stack_created"]:
            ok(f"Created Stack node '{stack_name}'")
        elif stats["stack_updated"]:
            ok(f"Updated Stack node '{stack_name}'")

        if stats["agents_created"] > 0:
            ok(f"Created {stats['agents_created']} Agent nodes")
        if stats["agents_existing"] > 0 and verbose:
            ok(f"{stats['agents_existing']} Agent nodes already existed")

        # Seed from profile if provided (fresh stacks)
        if profile_path:
            try:
                profile = json.loads(Path(profile_path).read_text())
                seed_stats = seed_from_profile(graph, stack_name, profile)
                stats["seed"] = seed_stats
                ok(f"Seeded from profile: {seed_stats['decisions']} decisions, "
                   f"{seed_stats['learnings']} learnings, {seed_stats['env_vars']} env vars")
            except Exception as e:
                warn(f"Profile seed failed: {e}")
                stats["seed_error"] = str(e)

        # Import existing knowledge files
        knowledge_dir = stack_dir / "docs" / "knowledge"
        if knowledge_dir.exists():
            jsonl_count = len(list(knowledge_dir.glob("*.jsonl")))
            md_count = len([f for f in knowledge_dir.glob("*.md") if f.name != "index.md"])

            if jsonl_count > 0 or md_count > 0:
                import_stats = import_stack_fn(graph, ROOT, stack_name)
                stats["import"] = import_stats
                ok(f"Imported knowledge: {import_stats.get('nodes_created', 0)} nodes, "
                   f"{import_stats.get('relationships_created', 0)} relationships")
            elif verbose:
                ok("No knowledge files to import yet")

        # Success — remove pending marker
        remove_pending_marker(stack_dir)
        stats["status"] = "ok"
        graph.close()
        return stats

    except Exception as e:
        fail(f"Init failed: {e}")
        create_pending_marker(stack_dir)
        try:
            graph.close()
        except Exception:
            pass
        return {"status": "error", "reason": str(e)}


def check_stacks(verbose: bool = False) -> int:
    """Check Neo4j init status for all stacks. Returns count of pending inits."""
    pending = 0

    graph, _ = connect_neo4j()
    neo4j_available = graph is not None

    for stack_dir in sorted(STACKS_DIR.iterdir()):
        if not stack_dir.is_dir() or stack_dir.name.startswith("."):
            continue

        name = stack_dir.name
        has_marker = has_pending_marker(stack_dir)

        if neo4j_available:
            stack_id = f"stack_{name}"
            node = graph.get_node(stack_id)
            if node:
                initialized_at = node.get("initialized_at", "unknown")
                ok(f"{name}: initialized (at {initialized_at})")
            elif has_marker:
                warn(f"{name}: pending — run: python framework/scripts/init-stack-neo4j.py --stack {name}")
                pending += 1
            else:
                warn(f"{name}: not initialized")
                pending += 1
        else:
            if has_marker:
                warn(f"{name}: pending (Neo4j unavailable)")
                pending += 1
            else:
                ok(f"{name}: no pending marker (Neo4j unavailable to verify)")

    if graph:
        graph.close()

    return pending


def main():
    parser = argparse.ArgumentParser(
        description="Initialize stack knowledge graph presence in Neo4j"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stack", help="Stack name to initialize")
    group.add_argument("--all", action="store_true", help="Initialize all stacks")
    group.add_argument("--check", action="store_true", help="Check init status (read-only)")

    parser.add_argument("--profile", help="Path to RequirementsProfile JSON (for fresh stacks)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    args = parser.parse_args()

    print("\033[1m")
    print("Neo4j Stack Initialization")
    print("=" * 40)
    print("\033[0m")

    if args.check:
        step("Stack Status")
        pending = check_stacks(args.verbose)
        print()
        if pending == 0:
            print("\033[32m\033[1mAll stacks initialized.\033[0m")
        else:
            print(f"\033[33m\033[1m{pending} stack(s) need initialization.\033[0m")
        sys.exit(1 if pending > 0 else 0)

    elif args.all:
        total_ok = 0
        total_fail = 0
        for stack_dir in sorted(STACKS_DIR.iterdir()):
            if not stack_dir.is_dir() or stack_dir.name.startswith("."):
                continue
            name = stack_dir.name
            step(f"Initializing: {name}")
            result = init_stack(name, verbose=args.verbose)
            if result.get("status") == "ok":
                total_ok += 1
            else:
                total_fail += 1

        print()
        print(f"\033[1mResults: {total_ok} initialized, {total_fail} failed/deferred\033[0m")
        sys.exit(1 if total_fail > 0 else 0)

    else:
        step(f"Initializing: {args.stack}")
        result = init_stack(args.stack, profile_path=args.profile, verbose=args.verbose)
        if args.verbose:
            print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
