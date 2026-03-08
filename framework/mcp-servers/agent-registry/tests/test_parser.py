"""Tests for YAML frontmatter parser."""

import pytest
from agent_registry.server import parse_frontmatter


class TestFrontmatterParser:
    """Test parse_frontmatter() function."""

    def test_parse_valid_frontmatter(self):
        """Parse valid frontmatter with all field types."""
        content = """---
name: test-agent
description: A test agent
version: 1.0
keywords:
  - test
  - agent
  - discovery
scope:
  primary:
    - Testing
    - Validation
---

# Your Role

Test agent content here."""

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter is not None
        assert frontmatter["name"] == "test-agent"
        assert frontmatter["description"] == "A test agent"
        assert frontmatter["version"] == "1.0"
        assert frontmatter["keywords"] == ["test", "agent", "discovery"]
        assert "Testing" in frontmatter["scope"]["primary"]
        assert "# Your Role" in body

    def test_parse_inline_array(self):
        """Parse inline array syntax."""
        content = """---
name: test-agent
keywords: [test, agent, discovery]
---

Body content."""

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter is not None
        assert frontmatter["keywords"] == ["test", "agent", "discovery"]

    def test_parse_no_frontmatter(self):
        """Handle content without frontmatter."""
        content = "# Just a markdown file\n\nNo frontmatter here."

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter is None
        assert body == content

    def test_parse_incomplete_frontmatter(self):
        """Handle incomplete frontmatter delimiter."""
        content = """---
name: test-agent

This is not closed."""

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter is None

    def test_parse_quoted_values(self):
        """Handle quoted values in frontmatter."""
        content = """---
name: "test-agent"
description: "A quoted description"
---

Body."""

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter is not None
        assert frontmatter["name"] == "test-agent"
        assert frontmatter["description"] == "A quoted description"

    def test_parse_empty_list(self):
        """Handle empty fields."""
        content = """---
name: test-agent
keywords:
description: Test
---

Body."""

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter is not None
        assert frontmatter["name"] == "test-agent"
        # keywords should be an empty list or not set
        # depending on implementation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
