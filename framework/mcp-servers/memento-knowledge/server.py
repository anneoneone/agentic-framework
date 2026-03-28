"""
Memento Knowledge Graph MCP Server

Neo4j-backed knowledge graph with entity relationships, temporal queries,
and cross-stack knowledge sharing for the agent-framework.

Tools follow agent-framework conventions: snake_case names, json.dumps returns.
"""

import json
import os
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

try:
    from .graph import GraphManager
    from .import_knowledge import import_stack, import_all_stacks
except ImportError:
    from graph import GraphManager
    from import_knowledge import import_stack, import_all_stacks


# ============================================================================
# MCP Server
# ============================================================================

mcp = FastMCP("memento-knowledge")

# Global graph manager (lazy singleton)
_graph: Optional[GraphManager] = None


def get_graph() -> GraphManager:
    """Get or create the GraphManager singleton."""
    global _graph
    if _graph is None:
        _graph = GraphManager(
            uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )
    return _graph


def get_root_path() -> Path:
    """Find agent-framework root path."""
    return Path(__file__).parent.parent.parent.parent.resolve()


# ============================================================================
# Query Tools
# ============================================================================


@mcp.tool()
def search_knowledge_graph(
    query: str,
    stack: str = None,
    entity_types: list[str] = None,
    limit: int = 10,
) -> str:
    """Search the knowledge graph using full-text search with relationship context.

    Args:
        query: Search query (supports Lucene syntax: AND, OR, wildcards)
        stack: Optional stack name to filter results
        entity_types: Optional list of entity types to search (Decision, Learning, Note, etc.)
        limit: Maximum number of results (default: 10)
    """
    try:
        graph = get_graph()
        results = graph.search_fulltext(query, stack, entity_types, limit)
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def find_related_knowledge(
    entity_id: str,
    relationship_types: list[str] = None,
    depth: int = 2,
    limit: int = 20,
) -> str:
    """Find related entities via graph traversal from a starting node.

    Args:
        entity_id: ID of the starting node
        relationship_types: Optional filter for relationship types (BELONGS_TO, MADE_BY, etc.)
        depth: Maximum traversal depth (default: 2, max: 5)
        limit: Maximum results (default: 20)
    """
    try:
        graph = get_graph()
        depth = min(depth, 5)
        results = graph.find_related(entity_id, relationship_types, depth, limit)
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_decision_timeline(
    stack: str,
    plan_id: str = None,
    agent: str = None,
    limit: int = 50,
) -> str:
    """Get chronological decisions for a stack with agent and plan context.

    Args:
        stack: Stack name (required)
        plan_id: Optional plan ID to filter
        agent: Optional agent name to filter (e.g., '@axum-backend')
        limit: Maximum results (default: 50)
    """
    try:
        graph = get_graph()
        results = graph.get_decision_timeline(stack, plan_id, agent, limit)
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_agent_context(agent: str, stack: str = None) -> str:
    """Get all knowledge relevant to an agent: decisions, learnings, endpoints.

    Args:
        agent: Agent name (e.g., '@axum-backend' or 'axum-backend')
        stack: Optional stack name to filter
    """
    try:
        graph = get_graph()
        result = graph.get_agent_context(agent, stack)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def trace_decision_chain(decision_id: str, depth: int = 5) -> str:
    """Follow DEPENDS_ON, RELATES_TO, and SUPERSEDES chains from a decision.

    Useful for understanding the reasoning chain behind a decision.

    Args:
        decision_id: ID of the starting decision
        depth: Maximum chain depth (default: 5)
    """
    try:
        graph = get_graph()
        results = graph.trace_decision_chain(decision_id, min(depth, 10))
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def find_affected_components(learning_id: str) -> str:
    """Find all endpoints, env vars, sensors affected by a learning.

    Args:
        learning_id: ID of the learning to check
    """
    try:
        graph = get_graph()
        results = graph.find_affected_components(learning_id)
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def cross_stack_similarity(
    stack_a: str,
    stack_b: str,
    entity_type: str = "Decision",
    limit: int = 20,
) -> str:
    """Find similar knowledge across two stacks using content overlap.

    Args:
        stack_a: First stack name
        stack_b: Second stack name
        entity_type: Entity type to compare (default: Decision)
        limit: Maximum pairs returned (default: 20)
    """
    try:
        graph = get_graph()
        results = graph.cross_stack_similarity(stack_a, stack_b, entity_type, limit)
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Mutation Tools
# ============================================================================


