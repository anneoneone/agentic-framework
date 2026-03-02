#!/usr/bin/env python3
"""Agent Registry MCP Server.

Provides programmatic agent discovery and routing via MCP tools.
Replaces file-scanning protocol with structured registry queries.

Tools:
  - list_agents: Discover agents by stack
  - get_agent: Retrieve full agent metadata
  - find_agents_for_task: Find agents matching a task
  - validate_agent: Validate agent file structure
  - get_capability_map: Build capability index for a stack
"""

import asyncio
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.models import InitializationOptions


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class AgentMetadata:
    """Parsed agent metadata from frontmatter."""

    name: str
    description: str
    version: str
    keywords: list[str]
    scope: dict[str, Any]
    stack: Optional[str] = None
    path: Optional[str] = None
    line_count: int = 0


@dataclass
class AgentSummary:
    """Brief agent summary for list operations."""

    name: str
    description: str
    version: str
    keywords: list[str]
    stack: Optional[str] = None
    path: Optional[str] = None


@dataclass
class ValidationResult:
    """Agent validation results."""

    path: str
    valid: bool
    errors: list[str]
    warnings: list[str]
    info: list[str]


# ============================================================================
# Cache Management
# ============================================================================


class AgentCache:
    """In-memory cache with TTL for agent metadata."""

    def __init__(self, ttl_hours: int = 24):
        self.ttl_seconds = ttl_hours * 3600
        self.agents: dict[str, tuple[AgentMetadata, float]] = {}
        self.capability_map: dict[str, tuple[dict[str, set[str]], float]] = {}

    def get_agent(self, name: str) -> Optional[AgentMetadata]:
        """Retrieve cached agent if valid."""
        if name in self.agents:
            metadata, timestamp = self.agents[name]
            if time.time() - timestamp < self.ttl_seconds:
                return metadata
            del self.agents[name]
        return None

    def set_agent(self, name: str, metadata: AgentMetadata) -> None:
        """Cache agent metadata."""
        self.agents[name] = (metadata, time.time())

    def get_capability_map(self, stack: str) -> Optional[dict[str, set[str]]]:
        """Retrieve cached capability map if valid."""
        if stack in self.capability_map:
            cap_map, timestamp = self.capability_map[stack]
            if time.time() - timestamp < self.ttl_seconds:
                return cap_map
            del self.capability_map[stack]
        return None

    def set_capability_map(self, stack: str, cap_map: dict[str, set[str]]) -> None:
        """Cache capability map."""
        self.capability_map[stack] = (cap_map, time.time())

    def clear(self) -> None:
        """Clear all cached data."""
        self.agents.clear()
        self.capability_map.clear()


# ============================================================================
# Frontmatter Parser
# ============================================================================


def parse_frontmatter(content: str) -> tuple[Optional[dict[str, Any]], str]:
    """Extract and parse YAML frontmatter from markdown content.

    Uses simple regex-based parsing to avoid external dependencies.
    Supports:
      - Key-value pairs: name: value
      - List items: - item
      - Inline arrays: [item1, item2]

    Args:
        content: Raw markdown content

    Returns:
        Tuple of (frontmatter_dict, body_text) or (None, content) if no frontmatter
    """
    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    frontmatter_text = content[3:end].strip()
    body = content[end + 3 :].strip()

    data: dict[str, Any] = {}
    current_key: Optional[str] = None
    current_list: Optional[list[str]] = None

    for line in frontmatter_text.split("\n"):
        line = line.rstrip()
        if not line:
            continue

        # List item: "  - value"
        if line.startswith("  - ") and current_key:
            if current_list is None:
                current_list = []
                data[current_key] = current_list
            current_list.append(line.strip("- ").strip().strip("'\""))
            continue

        # Key-value pair: "key: value"
        match = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if match:
            current_key = match.group(1)
            value = match.group(2).strip().strip("'\"")
            current_list = None

            if value.startswith("[") and value.endswith("]"):
                # Inline array: [item1, item2]
                items = [
                    v.strip().strip("'\"")
                    for v in value[1:-1].split(",")
                    if v.strip()
                ]
                data[current_key] = items
            elif value:
                data[current_key] = value
            continue

    return data, body


# ============================================================================
# Agent Discovery
# ============================================================================


