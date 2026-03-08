"""Tests for AgentRegistry functionality."""

import pytest
from pathlib import Path
from agent_registry.server import AgentRegistry, AgentMetadata, parse_frontmatter


class TestAgentRegistry:
    """Test AgentRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create registry pointing to test agent-framework directory."""
        # Find the actual agent-framework directory in the test environment
        root = Path(__file__).parent.parent.parent.parent.parent.parent.parent / "agent-framework"
        if not root.exists():
            pytest.skip("agent-framework directory not found")
        return AgentRegistry(root)

    def test_find_agent_files(self, registry):
        """Test finding agent files."""
        agents = registry.find_agent_files()
        assert len(agents) > 0, "Should find at least some agents"
        assert all(str(a).endswith(".agent.md") for a in agents)

    def test_find_agent_files_by_stack(self, registry):
        """Test finding agents filtered by stack."""
        # Try a known stack
        agents = registry.find_agent_files(stack="live-moafunk")
        if agents:  # Stack might not exist in test environment
            assert all(
                "live-moafunk" in str(a) for a in agents
            ), "All agents should be in the specified stack"

    def test_parse_agent(self, registry):
        """Test parsing an agent file."""
        agents = registry.find_agent_files()
        if not agents:
            pytest.skip("No agents found to test")

        metadata = registry.parse_agent(agents[0])
        assert metadata is not None
        assert metadata.name is not None
        assert metadata.description is not None
        assert metadata.version is not None

    def test_list_agents(self, registry):
        """Test listing agents."""
        agents = registry.list_agents()
        assert len(agents) > 0
        assert all(a.name for a in agents)
        assert agents == sorted(agents, key=lambda a: a.name)

    def test_get_agent(self, registry):
        """Test getting a specific agent by name."""
        agents = registry.list_agents()
        if not agents:
            pytest.skip("No agents found")

        # Get first agent
        first_agent = agents[0]
        retrieved = registry.get_agent(first_agent.name)

        assert retrieved is not None
        assert retrieved.name == first_agent.name
        assert retrieved.description == first_agent.description

    def test_find_agents_for_task_empty_description(self, registry):
        """Test task search with empty description."""
        results = registry.find_agents_for_task("")
        assert results == []

    def test_find_agents_for_task(self, registry):
        """Test finding agents for a task."""
        results = registry.find_agents_for_task("I need to write documentation and API guides")

        # Should find agents with documentation-related keywords
        if results:
            # Results should be sorted by score descending
            scores = [score for _, score in results]
            assert scores == sorted(scores, reverse=True)

            # All results should have positive scores
            assert all(score > 0 for _, score in results)

    def test_validate_agent(self, registry):
        """Test agent validation."""
        agents = registry.find_agent_files()
        if not agents:
            pytest.skip("No agents found")

        result = registry.validate_agent(str(agents[0]))
        assert hasattr(result, "valid")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")

    def test_get_capability_map(self, registry):
        """Test building capability map."""
        # Find a stack with agents
        agents = registry.list_agents()
        stacks = set(a.stack for a in agents if a.stack)

        if not stacks:
            pytest.skip("No stacks found with agents")

        stack = next(iter(stacks))
        cap_map = registry.get_capability_map(stack)

        assert isinstance(cap_map, dict)
        # Map should have keywords pointing to agent names
        if cap_map:
            for keyword, agent_names in cap_map.items():
                assert isinstance(keyword, str)
                assert isinstance(agent_names, set)

    def test_cache_get_agent(self, registry):
        """Test that agent caching works."""
        agents = registry.list_agents()
        if not agents:
            pytest.skip("No agents found")

        first_name = agents[0].name

        # First call should parse the file
        agent1 = registry.get_agent(first_name)

        # Second call should return from cache
        agent2 = registry.get_agent(first_name)

        assert agent1 == agent2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
