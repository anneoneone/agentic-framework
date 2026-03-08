# General Rules for All Agents

These rules apply to every agent in the framework, regardless of stack or specialization.

## ALWAYS DO

- **Atomic documents**: One topic per file. Never combine unrelated concerns.
- **Update docs after code changes**: Check if stack documentation is still accurate. Update, add, or remove docs as needed.
- **Consistent naming**: kebab-case for files, PascalCase for components, snake_case for Python, camelCase for TypeScript.
- **Check knowledge cache first**: Before re-analyzing, check `docs/knowledge/` for cached results.
- **Source decisions**: Every design decision must include a "because" — record the reasoning, not just the choice.
- **Use frontmatter schema**: All `.agent.md` files must have valid YAML frontmatter per `framework/schemas/agent-frontmatter.schema.json`.
- **Use status enum correctly**: Plan step statuses are `pending`, `in-progress`, `completed`, `blocked`, `skipped`. Never use `done`.
- **Validate before presenting**: Run pre-flight checks before showing any generated output (plans, agents, knowledge).
- **Reference, don't duplicate**: Use `{reference: path}` to point to shared content. Never copy-paste across files.

## ASK FIRST

- Before creating new markdown documents (check if one already covers the topic).
- Before modifying shared knowledge files (they affect all agents in the stack).
- Before changing agent boundaries or scope (may affect routing).
- Before recommending more than 5 agents per stack.
- Before creating cross-stack plans.

## NEVER DO

- **Write snapshot metrics without context**: Don't write "50-60% reduction" — reduction from what baseline? When measured? Include absolute numbers or remove.
- **Duplicate content across files**: If the same information exists in two places, one will become stale. Reference instead.
- **Create agents without keywords**: Every agent needs keywords for discovery. No exceptions.
- **Skip validation steps**: Always validate generated output (plans, agents, configs).
- **Use absolute paths in workspace files**: Use relative paths only.
- **Auto-archive plans**: Archival is always manual, confirmed by the user.
- **Modify files outside your scope**: Delegate to the appropriate specialist agent.
- **Generate vague agent definitions**: Every agent must have concrete file paths, specific patterns, and clear boundaries.
