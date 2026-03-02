# Repository structure overview

This repository contains GitHub Copilot agents and workspace configurations for the ebee monorepo.

## Directory Layout

- **[stacks/](../../stacks/)** - Stack workspaces (primary agent location)
  - Stack agents live in `stacks/STACKNAME/.github/agents/*.agent.md`
  - Each stack has `monorepo -> /path/to/clone` symlink for service paths
  - Plans stored in `stacks/STACKNAME/.copilot-agents/plans/`
  - Knowledge stored in `stacks/STACKNAME/docs/knowledge/`

- **[framework/](../)** - Framework core
  - `core/common-agents/` — Shared agents: @coordinator, @gitlab, @planner
  - `core/shared-agents/` — Domain experts reusable across stacks
  - `core/meta-agents/` — Framework management: @analyzer, @writer
  - `core/guidelines/` — GENERAL_RULES.md, TOKEN_EFFICIENCY.md
  - `mcp-servers/` — 3 MCP servers (agent-registry, knowledge-search, plan-execution)
  - `scripts/` — 12 utility scripts (validation, execution, optimization)
  - `schemas/` — JSON schemas (agent frontmatter, plan v2.0)
  - `knowledge/` — Cross-stack knowledge index
  - `telemetry/` — Token usage and agent scoring data
  - `cache/` — Adaptive cache TTL configs
  - `templates/` — Agent templates

- **[.github/agents/](../../.github/agents/)** - Root-level agent discovery (optional)
  - Kept for backward compatibility; stacks should use their own `.github/agents/`

- **[docs/](../../docs/)** - Documentation
  - `usage-guide.md` - Day-to-day workflows
  - `coordinator-usage.md` - Coordinator agent guide
  - `multi-clone-setup.md` - Multi-clone configuration
  - `stack-map.md` - Monorepo architecture reference

## Quick Navigation

- **Getting started:** See [GETTING_STARTED.md](../../GETTING_STARTED.md)
- **Framework overview:** See [README.md](../../README.md)
- **Usage guide:** See [docs/usage-guide.md](../../docs/usage-guide.md)
- **Architecture:** See [stack-architecture.md](stack-architecture.md)
- **Multi-clone setup:** See [docs/multi-clone-setup.md](../../docs/multi-clone-setup.md)
