#!/usr/bin/env python3
"""Example usage of the Agent Registry.

This script demonstrates how to use the AgentRegistry class directly
(without MCP transport) for agent discovery and management.

Run with:
    python example_usage.py
"""

import json
from pathlib import Path
from server import AgentRegistry


def main():
    """Run example queries."""
    print("=" * 70)
    print("Agent Registry Examples")
    print("=" * 70)

    # Initialize registry
    registry = AgentRegistry()
    print(f"\nRegistry root: {registry.root}\n")

    # Example 1: List all agents
    print("1. LIST ALL AGENTS")
    print("-" * 70)
    agents = registry.list_agents()
    print(f"Found {len(agents)} agents\n")
    for agent in agents[:5]:  # Show first 5
        print(f"  • {agent.name:25} v{agent.version:4} | {agent.description[:40]}")
    if len(agents) > 5:
        print(f"  ... and {len(agents) - 5} more")

    # Example 2: Get specific agent
    print("\n2. GET AGENT DETAILS")
    print("-" * 70)
    if agents:
        agent_name = agents[0].name
        full_agent = registry.get_agent(agent_name)
        if full_agent:
            print(f"Agent: {full_agent.name}")
            print(f"Description: {full_agent.description}")
            print(f"Version: {full_agent.version}")
            print(f"Keywords: {', '.join(full_agent.keywords)}")
            print(f"Line count: {full_agent.line_count}")
            print(f"Path: {full_agent.path}")

    # Example 3: Find agents for a task
    print("\n3. FIND AGENTS FOR TASK")
    print("-" * 70)
    task = "I need to build API documentation for a Python microservice"
    print(f"Task: {task}\n")

    results = registry.find_agents_for_task(task)
    if results:
        print(f"Found {len(results)} matching agents:\n")
        for i, (agent, score) in enumerate(results[:5], 1):
            quality = (
                "excellent" if score >= 10 else "good" if score >= 5 else "fair"
            )
            print(f"  {i}. {agent.name:25} (score: {score:5.1f}, {quality})")
            print(f"     {agent.description}")
    else:
        print("No matching agents found")

    # Example 4: List agents by stack
    print("\n4. LIST AGENTS BY STACK")
    print("-" * 70)
    stacks = set(a.stack for a in agents if a.stack)
    if stacks:
        for stack in sorted(stacks)[:3]:  # Show first 3 stacks
            stack_agents = registry.list_agents(stack)
            print(f"\n  Stack: {stack} ({len(stack_agents)} agents)")
            for agent in stack_agents[:3]:
                print(f"    • {agent.name}: {agent.description}")
            if len(stack_agents) > 3:
                print(f"    ... and {len(stack_agents) - 3} more")

    # Example 5: Validate an agent
    print("\n5. VALIDATE AGENT")
    print("-" * 70)
    agent_files = registry.find_agent_files()
    if agent_files:
        test_file = agent_files[0]
        print(f"Validating: {test_file.relative_to(registry.root)}\n")

        result = registry.validate_agent(str(test_file))
        if result.valid:
            print("✓ Agent is valid")
        else:
            print("✗ Agent has errors:")
            for error in result.errors:
                print(f"  ERROR: {error}")

        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  WARN: {warning}")

    # Example 6: Get capability map
    print("\n6. CAPABILITY MAP")
    print("-" * 70)
    if stacks:
        stack = next(iter(stacks))
        cap_map = registry.get_capability_map(stack)
        print(f"\nCapability map for stack: {stack}")
        print(f"Keywords indexed: {len(cap_map)}\n")

        # Show first 10 keywords
        for keyword in sorted(cap_map.keys())[:10]:
            agents_with_kw = cap_map[keyword]
            print(f"  {keyword:20} → {', '.join(agents_with_kw)}")

        if len(cap_map) > 10:
            print(f"  ... and {len(cap_map) - 10} more keywords")

    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
