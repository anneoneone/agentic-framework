"""
Neo4j GraphManager for Memento Knowledge Graph

Provides CRUD operations, relationship management, and graph queries
for the agent-framework knowledge system.
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError

try:
    from .schema import init_schema
except ImportError:
    from schema import init_schema


@dataclass
class KnowledgeNode:
    """Represents a node in the knowledge graph"""
    id: str
    label: str
    properties: dict
    relationships: list = field(default_factory=list)


@dataclass
class GraphStats:
    """Graph statistics"""
    total_nodes: int = 0
    total_relationships: int = 0
    nodes_by_label: dict = field(default_factory=dict)
    relationships_by_type: dict = field(default_factory=dict)


def generate_id(label: str, stack: str) -> str:
    """Generate a unique ID for a node."""
    short_uuid = uuid.uuid4().hex[:12]
    return f"{label.lower()}_{stack}_{short_uuid}"


class GraphManager:
    """Manages Neo4j knowledge graph operations.

    Uses lazy initialization and connection pooling.
    Thread-safe via Neo4j driver's built-in pool management.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    BATCH_SIZE = 500

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self._username = username or os.getenv("NEO4J_USER", "neo4j")
        self._password = password or os.getenv("NEO4J_PASSWORD", "password")
        self._driver: Optional[Driver] = None
        self._schema_initialized = False

    @property
    def driver(self) -> Driver:
        """Lazy-initialize Neo4j driver."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
            if not self._schema_initialized:
                init_schema(self._driver)
                self._schema_initialized = True
        return self._driver

    def close(self):
        """Close the Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def _retry(self, func, *args, **kwargs):
        """Execute with retry logic for transient failures."""
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except ServiceUnavailable as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
        raise last_error

    # =========================================================================
    # Node CRUD
    # =========================================================================

    def create_node(self, label: str, properties: dict) -> dict:
        """Create a single node with the given label and properties."""
        if "id" not in properties:
            stack = properties.get("stack", "unknown")
            properties["id"] = generate_id(label, stack)
        if "created_at" not in properties:
            properties["created_at"] = datetime.now(timezone.utc).isoformat()

        def _create(tx):
            # Build property string dynamically
            prop_str = ", ".join(f"{k}: ${k}" for k in properties)
            query = f"CREATE (n:{label} {{{prop_str}}}) RETURN n"
            result = tx.run(query, **properties)
            record = result.single()
            return dict(record["n"]) if record else None

        with self.driver.session() as session:
            return self._retry(session.execute_write, _create)

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get a node by its ID."""
        def _get(tx):
            result = tx.run(
                "MATCH (n {id: $id}) RETURN n, labels(n) as labels",
                id=node_id,
            )
            record = result.single()
            if record:
                node = dict(record["n"])
                node["_labels"] = record["labels"]
                return node
            return None

        with self.driver.session() as session:
            return self._retry(session.execute_read, _get)

    def update_node(self, node_id: str, properties: dict) -> Optional[dict]:
        """Update a node's properties."""
        properties["updated_at"] = datetime.now(timezone.utc).isoformat()

        def _update(tx):
            set_clauses = ", ".join(f"n.{k} = ${k}" for k in properties)
            result = tx.run(
                f"MATCH (n {{id: $id}}) SET {set_clauses} RETURN n",
                id=node_id,
                **properties,
            )
            record = result.single()
            return dict(record["n"]) if record else None

        with self.driver.session() as session:
            return self._retry(session.execute_write, _update)

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its relationships."""
        def _delete(tx):
            result = tx.run(
                "MATCH (n {id: $id}) DETACH DELETE n RETURN count(n) as deleted",
                id=node_id,
            )
            record = result.single()
            return record["deleted"] > 0 if record else False

        with self.driver.session() as session:
            return self._retry(session.execute_write, _delete)

    def batch_create_nodes(self, label: str, nodes_data: list[dict]) -> int:
        """Create multiple nodes in batches. Returns count of created nodes."""
        created = 0

        for i in range(0, len(nodes_data), self.BATCH_SIZE):
            batch = nodes_data[i:i + self.BATCH_SIZE]

            for props in batch:
                if "id" not in props:
                    stack = props.get("stack", "unknown")
                    props["id"] = generate_id(label, stack)
                if "created_at" not in props:
                    props["created_at"] = datetime.now(timezone.utc).isoformat()

            def _batch_create(tx, items=batch):
                query = (
                    f"UNWIND $items AS props "
                    f"CREATE (n:{label}) SET n = props "
                    f"RETURN count(n) as created"
                )
                result = tx.run(query, items=items)
                record = result.single()
                return record["created"] if record else 0

            with self.driver.session() as session:
                created += self._retry(session.execute_write, _batch_create)

        return created

    # =========================================================================
    # Relationship Operations
    # =========================================================================

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: Optional[dict] = None,
    ) -> Optional[dict]:
        """Create a relationship between two nodes."""
        props = properties or {}
        if "created_at" not in props:
            props["created_at"] = datetime.now(timezone.utc).isoformat()

        def _create_rel(tx):
            prop_str = ""
            if props:
                prop_assignments = ", ".join(f"{k}: ${k}" for k in props)
                prop_str = f" {{{prop_assignments}}}"

            query = (
                f"MATCH (a {{id: $source_id}}), (b {{id: $target_id}}) "
                f"CREATE (a)-[r:{rel_type}{prop_str}]->(b) "
                f"RETURN type(r) as type, properties(r) as props"
            )
            result = tx.run(query, source_id=source_id, target_id=target_id, **props)
            record = result.single()
            if record:
                return {"type": record["type"], "properties": record["props"]}
            return None

        with self.driver.session() as session:
            return self._retry(session.execute_write, _create_rel)

    def batch_create_relationships(
        self, relationships: list[dict]
    ) -> int:
        """Create multiple relationships in batches.

        Each dict: {source_id, target_id, rel_type, properties?}
        """
        created = 0

        for i in range(0, len(relationships), self.BATCH_SIZE):
            batch = relationships[i:i + self.BATCH_SIZE]

            # Group by relationship type for efficient Cypher
            by_type: dict[str, list] = {}
            for rel in batch:
                rt = rel["rel_type"]
                if rt not in by_type:
                    by_type[rt] = []
                by_type[rt].append({
                    "source_id": rel["source_id"],
                    "target_id": rel["target_id"],
                    "props": rel.get("properties", {}),
                })

            for rel_type, items in by_type.items():
                def _batch_rels(tx, rt=rel_type, data=items):
                    query = (
                        f"UNWIND $data AS rel "
                        f"MATCH (a {{id: rel.source_id}}), (b {{id: rel.target_id}}) "
                        f"CREATE (a)-[r:{rt}]->(b) "
                        f"SET r = rel.props "
                        f"RETURN count(r) as created"
                    )
                    result = tx.run(query, data=data)
                    record = result.single()
                    return record["created"] if record else 0

                with self.driver.session() as session:
                    created += self._retry(session.execute_write, _batch_rels)

        return created

    def get_relationships(
        self, node_id: str, rel_type: Optional[str] = None, direction: str = "both"
    ) -> list[dict]:
        """Get relationships for a node."""
        def _get_rels(tx):
            if direction == "outgoing":
                pattern = "(a {id: $id})-[r]->(b)"
            elif direction == "incoming":
                pattern = "(a {id: $id})<-[r]-(b)"
            else:
                pattern = "(a {id: $id})-[r]-(b)"

            type_filter = f" AND type(r) = '{rel_type}'" if rel_type else ""

            query = (
                f"MATCH {pattern} "
                f"WHERE true{type_filter} "
                f"RETURN type(r) as type, properties(r) as rel_props, "
                f"b.id as target_id, labels(b) as target_labels, "
                f"b.content as target_content, b.name as target_name"
            )
            result = tx.run(query, id=node_id)
            return [
                {
                    "type": r["type"],
                    "properties": r["rel_props"],
                    "target_id": r["target_id"],
                    "target_labels": r["target_labels"],
                    "target_preview": r["target_content"][:200] if r["target_content"] else r["target_name"],
                }
                for r in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _get_rels)

    # =========================================================================
    # Search & Query
    # =========================================================================

    def search_fulltext(
        self,
        query: str,
        stack: Optional[str] = None,
        entity_types: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Full-text search across knowledge entities."""
        def _search(tx):
            # Use the full-text index
            cypher = (
                "CALL db.index.fulltext.queryNodes('knowledge_content', $query) "
                "YIELD node, score "
            )

            filters = []
            params = {"query": query, "limit": limit}

            if stack:
                filters.append("node.stack = $stack")
                params["stack"] = stack

            if entity_types:
                label_checks = " OR ".join(f"'{t}' IN labels(node)" for t in entity_types)
                filters.append(f"({label_checks})")

            if filters:
                cypher += "WHERE " + " AND ".join(filters) + " "

            cypher += (
                "RETURN node, labels(node) as labels, score "
                "ORDER BY score DESC LIMIT $limit"
            )

            result = tx.run(cypher, **params)
            return [
                {
                    "id": record["node"]["id"],
                    "labels": record["labels"],
                    "score": round(record["score"], 4),
                    "content": (record["node"].get("content") or "")[:200],
                    "stack": record["node"].get("stack"),
                    "agent": record["node"].get("agent"),
                    "created_at": record["node"].get("created_at"),
                }
                for record in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _search)

    def search_components(
        self,
        query: str,
        stack: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search endpoints, env vars, sensors via full-text index."""
        def _search(tx):
            cypher = (
                "CALL db.index.fulltext.queryNodes('component_search', $query) "
                "YIELD node, score "
            )
            params = {"query": query, "limit": limit}

            if stack:
                cypher += "WHERE node.stack = $stack "
                params["stack"] = stack

            cypher += (
                "RETURN node, labels(node) as labels, score "
                "ORDER BY score DESC LIMIT $limit"
            )

            result = tx.run(cypher, **params)
            return [
                {
                    "id": record["node"]["id"],
                    "labels": record["labels"],
                    "score": round(record["score"], 4),
                    "properties": dict(record["node"]),
                }
                for record in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _search)

    def find_related(
        self,
        entity_id: str,
        relationship_types: Optional[list[str]] = None,
        depth: int = 2,
        limit: int = 20,
    ) -> list[dict]:
        """Find related entities via graph traversal."""
        def _find(tx):
            rel_filter = ""
            if relationship_types:
                rel_filter = ":" + "|".join(relationship_types)

            query = (
                f"MATCH path = (start {{id: $id}})-[r{rel_filter}*1..{depth}]-(end) "
                f"RETURN end, labels(end) as labels, length(path) as distance, "
                f"[rel in relationships(path) | type(rel)] as rel_types "
                f"ORDER BY distance ASC "
                f"LIMIT $limit"
            )
            result = tx.run(query, id=entity_id, limit=limit)
            return [
                {
                    "id": record["end"]["id"],
                    "labels": record["labels"],
                    "distance": record["distance"],
                    "relationship_path": record["rel_types"],
                    "content": (record["end"].get("content") or record["end"].get("name") or "")[:200],
                    "stack": record["end"].get("stack"),
                }
                for record in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _find)

    def get_decision_timeline(
        self,
        stack: str,
        plan_id: Optional[str] = None,
        agent: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get chronological decisions for a stack."""
        def _timeline(tx):
            filters = ["d.stack = $stack"]
            params = {"stack": stack, "limit": limit}

            if plan_id:
                filters.append("d.plan_id = $plan_id")
                params["plan_id"] = plan_id
            if agent:
                filters.append("d.agent = $agent")
                params["agent"] = agent

            where = " AND ".join(filters)

            query = (
                f"MATCH (d:Decision) WHERE {where} "
                f"OPTIONAL MATCH (d)-[:MADE_BY]->(a:Agent) "
                f"OPTIONAL MATCH (d)-[:USED_IN]->(p:Plan) "
                f"RETURN d, a.name as agent_name, p.id as plan_ref "
                f"ORDER BY d.created_at DESC LIMIT $limit"
            )
            result = tx.run(query, **params)
            return [
                {
                    "id": record["d"]["id"],
                    "content": record["d"].get("content", ""),
                    "agent": record["agent_name"] or record["d"].get("agent"),
                    "plan_id": record["plan_ref"] or record["d"].get("plan_id"),
                    "created_at": record["d"].get("created_at"),
                }
                for record in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _timeline)

    def get_agent_context(self, agent_name: str, stack: Optional[str] = None) -> dict:
        """Get all knowledge relevant to an agent."""
        def _context(tx):
            stack_filter = ""
            params = {"agent": agent_name}
            if stack:
                stack_filter = " AND d.stack = $stack"
                params["stack"] = stack

            # Decisions made by agent
            decisions = tx.run(
                f"MATCH (d:Decision) WHERE d.agent = $agent{stack_filter} "
                f"RETURN d ORDER BY d.created_at DESC LIMIT 20",
                **params,
            ).data()

            # Learnings by agent
            learnings = tx.run(
                f"MATCH (l:Learning) WHERE l.agent = $agent{stack_filter} "
                f"RETURN l ORDER BY l.created_at DESC LIMIT 20",
                **params,
            ).data()

            # Endpoints the agent affects
            endpoints = tx.run(
                "MATCH (d)-[:AFFECTS]->(e:Endpoint) "
                "WHERE d.agent = $agent "
                "RETURN DISTINCT e LIMIT 20",
                **params,
            ).data()

            return {
                "agent": agent_name,
                "decisions_count": len(decisions),
                "decisions": [
                    {"id": d["d"]["id"], "content": d["d"].get("content", "")[:150]}
                    for d in decisions
                ],
                "learnings_count": len(learnings),
                "learnings": [
                    {"id": l["l"]["id"], "content": l["l"].get("content", "")[:150]}
                    for l in learnings
                ],
                "endpoints": [
                    {"id": e["e"]["id"], "path": e["e"].get("path"), "method": e["e"].get("method")}
                    for e in endpoints
                ],
            }

        with self.driver.session() as session:
            return self._retry(session.execute_read, _context)

    def trace_decision_chain(self, decision_id: str, depth: int = 5) -> list[dict]:
        """Follow DEPENDS_ON and RELATES_TO chains from a decision."""
        def _trace(tx):
            query = (
                "MATCH path = (start:Decision {id: $id})"
                "-[:DEPENDS_ON|RELATES_TO|SUPERSEDES*0.." + str(depth) + "]->(chain) "
                "RETURN chain, labels(chain) as labels, length(path) as distance, "
                "[rel IN relationships(path) | type(rel)] as rel_types "
                "ORDER BY distance ASC LIMIT 50"
            )
            result = tx.run(query, id=decision_id)
            return [
                {
                    "id": record["chain"]["id"],
                    "labels": record["labels"],
                    "content": (record["chain"].get("content") or "")[:200],
                    "distance": record["distance"],
                    "relationship_path": record["rel_types"],
                }
                for record in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _trace)

    def find_affected_components(self, learning_id: str) -> list[dict]:
        """Find components affected by a learning."""
        def _find(tx):
            query = (
                "MATCH (l:Learning {id: $id})-[:AFFECTS]->(c) "
                "RETURN c, labels(c) as labels"
            )
            result = tx.run(query, id=learning_id)
            return [
                {
                    "id": record["c"]["id"],
                    "labels": record["labels"],
                    "properties": dict(record["c"]),
                }
                for record in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _find)

    def cross_stack_similarity(
        self,
        stack_a: str,
        stack_b: str,
        entity_type: str = "Decision",
        limit: int = 20,
    ) -> list[dict]:
        """Find similar knowledge across two stacks using shared keywords."""
        def _similarity(tx):
            # Find entities in both stacks with overlapping content words
            query = (
                f"MATCH (a:{entity_type} {{stack: $stack_a}}) "
                f"MATCH (b:{entity_type} {{stack: $stack_b}}) "
                f"WHERE a.content IS NOT NULL AND b.content IS NOT NULL "
                f"WITH a, b, "
                f"  [word IN split(toLower(a.content), ' ') WHERE size(word) > 4] AS words_a, "
                f"  [word IN split(toLower(b.content), ' ') WHERE size(word) > 4] AS words_b "
                f"WITH a, b, "
                f"  size([w IN words_a WHERE w IN words_b]) AS overlap, "
                f"  size(words_a) + size(words_b) AS total "
                f"WHERE overlap > 1 "
                f"RETURN a.id as id_a, a.content as content_a, "
                f"  b.id as id_b, b.content as content_b, "
                f"  toFloat(overlap) / toFloat(total) as similarity "
                f"ORDER BY similarity DESC LIMIT $limit"
            )
            result = tx.run(query, stack_a=stack_a, stack_b=stack_b, limit=limit)
            return [
                {
                    "stack_a_entity": {
                        "id": r["id_a"],
                        "content": r["content_a"][:150],
                    },
                    "stack_b_entity": {
                        "id": r["id_b"],
                        "content": r["content_b"][:150],
                    },
                    "similarity": round(r["similarity"], 4),
                }
                for r in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _similarity)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self, stack: Optional[str] = None) -> dict:
        """Get graph statistics."""
        def _stats(tx):
            stack_filter = ""
            params = {}
            if stack:
                stack_filter = " WHERE n.stack = $stack"
                params["stack"] = stack

            # Node counts by label
            nodes_query = (
                f"MATCH (n){stack_filter} "
                f"RETURN labels(n) as labels, count(n) as count"
            )
            node_results = tx.run(nodes_query, **params).data()

            nodes_by_label = {}
            total_nodes = 0
            for r in node_results:
                for label in r["labels"]:
                    nodes_by_label[label] = nodes_by_label.get(label, 0) + r["count"]
                total_nodes += r["count"]

            # Relationship counts by type
            rels_query = (
                "MATCH ()-[r]->() "
                "RETURN type(r) as type, count(r) as count"
            )
            rel_results = tx.run(rels_query).data()

            rels_by_type = {r["type"]: r["count"] for r in rel_results}
            total_rels = sum(rels_by_type.values())

            return {
                "total_nodes": total_nodes,
                "total_relationships": total_rels,
                "nodes_by_label": nodes_by_label,
                "relationships_by_type": rels_by_type,
            }

        with self.driver.session() as session:
            return self._retry(session.execute_read, _stats)

    # =========================================================================
    # Knowledge Ingestion (for post-step-hook integration)
    # =========================================================================

    def ingest_step_knowledge(
        self,
        stack: str,
        plan_id: str,
        step_id: str,
        agent: Optional[str],
        knowledge_items: list[dict],
    ) -> dict:
        """Ingest knowledge items from a completed plan step.

        Called by post-step-hook.py after step completion.
        """
        stats = {"decisions": 0, "learnings": 0, "notes": 0, "blockers": 0}

        # Ensure stack node exists
        self._ensure_stack(stack)

        # Ensure plan node exists
        self._ensure_plan(plan_id, stack)

        # Ensure agent node exists
        if agent:
            self._ensure_agent(agent, stack)

        for item in knowledge_items:
            item_type = item.get("type", "note")
            content = item.get("content", "")

            if not content:
                continue

            label = {
                "decision": "Decision",
                "learning": "Learning",
                "note": "Note",
                "blocker_resolution": "BlockerResolution",
            }.get(item_type, "Note")

            props = {
                "content": content,
                "stack": stack,
                "plan_id": plan_id,
                "step_id": step_id,
                "agent": agent or "",
                "source": "post-step-hook",
            }

            node = self.create_node(label, props)
            if node:
                # Create relationships
                stack_id = f"stack_{stack}"
                self.create_relationship(node["id"], stack_id, "BELONGS_TO")

                if plan_id:
                    plan_node_id = f"plan_{stack}_{plan_id}"
                    self.create_relationship(node["id"], plan_node_id, "USED_IN")

                if agent:
                    agent_id = f"agent_{stack}_{agent.lstrip('@')}"
                    self.create_relationship(node["id"], agent_id, "MADE_BY")

                stats[item_type + "s" if item_type != "blocker_resolution" else "blockers"] = (
                    stats.get(item_type + "s" if item_type != "blocker_resolution" else "blockers", 0) + 1
                )

        return stats

    def _ensure_stack(self, stack: str):
        """Ensure a Stack node exists."""
        stack_id = f"stack_{stack}"
        if not self.get_node(stack_id):
            self.create_node("Stack", {
                "id": stack_id,
                "name": stack,
                "active": True,
            })

    def _ensure_plan(self, plan_id: str, stack: str):
        """Ensure a Plan node exists."""
        node_id = f"plan_{stack}_{plan_id}"
        if not self.get_node(node_id):
            plan_node = self.create_node("Plan", {
                "id": node_id,
                "plan_id": plan_id,
                "stack": stack,
                "status": "unknown",
            })
            if plan_node:
                stack_id = f"stack_{stack}"
                self.create_relationship(node_id, stack_id, "BELONGS_TO")

    def _ensure_agent(self, agent: str, stack: str):
        """Ensure an Agent node exists."""
        agent_clean = agent.lstrip("@")
        agent_id = f"agent_{stack}_{agent_clean}"
        if not self.get_node(agent_id):
            agent_node = self.create_node("Agent", {
                "id": agent_id,
                "name": agent_clean,
                "stack": stack,
            })
            if agent_node:
                stack_id = f"stack_{stack}"
                self.create_relationship(agent_id, stack_id, "BELONGS_TO")

    # =========================================================================
    # Export
    # =========================================================================

    def export_stack(self, stack: str) -> list[dict]:
        """Export all knowledge for a stack as a list of dicts."""
        def _export(tx):
            query = (
                "MATCH (n) WHERE n.stack = $stack "
                "RETURN n, labels(n) as labels "
                "ORDER BY n.created_at"
            )
            result = tx.run(query, stack=stack)
            return [
                {
                    "labels": record["labels"],
                    "properties": dict(record["n"]),
                }
                for record in result
            ]

        with self.driver.session() as session:
            return self._retry(session.execute_read, _export)

    def clear_stack(self, stack: str) -> dict:
        """Delete all knowledge for a stack."""
        def _clear(tx):
            result = tx.run(
                "MATCH (n) WHERE n.stack = $stack DETACH DELETE n "
                "RETURN count(n) as deleted",
                stack=stack,
            ).single()
            return {"deleted": result["deleted"] if result else 0}

        with self.driver.session() as session:
            return self._retry(session.execute_write, _clear)
