"""
Neo4j Schema Initialization for Memento Knowledge Graph

Manages constraints, indexes, and full-text search setup.
Called on first server start to ensure schema is ready.
"""

from neo4j import Driver


# Node labels used in the knowledge graph
NODE_LABELS = [
    "Decision", "Learning", "Pattern", "Endpoint", "EnvVar",
    "Sensor", "GPIOPin", "Agent", "Plan", "Stack", "Note", "BlockerResolution"
]

# Relationship types
RELATIONSHIP_TYPES = [
    "BELONGS_TO",       # Entity -> Stack
    "MADE_BY",          # Decision/Learning -> Agent
    "USED_IN",          # Decision/Learning -> Plan
    "RELATES_TO",       # Entity -> Entity (generic)
    "SUPERSEDES",       # Decision -> Decision (newer overrides older)
    "DEPENDS_ON",       # Decision -> Decision, Plan -> Plan
    "AFFECTS",          # Learning -> Endpoint/EnvVar/Sensor
    "USES",             # Plan -> Endpoint, Agent -> Endpoint
    "CONFIGURES",       # Agent -> EnvVar
    "MONITORS",         # Agent -> Sensor
    "CONTROLS",         # Agent -> GPIOPin
]


def init_schema(driver: Driver) -> dict:
    """Initialize Neo4j schema with constraints, indexes, and full-text search.

    Returns dict with counts of created constraints and indexes.
    """
    stats = {"constraints": 0, "indexes": 0, "errors": []}

    with driver.session() as session:
        # Uniqueness constraints (also creates indexes)
        for label in NODE_LABELS:
            try:
                session.run(
                    f"CREATE CONSTRAINT {label.lower()}_id_unique "
                    f"IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
                )
                stats["constraints"] += 1
            except Exception as e:
                stats["errors"].append(f"Constraint {label}: {e}")

        # Property indexes for common query patterns
        index_definitions = [
            ("Decision", "stack"),
            ("Decision", "agent"),
            ("Decision", "plan_id"),
            ("Decision", "created_at"),
            ("Learning", "stack"),
            ("Learning", "agent"),
            ("Learning", "category"),
            ("Learning", "created_at"),
            ("Pattern", "stack"),
            ("Pattern", "name"),
            ("Endpoint", "stack"),
            ("Endpoint", "path"),
            ("Endpoint", "method"),
            ("EnvVar", "stack"),
            ("EnvVar", "name"),
            ("Sensor", "stack"),
            ("Sensor", "name"),
            ("GPIOPin", "stack"),
            ("GPIOPin", "pin_number"),
            ("Agent", "stack"),
            ("Agent", "name"),
            ("Plan", "stack"),
            ("Plan", "status"),
            ("Stack", "active"),
            ("Note", "stack"),
            ("Note", "agent"),
            ("BlockerResolution", "stack"),
        ]

        for label, prop in index_definitions:
            try:
                idx_name = f"idx_{label.lower()}_{prop}"
                session.run(
                    f"CREATE INDEX {idx_name} IF NOT EXISTS "
                    f"FOR (n:{label}) ON (n.{prop})"
                )
                stats["indexes"] += 1
            except Exception as e:
                stats["errors"].append(f"Index {label}.{prop}: {e}")

        # Full-text index for content search across knowledge entities
        try:
            session.run(
                "CREATE FULLTEXT INDEX knowledge_content IF NOT EXISTS "
                "FOR (n:Decision|Learning|Note|BlockerResolution|Pattern) "
                "ON EACH [n.content, n.description]"
            )
            stats["indexes"] += 1
        except Exception as e:
            stats["errors"].append(f"Full-text index: {e}")

        # Full-text index for endpoint/component search
        try:
            session.run(
                "CREATE FULLTEXT INDEX component_search IF NOT EXISTS "
                "FOR (n:Endpoint|EnvVar|Sensor|GPIOPin) "
                "ON EACH [n.name, n.purpose, n.path, n.description]"
            )
            stats["indexes"] += 1
        except Exception as e:
            stats["errors"].append(f"Component full-text index: {e}")

    return stats


def verify_schema(driver: Driver) -> dict:
    """Verify that schema is properly initialized.

    Returns dict with current schema state.
    """
    with driver.session() as session:
        constraints = session.run("SHOW CONSTRAINTS").data()
        indexes = session.run("SHOW INDEXES").data()

        return {
            "constraints_count": len(constraints),
            "indexes_count": len(indexes),
            "constraints": [
                {"name": c.get("name"), "type": c.get("type")}
                for c in constraints
            ],
            "indexes": [
                {"name": i.get("name"), "type": i.get("type"), "state": i.get("state")}
                for i in indexes
            ],
        }


def drop_all(driver: Driver) -> dict:
    """Drop all data and schema. USE WITH CAUTION.

    Returns counts of deleted items.
    """
    with driver.session() as session:
        # Delete all relationships and nodes
        result = session.run("MATCH (n) DETACH DELETE n").consume()

        # Drop constraints
        constraints = session.run("SHOW CONSTRAINTS").data()
        for c in constraints:
            try:
                session.run(f"DROP CONSTRAINT {c['name']}")
            except Exception:
                pass

        # Drop indexes
        indexes = session.run("SHOW INDEXES").data()
        for i in indexes:
            try:
                session.run(f"DROP INDEX {i['name']}")
            except Exception:
                pass

        return {
            "nodes_deleted": result.counters.nodes_deleted,
            "relationships_deleted": result.counters.relationships_deleted,
            "constraints_dropped": len(constraints),
            "indexes_dropped": len(indexes),
        }
