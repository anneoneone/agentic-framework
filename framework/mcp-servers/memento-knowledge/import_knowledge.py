"""
Knowledge Import Pipeline: JSONL/Markdown → Neo4j Knowledge Graph

Bulk imports existing knowledge files from agent-framework stacks into
the Neo4j knowledge graph. Handles all entity types and infers relationships.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from .graph import GraphManager, generate_id
except ImportError:
    from graph import GraphManager, generate_id


# Mapping: filename pattern → node label
FILE_LABEL_MAP = {
    "extracted-decisions": "Decision",
    "decisions": "Decision",
    "extracted-learnings": "Learning",
    "extracted-notes": "Note",
    "extracted-blocker-resolutions": "BlockerResolution",
    "api-endpoints": "Endpoint",
    "env-vars": "EnvVar",
    "sensors": "Sensor",
    "gpio-pins": "GPIOPin",
    "deployment-urls": "Endpoint",
    "versions": "EnvVar",
    "external-apis": "Endpoint",
    "protobuf-definitions": "Learning",
}


def detect_label(filename: str) -> Optional[str]:
    """Detect the node label from a filename."""
    stem = Path(filename).stem
    for pattern, label in FILE_LABEL_MAP.items():
        if pattern in stem:
            return label
    return None


def import_stack(graph: GraphManager, root_path: Path, stack: str) -> dict:
    """Import all knowledge from a stack into the graph.

    Args:
        graph: GraphManager instance
        root_path: Path to agent-framework root
        stack: Stack name (e.g., 'live-moafunk')

    Returns:
        Import statistics
    """
    knowledge_dir = root_path / "stacks" / stack / "docs" / "knowledge"
    if not knowledge_dir.exists():
        return {"error": f"Knowledge directory not found: {knowledge_dir}"}

    stats = {
        "stack": stack,
        "nodes_created": 0,
        "relationships_created": 0,
        "files_processed": 0,
        "errors": [],
        "by_label": {},
    }

    # Ensure stack node exists
    graph._ensure_stack(stack)

    # Collect all entities for relationship inference later
    all_entities: dict[str, list[dict]] = {}

    # Phase 1: Import JSONL files
    for jsonl_file in knowledge_dir.rglob("*.jsonl"):
        label = detect_label(jsonl_file.name)
        if not label:
            stats["errors"].append(f"Unknown file type: {jsonl_file.name}")
            continue

        try:
            nodes = _import_jsonl_file(graph, jsonl_file, stack, label)
            stats["nodes_created"] += len(nodes)
            stats["by_label"][label] = stats["by_label"].get(label, 0) + len(nodes)
            stats["files_processed"] += 1

            if label not in all_entities:
                all_entities[label] = []
            all_entities[label].extend(nodes)

        except Exception as e:
            stats["errors"].append(f"{jsonl_file.name}: {e}")

    # Phase 2: Import Markdown files as Pattern/knowledge docs
    for md_file in knowledge_dir.rglob("*.md"):
        if md_file.name == "index.md":
            continue  # Skip index files

        try:
            nodes = _import_markdown_file(graph, md_file, stack)
            stats["nodes_created"] += len(nodes)
            stats["by_label"]["Pattern"] = stats["by_label"].get("Pattern", 0) + len(nodes)
            stats["files_processed"] += 1

            if "Pattern" not in all_entities:
                all_entities["Pattern"] = []
            all_entities["Pattern"].extend(nodes)

        except Exception as e:
            stats["errors"].append(f"{md_file.name}: {e}")

    # Phase 3: Import agents as Agent nodes
    agents_dir = root_path / "stacks" / stack / "agents"
    if agents_dir.exists():
        agent_nodes = _import_agents(graph, agents_dir, stack)
        stats["nodes_created"] += len(agent_nodes)
        stats["by_label"]["Agent"] = len(agent_nodes)
        all_entities["Agent"] = agent_nodes

    # Phase 4: Import plans as Plan nodes
    plans_dir = root_path / "stacks" / stack / "plans"
    if plans_dir.exists():
        plan_nodes = _import_plans(graph, plans_dir, stack)
        stats["nodes_created"] += len(plan_nodes)
        stats["by_label"]["Plan"] = len(plan_nodes)
        all_entities["Plan"] = plan_nodes

    # Phase 5: Build relationships
    rels_created = _build_relationships(graph, stack, all_entities)
    stats["relationships_created"] = rels_created

    return stats


def _import_jsonl_file(
    graph: GraphManager, file_path: Path, stack: str, label: str
) -> list[dict]:
    """Import a JSONL file as nodes."""
    nodes = []
    batch = []

    with open(file_path, "r") as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            props = _normalize_entry(entry, label, stack, file_path.name, line_num)
            batch.append(props)
            nodes.append(props)

    if batch:
        graph.batch_create_nodes(label, batch)

    return nodes


def _normalize_entry(
    entry: dict, label: str, stack: str, source_file: str, line_num: int
) -> dict:
    """Normalize a JSONL entry into node properties."""
    node_id = generate_id(label, stack)

    # Common fields
    props = {
        "id": node_id,
        "stack": stack,
        "source_file": source_file,
        "source_index": line_num,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if label in ("Decision", "Learning", "Note", "BlockerResolution"):
        props["content"] = entry.get("content", "")
        props["agent"] = entry.get("agent", "")
        props["plan_id"] = entry.get("plan_id", "")
        props["step_id"] = entry.get("step_id", "")
        if label == "Learning":
            props["category"] = entry.get("category", "general")

    elif label == "Endpoint":
        props["method"] = entry.get("method", "GET")
        props["path"] = entry.get("path", entry.get("url", ""))
        props["purpose"] = entry.get("purpose", entry.get("description", ""))
        props["auth_required"] = entry.get("auth", entry.get("auth_required", False))
        props["name"] = f"{props['method']} {props['path']}"
        props["content"] = props["purpose"]  # For full-text search

    elif label == "EnvVar":
        props["name"] = entry.get("name", entry.get("var", ""))
        props["value"] = entry.get("value", entry.get("default", ""))
        props["purpose"] = entry.get("purpose", entry.get("description", ""))
        props["target"] = entry.get("target", "")
        props["content"] = f"{props['name']}: {props['purpose']}"

    elif label == "Sensor":
        props["name"] = entry.get("name", entry.get("sensor", ""))
        props["sensor_type"] = entry.get("type", "")
        props["gpio_pin"] = entry.get("gpio", entry.get("pin", -1))
        props["description"] = entry.get("description", entry.get("purpose", ""))
        props["content"] = f"{props['name']}: {props['description']}"

    elif label == "GPIOPin":
        props["pin_number"] = entry.get("bcm", entry.get("pin", -1))
        props["purpose"] = entry.get("purpose", entry.get("description", ""))
        props["mode"] = entry.get("mode", entry.get("direction", "output"))
        props["name"] = f"GPIO{props['pin_number']}"
        props["content"] = f"GPIO{props['pin_number']}: {props['purpose']}"

    return props


def _import_markdown_file(
    graph: GraphManager, file_path: Path, stack: str
) -> list[dict]:
    """Import a markdown file as Pattern nodes (one per H2 section)."""
    with open(file_path, "r") as f:
        content = f.read()

    nodes = []
    sections = re.split(r"\n## ", content)

    for idx, section in enumerate(sections):
        if not section.strip():
            continue

        lines = section.split("\n")
        title = lines[0].strip().lstrip("# ")
        body = "\n".join(lines[1:]).strip()

        if not body:
            continue

        props = {
            "id": generate_id("Pattern", stack),
            "name": title,
            "description": body[:500],
            "content": body,
            "stack": stack,
            "source_file": file_path.name,
            "source_index": idx,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        graph.create_node("Pattern", props)
        nodes.append(props)

    return nodes


def _import_agents(graph: GraphManager, agents_dir: Path, stack: str) -> list[dict]:
    """Import agent files as Agent nodes."""
    nodes = []

    for agent_file in agents_dir.glob("*.agent.md"):
        agent_name = agent_file.stem.replace(".agent", "")
        agent_id = f"agent_{stack}_{agent_name}"

        # Check if already exists
        if graph.get_node(agent_id):
            continue

        # Parse basic info from frontmatter
        description = ""
        try:
            with open(agent_file, "r") as f:
                content = f.read()
            # Simple YAML frontmatter extraction
            if content.startswith("---"):
                end = content.index("---", 3)
                frontmatter = content[3:end]
                for line in frontmatter.split("\n"):
                    if line.strip().startswith("description:"):
                        description = line.split(":", 1)[1].strip().strip("\"'")
        except Exception:
            pass

        props = {
            "id": agent_id,
            "name": agent_name,
            "stack": stack,
            "description": description,
            "source_file": agent_file.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        graph.create_node("Agent", props)
        nodes.append(props)

    return nodes


def _import_plans(graph: GraphManager, plans_dir: Path, stack: str) -> list[dict]:
    """Import plan JSON files as Plan nodes."""
    nodes = []

    for plan_file in plans_dir.glob("*.json"):
        try:
            with open(plan_file, "r") as f:
                plan = json.load(f)

            plan_id = plan.get("plan_id", plan_file.stem)
            node_id = f"plan_{stack}_{plan_id}"

            if graph.get_node(node_id):
                continue

            props = {
                "id": node_id,
                "plan_id": plan_id,
                "stack": stack,
                "description": plan.get("description", ""),
                "status": plan.get("overall_status", "unknown"),
                "created_at": plan.get("created_at", datetime.now(timezone.utc).isoformat()),
                "source_file": plan_file.name,
            }

            graph.create_node("Plan", props)
            nodes.append(props)

        except (json.JSONDecodeError, IOError):
            continue

    return nodes


def _build_relationships(
    graph: GraphManager, stack: str, all_entities: dict[str, list[dict]]
) -> int:
    """Build relationships between imported entities."""
    relationships = []
    stack_id = f"stack_{stack}"

    # BELONGS_TO Stack for all entities
    for label, entities in all_entities.items():
        for entity in entities:
            relationships.append({
                "source_id": entity["id"],
                "target_id": stack_id,
                "rel_type": "BELONGS_TO",
            })

    # MADE_BY Agent (for decisions, learnings, notes)
    agent_lookup = {}
    for agent in all_entities.get("Agent", []):
        agent_lookup[agent["name"]] = agent["id"]
        # Also map with @ prefix
        agent_lookup[f"@{agent['name']}"] = agent["id"]

    for label in ("Decision", "Learning", "Note", "BlockerResolution"):
        for entity in all_entities.get(label, []):
            agent_name = entity.get("agent", "")
            if agent_name and agent_name in agent_lookup:
                relationships.append({
                    "source_id": entity["id"],
                    "target_id": agent_lookup[agent_name],
                    "rel_type": "MADE_BY",
                })

    # USED_IN Plan (for decisions, learnings, notes)
    plan_lookup = {}
    for plan in all_entities.get("Plan", []):
        plan_lookup[plan.get("plan_id", "")] = plan["id"]

    for label in ("Decision", "Learning", "Note", "BlockerResolution"):
        for entity in all_entities.get(label, []):
            plan_id = entity.get("plan_id", "")
            if plan_id and plan_id in plan_lookup:
                relationships.append({
                    "source_id": entity["id"],
                    "target_id": plan_lookup[plan_id],
                    "rel_type": "USED_IN",
                })

    # AFFECTS: Learnings that mention endpoint paths
    endpoints = all_entities.get("Endpoint", [])
    for learning in all_entities.get("Learning", []):
        content = learning.get("content", "").lower()
        for endpoint in endpoints:
            ep_path = endpoint.get("path", "")
            if ep_path and ep_path.lower() in content:
                relationships.append({
                    "source_id": learning["id"],
                    "target_id": endpoint["id"],
                    "rel_type": "AFFECTS",
                })

    # AFFECTS: Learnings that mention env var names
    env_vars = all_entities.get("EnvVar", [])
    for learning in all_entities.get("Learning", []):
        content = learning.get("content", "").lower()
        for ev in env_vars:
            ev_name = ev.get("name", "")
            if ev_name and ev_name.lower() in content:
                relationships.append({
                    "source_id": learning["id"],
                    "target_id": ev["id"],
                    "rel_type": "AFFECTS",
                })

    # AFFECTS: Learnings that mention sensor/GPIO names
    for sensor in all_entities.get("Sensor", []):
        sensor_name = sensor.get("name", "").lower()
        for learning in all_entities.get("Learning", []):
            if sensor_name and sensor_name in learning.get("content", "").lower():
                relationships.append({
                    "source_id": learning["id"],
                    "target_id": sensor["id"],
                    "rel_type": "AFFECTS",
                })

    # Batch create all relationships
    created = 0
    if relationships:
        created = graph.batch_create_relationships(relationships)

    return created


def import_all_stacks(graph: GraphManager, root_path: Path) -> dict:
    """Import knowledge from all stacks."""
    stacks_dir = root_path / "stacks"
    if not stacks_dir.exists():
        return {"error": "No stacks directory found"}

    results = {}
    for stack_dir in stacks_dir.iterdir():
        if stack_dir.is_dir():
            stack_name = stack_dir.name
            results[stack_name] = import_stack(graph, root_path, stack_name)

    return results


# CLI entry point
if __name__ == "__main__":
    root = Path(__file__).parent.parent.parent.parent.resolve()

    graph = GraphManager(
        uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        username=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )

    if len(sys.argv) > 1:
        stack = sys.argv[1]
        print(f"Importing stack: {stack}")
        result = import_stack(graph, root, stack)
    else:
        print("Importing all stacks...")
        result = import_all_stacks(graph, root)

    print(json.dumps(result, indent=2, default=str))
    graph.close()