class AgentRegistry:
    """Manages agent discovery and routing."""

    def __init__(self, root_path: Optional[Path] = None):
        """Initialize registry.

        Args:
            root_path: Path to copilot-agents root. If None, auto-detected
                      from server location.
        """
        if root_path is None:
            # Auto-detect: server is in framework/mcp-servers/agent-registry/
            # Root should be copilot-agents/
            server_dir = Path(__file__).parent.parent.parent.parent  # agent-registry -> copilot-agents
            root_path = server_dir

        self.root = root_path.resolve()
        self.cache = AgentCache(ttl_hours=24)

    def find_agent_files(self, stack: Optional[str] = None) -> list[Path]:
        """Find all .agent.md files.

        Args:
            stack: Optional stack name to limit search

        Returns:
            List of agent file paths
        """
        agents: list[Path] = []

        if stack:
            # Stack-specific agents
            pattern = f"stacks/{stack}/agents/*.agent.md"
            agents.extend(self.root.glob(pattern))
        else:
            # All agents
            agents.extend(self.root.glob("**/*.agent.md"))

        # Also include framework agents
        agents.extend(self.root.glob("framework/core/**/*.agent.md"))

        # Resolve symlinks and deduplicate
        resolved = set()
        for agent in agents:
            try:
                resolved.add(agent.resolve())
            except (OSError, RuntimeError):
                # Skip broken symlinks
                pass

        return sorted(list(resolved))

    def _extract_stack(self, agent_path: Path) -> Optional[str]:
        """Extract stack name from agent file path.

        Args:
            agent_path: Path to agent file

        Returns:
            Stack name or None
        """
        parts = agent_path.parts
        if "stacks" in parts:
            idx = parts.index("stacks")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return None

    def parse_agent(self, path: Path) -> Optional[AgentMetadata]:
        """Parse agent file into metadata.

        Args:
            path: Path to .agent.md file

        Returns:
            AgentMetadata or None if invalid
        """
        # Check cache first
        name = path.stem.replace(".agent", "")
        cached = self.cache.get_agent(name)
        if cached:
            return cached

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            # File not readable
            return None

        frontmatter, body = parse_frontmatter(content)
        if not frontmatter:
            return None

        # Extract required fields
        try:
            metadata = AgentMetadata(
                name=frontmatter.get("name", name),
                description=frontmatter.get("description", ""),
                version=frontmatter.get("version", "0.0"),
                keywords=frontmatter.get("keywords", []),
                scope=frontmatter.get("scope", {}),
                stack=self._extract_stack(path),
                path=str(path.relative_to(self.root)),
                line_count=len(content.split("\n")),
            )

            # Cache it
            self.cache.set_agent(metadata.name, metadata)
            return metadata

        except (KeyError, ValueError):
            return None

    def list_agents(self, stack: Optional[str] = None) -> list[AgentSummary]:
        """List all agents with optional stack filter.

        Args:
            stack: Optional stack name to filter

        Returns:
            List of agent summaries sorted by name
        """
        summaries: list[AgentSummary] = []

        for agent_path in self.find_agent_files(stack):
            metadata = self.parse_agent(agent_path)
            if metadata:
                summaries.append(
                    AgentSummary(
                        name=metadata.name,
                        description=metadata.description,
                        version=metadata.version,
                        keywords=metadata.keywords,
                        stack=metadata.stack,
                        path=metadata.path,
                    )
                )

        return sorted(summaries, key=lambda a: a.name)

    def get_agent(self, name: str) -> Optional[AgentMetadata]:
        """Get full agent metadata by name.

        Args:
            name: Agent name (kebab-case)

        Returns:
            Full AgentMetadata or None
        """
        # Search for agent file
        for agent_path in self.find_agent_files():
            if agent_path.stem.replace(".agent", "") == name:
                return self.parse_agent(agent_path)

        return None

    def find_agents_for_task(
        self, task_description: str, stack: Optional[str] = None
    ) -> list[tuple[AgentSummary, float]]:
        """Find agents matching a task description.

        Extracts keywords from task and scores agents based on keyword overlap:
          - Exact match: +5 points
          - Partial match (substring): +2 points
          - Category match (both contain common word): +1 point

        Args:
            task_description: Description of the task
            stack: Optional stack to limit search

        Returns:
            List of (AgentSummary, score) tuples sorted by score descending
        """
        agents = self.list_agents(stack)

        # Extract task keywords (words > 4 chars)
        task_keywords = set(
            word.lower()
            for word in re.findall(r"\w+", task_description.lower())
            if len(word) > 4
        )

        if not task_keywords:
            # Fallback: return all agents
            return [(agent, 0.0) for agent in agents]

        results: list[tuple[AgentSummary, float]] = []

        for agent in agents:
            score = 0.0
            agent_keywords = set(kw.lower() for kw in agent.keywords)
            agent_description = agent.description.lower()

            # Score keyword matches
            for task_kw in task_keywords:
                # Exact match
                if task_kw in agent_keywords:
                    score += 5.0
                else:
                    # Partial match (substring)
                    for agent_kw in agent_keywords:
                        if task_kw in agent_kw or agent_kw in task_kw:
                            score += 2.0
                            break
                    else:
                        # Category match (word appears in description)
                        if task_kw in agent_description:
                            score += 1.0

            if score > 0:
                results.append((agent, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def validate_agent(self, path: str) -> ValidationResult:
        """Validate agent file structure.

        Checks:
          1. YAML frontmatter presence and validity
          2. Required fields (name, description, version)
          3. Optional but recommended fields (keywords, scope)
          4. Section structure (role, scope, key files)
          5. File naming consistency
          6. Line count range

        Args:
            path: Path to agent file

        Returns:
            ValidationResult with errors, warnings, and info messages
        """
        agent_path = Path(path)
        result = ValidationResult(path=path, valid=True, errors=[], warnings=[], info=[])

        if not agent_path.exists():
            result.valid = False
            result.errors.append(f"File not found: {path}")
            return result

        try:
            content = agent_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            result.valid = False
            result.errors.append(f"Cannot read file: {e}")
            return result

        lines = content.split("\n")
        line_count = len(lines)

        # Check frontmatter
        frontmatter, body = parse_frontmatter(content)

        if frontmatter is None:
            result.valid = False
            result.errors.append("Missing YAML frontmatter (--- block)")
        else:
            # Required fields
            if "name" not in frontmatter:
                result.valid = False
                result.errors.append("Missing required field: name")
            else:
                name = frontmatter["name"]
                expected_name = agent_path.stem.replace(".agent", "")
                if name != expected_name:
                    result.valid = False
                    result.errors.append(
                        f"name '{name}' doesn't match filename '{expected_name}'"
                    )
                if not re.match(r"^[a-z][a-z0-9-]*$", name):
                    result.valid = False
                    result.errors.append(
                        f"name '{name}' must be lowercase kebab-case"
                    )

            if "description" not in frontmatter:
                result.valid = False
                result.errors.append("Missing required field: description")
            elif len(frontmatter["description"]) < 10:
                result.warnings.append("description is very short (< 10 chars)")
            elif len(frontmatter["description"]) > 200:
                result.warnings.append("description exceeds 200 chars")

            if "version" not in frontmatter:
                result.valid = False
                result.errors.append("Missing required field: version")
            elif not re.match(r"^\d+\.\d+", str(frontmatter["version"])):
                result.valid = False
                result.errors.append(
                    f"version '{frontmatter['version']}' must be major.minor format"
                )

            # Recommended fields
            if "keywords" not in frontmatter:
                result.warnings.append(
                    "Missing recommended field: keywords (needed for discovery)"
                )
            else:
                kw = frontmatter["keywords"]
                if isinstance(kw, list) and len(kw) < 3:
                    result.warnings.append(
                        f"Only {len(kw)} keywords — recommend at least 3"
                    )

            if "scope" not in frontmatter:
                result.warnings.append("Missing recommended field: scope")

        # Check section structure
        body_lower = body.lower() if body else ""
        headings = [
            line.strip().lower().lstrip("#").strip()
            for line in lines
            if line.strip().startswith("#")
        ]

        required_sections = ["role", "scope", "key files"]
        section_aliases = {
            "role": ["role", "your role", "identity"],
            "scope": ["scope", "your expertise", "expertise", "responsibilities"],
            "key files": ["key files", "primary code", "project context"],
        }

        for section_name, aliases in section_aliases.items():
            found = any(alias in headings for alias in aliases)
            if not found:
                result.warnings.append(
                    f"Missing section: {section_name} (or aliases: {', '.join(aliases)})"
                )

        # Check line count
        if line_count < 30:
            result.warnings.append(f"File is short ({line_count} lines) — may be vague")
        elif line_count > 250:
            result.warnings.append(f"File is long ({line_count} lines) — consider externalizing")

        return result

    def get_capability_map(self, stack: str) -> dict[str, set[str]]:
        """Build keyword → agent name map for a stack.

        Useful for quick capability lookups.

        Args:
            stack: Stack name

        Returns:
            Dict mapping keyword → set of agent names
        """
        # Check cache
        cached = self.cache.get_capability_map(stack)
        if cached:
            return cached

        cap_map: dict[str, set[str]] = {}
        agents = self.list_agents(stack)

        for agent in agents:
            for keyword in agent.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower not in cap_map:
                    cap_map[keyword_lower] = set()
                cap_map[keyword_lower].add(agent.name)

        # Cache it
        self.cache.set_capability_map(stack, cap_map)
        return cap_map


# ============================================================================
# MCP Server
# ============================================================================


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get or create global registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


# Create MCP server
server = Server("agent-registry")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_agents",
            description="List all agents with optional stack filter. Returns agent summaries with name, description, version, keywords, and stack.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stack": {
                        "type": "string",
                        "description": "Optional stack name to filter agents (e.g., 'live-moafunk', 'gartenroboter3000')",
                    }
                },
            },
        ),
        Tool(
            name="get_agent",
            description="Retrieve full agent metadata including frontmatter, body sections, and file info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Agent name in kebab-case (e.g., 'documentation', 'planner')",
                    }
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="find_agents_for_task",
            description="Find agents matching a task description. Extracts keywords from task and returns ranked agents based on keyword overlap (exact=5pts, partial=2pts, category=1pt).",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task to find agents for",
                    },
                    "stack": {
                        "type": "string",
                        "description": "Optional stack name to limit search",
                    },
                },
                "required": ["task_description"],
            },
        ),
        Tool(
            name="validate_agent",
            description="Validate an agent file for correctness. Checks frontmatter, required fields, section structure, and naming conventions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to agent file (relative to copilot-agents root)",
                    }
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="get_capability_map",
            description="Get capability index for a stack. Returns mapping of keywords to agent names.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stack": {
                        "type": "string",
                        "description": "Stack name",
                    }
                },
                "required": ["stack"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    registry = get_registry()

    try:
        if name == "list_agents":
            stack = arguments.get("stack")
            agents = registry.list_agents(stack)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        [asdict(agent) for agent in agents],
                        indent=2,
                        default=str,
                    ),
                )
            ]

        elif name == "get_agent":
            agent_name = arguments.get("name")
            if not agent_name:
                return [TextContent(type="text", text="Error: 'name' parameter required")]

            agent = registry.get_agent(agent_name)
            if not agent:
                return [TextContent(type="text", text=f"Agent not found: {agent_name}")]

            return [TextContent(type="text", text=json.dumps(asdict(agent), indent=2, default=str))]

        elif name == "find_agents_for_task":
            task_desc = arguments.get("task_description")
            stack = arguments.get("stack")

            if not task_desc:
                return [
                    TextContent(
                        type="text",
                        text="Error: 'task_description' parameter required",
                    )
                ]

            results = registry.find_agents_for_task(task_desc, stack)
            output = [
                {
                    "agent": asdict(agent_summary),
                    "score": score,
                    "match_quality": (
                        "excellent" if score >= 10 else "good" if score >= 5 else "fair"
                    ),
                }
                for agent_summary, score in results
            ]

            return [TextContent(type="text", text=json.dumps(output, indent=2, default=str))]

        elif name == "validate_agent":
            path = arguments.get("path")
            if not path:
                return [TextContent(type="text", text="Error: 'path' parameter required")]

            full_path = registry.root / path
            result = registry.validate_agent(str(full_path))

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "path": result.path,
                            "valid": result.valid,
                            "errors": result.errors,
                            "warnings": result.warnings,
                            "info": result.info,
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "get_capability_map":
            stack = arguments.get("stack")
            if not stack:
                return [
                    TextContent(
                        type="text",
                        text="Error: 'stack' parameter required",
                    )
                ]

            cap_map = registry.get_capability_map(stack)
            # Convert sets to lists for JSON serialization
            output = {k: sorted(list(v)) for k, v in cap_map.items()}

            return [TextContent(type="text", text=json.dumps(output, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server with stdio transport."""
    async with server:
        # Server runs until stdin closes
        await server.wait_for_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