@mcp.tool()
def add_decision(
    content: str,
    stack: str,
    plan_id: str = None,
    step_id: str = None,
    agent: str = None,
) -> str:
    """Create a Decision node and establish relationships.

    Args:
        content: The decision text
        stack: Stack name
        plan_id: Optional plan ID this decision belongs to
        step_id: Optional step ID within the plan
        agent: Optional agent that made the decision
    """
    try:
        graph = get_graph()
        graph._ensure_stack(stack)

        props = {
            "content": content,
            "stack": stack,
            "plan_id": plan_id or "",
            "step_id": step_id or "",
            "agent": agent or "",
        }
        node = graph.create_node("Decision", props)

        if node:
            stack_id = f"stack_{stack}"
            graph.create_relationship(node["id"], stack_id, "BELONGS_TO")

            if agent:
                graph._ensure_agent(agent, stack)
                agent_id = f"agent_{stack}_{agent.lstrip('@')}"
                graph.create_relationship(node["id"], agent_id, "MADE_BY")

            if plan_id:
                graph._ensure_plan(plan_id, stack)
                plan_node_id = f"plan_{stack}_{plan_id}"
                graph.create_relationship(node["id"], plan_node_id, "USED_IN")

        return json.dumps(node, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def add_learning(
    content: str,
    stack: str,
    category: str = None,
    agent: str = None,
    affected_components: list[str] = None,
) -> str:
    """Create a Learning node and optionally link to affected components.

    Args:
        content: The learning text
        stack: Stack name
        category: Optional category (e.g., 'performance', 'bug', 'architecture')
        agent: Optional agent name
        affected_components: Optional list of entity IDs this learning affects
    """
    try:
        graph = get_graph()
        graph._ensure_stack(stack)

        props = {
            "content": content,
            "stack": stack,
            "category": category or "general",
            "agent": agent or "",
        }
        node = graph.create_node("Learning", props)

        if node:
            stack_id = f"stack_{stack}"
            graph.create_relationship(node["id"], stack_id, "BELONGS_TO")

            if agent:
                graph._ensure_agent(agent, stack)
                agent_id = f"agent_{stack}_{agent.lstrip('@')}"
                graph.create_relationship(node["id"], agent_id, "MADE_BY")

            for comp_id in (affected_components or []):
                graph.create_relationship(node["id"], comp_id, "AFFECTS")

        return json.dumps(node, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def link_knowledge(
    source_id: str,
    target_id: str,
    relationship_type: str,
    properties: dict = None,
) -> str:
    """Create a relationship between two existing knowledge entities.

    Args:
        source_id: ID of the source node
        target_id: ID of the target node
        relationship_type: Relationship type (RELATES_TO, DEPENDS_ON, AFFECTS, SUPERSEDES)
        properties: Optional properties for the relationship
    """
    allowed_types = {
        "RELATES_TO", "DEPENDS_ON", "AFFECTS", "SUPERSEDES",
        "USES", "CONFIGURES", "MONITORS", "CONTROLS",
    }
    if relationship_type not in allowed_types:
        return json.dumps({
            "error": f"Invalid relationship type. Allowed: {sorted(allowed_types)}"
        })

    try:
        graph = get_graph()
        result = graph.create_relationship(source_id, target_id, relationship_type, properties)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def supersede_decision(
    old_decision_id: str,
    new_decision_id: str,
    reason: str,
) -> str:
    """Mark an old decision as superseded by a new one.

    Args:
        old_decision_id: ID of the old decision
        new_decision_id: ID of the new decision that supersedes it
        reason: Why the old decision was superseded
    """
    try:
        graph = get_graph()

        # Create SUPERSEDES relationship
        result = graph.create_relationship(
            new_decision_id, old_decision_id, "SUPERSEDES",
            {"reason": reason},
        )

        # Mark old decision as superseded
        graph.update_node(old_decision_id, {"superseded": True, "superseded_by": new_decision_id})

        return json.dumps({
            "old_decision": old_decision_id,
            "new_decision": new_decision_id,
            "reason": reason,
            "relationship": result,
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def add_endpoint(
    method: str,
    path: str,
    purpose: str,
    auth_required: bool,
    stack: str,
) -> str:
    """Register an API endpoint in the knowledge graph.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: Endpoint path (e.g., '/api/stream/status')
        purpose: Brief description of what the endpoint does
        auth_required: Whether authentication is required
        stack: Stack name
    """
    try:
        graph = get_graph()
        graph._ensure_stack(stack)

        props = {
            "method": method.upper(),
            "path": path,
            "purpose": purpose,
            "auth_required": auth_required,
            "stack": stack,
            "name": f"{method.upper()} {path}",
            "content": purpose,
        }
        node = graph.create_node("Endpoint", props)

        if node:
            stack_id = f"stack_{stack}"
            graph.create_relationship(node["id"], stack_id, "BELONGS_TO")

        return json.dumps(node, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def add_env_var(
    name: str,
    purpose: str,
    stack: str,
    value: str = "",
) -> str:
    """Register an environment variable in the knowledge graph.

    Args:
        name: Variable name (e.g., 'DATABASE_URL')
        purpose: What this variable configures
        stack: Stack name
        value: Default or example value (masked in responses)
    """
    try:
        graph = get_graph()
        graph._ensure_stack(stack)

        props = {
            "name": name,
            "purpose": purpose,
            "value": value,
            "stack": stack,
            "content": f"{name}: {purpose}",
        }
        node = graph.create_node("EnvVar", props)

        if node:
            stack_id = f"stack_{stack}"
            graph.create_relationship(node["id"], stack_id, "BELONGS_TO")

        # Mask value in response
        response = dict(node) if node else {}
        if "value" in response and response["value"]:
            response["value"] = "***"

        return json.dumps(response, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Admin Tools
# ============================================================================


@mcp.tool()
def get_graph_stats(stack: str = None) -> str:
    """Get knowledge graph statistics: node counts, relationship counts, index health.

    Args:
        stack: Optional stack name to filter (omit for global stats)
    """
    try:
        graph = get_graph()
        stats = graph.get_stats(stack)
        return json.dumps(stats, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def import_stack_knowledge(stack: str) -> str:
    """Import knowledge from JSONL/markdown files into the graph for a stack.

    Reads from stacks/{stack}/docs/knowledge/ and creates nodes + relationships.

    Args:
        stack: Stack name to import (e.g., 'live-moafunk')
    """
    try:
        graph = get_graph()
        root = get_root_path()
        result = import_stack(graph, root, stack)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def init_stack(stack: str) -> str:
    """Initialize a stack's Neo4j knowledge graph presence.

    Creates the Stack node, Agent nodes for all agents in the stack's agents/
    directory, and imports existing knowledge files.
    Idempotent — safe to call multiple times.

    For fresh stacks with a RequirementsProfile, use the CLI script instead:
    python framework/scripts/init-stack-neo4j.py --stack NAME --profile PATH

    Args:
        stack: Stack name (e.g., 'next-generation')
    """
    try:
        graph = get_graph()
        root = get_root_path()
        stack_dir = root / "stacks" / stack

        if not stack_dir.is_dir():
            return json.dumps({"error": f"Stack directory not found: stacks/{stack}"})

        # Load stack metadata
        from datetime import datetime, timezone
        metadata = {"initialized_at": datetime.now(timezone.utc).isoformat()}
        config_path = stack_dir / ".stack.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                for key in ("description", "type", "repo_path", "created_at"):
                    if config.get(key):
                        metadata[key] = config[key]
            except (json.JSONDecodeError, OSError):
                pass

        # Parse agents from directory
        agents = []
        agents_dir = stack_dir / "agents"
        if agents_dir.exists():
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
                agents.append({"name": agent_name, "description": description, "source_file": f.name})

        # Initialize graph
        stats = graph.init_stack_graph(stack, metadata, agents)

        # Import existing knowledge files
        knowledge_dir = stack_dir / "docs" / "knowledge"
        if knowledge_dir.exists():
            import_stats = import_stack(graph, root, stack)
            stats["import"] = import_stats

        return json.dumps(stats, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def export_stack_knowledge(stack: str, format: str = "jsonl") -> str:
    """Export all knowledge for a stack from the graph.

    Args:
        stack: Stack name to export
        format: Output format ('jsonl' or 'json')
    """
    try:
        graph = get_graph()
        data = graph.export_stack(stack)

        if format == "jsonl":
            lines = [json.dumps(item, default=str) for item in data]
            return "\n".join(lines)
        else:
            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# Entry Point
# ============================================================================


if __name__ == "__main__":
    mcp.run(transport="stdio")
