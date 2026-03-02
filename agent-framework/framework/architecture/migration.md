# Migration to Stack-Local Agent Architecture

## Status: Complete ✅

This file documents the migration to the **stack-local agent discovery** model. All migration phases are complete as of v2.0 (March 2026).

## Current Standard (target)

- **Stack-local agents (source of truth):** `stacks/STACKNAME/agents/*.agent.md`
- **Workspace uses relative paths only:** `agents`, `.`, and `monorepo/...`
- **Monorepo selection:** `stacks/STACKNAME/monorepo -> /absolute/path/to/clone`

> Note: The framework-level `agents/` may still exist as an optional shared library, but stacks should copy/symlink what they need into their own `stacks/STACKNAME/agents/` so the stack workspace stays self-contained.

## Deprecated Patterns

- Treating framework-level `agents/` as the *primary* place for all agents.
- Using `~`, `${userHome}`, or `${env:...}` inside `.code-workspace` `folders[].path`.
- Previously used `.github/agents/` instead of the current `agents/` pattern.

## Migration Steps

### Phase 1: Ensure stacks follow the new layout

For each stack:

1. Ensure `stacks/STACKNAME/agents/` exists and contains the stack’s agents.
2. Ensure the stack workspace points to:
	- `"🤖 Agents" -> agents`
	- `"📚 Stack" -> .`
	- `"📦 Service" -> monorepo/<path>`
3. Create/update `stacks/STACKNAME/monorepo` symlink to the desired clone.

### Phase 2: Fix OCPP20 Rust stack paths (example)

The OCPP 2.0 Rust stack should reference the service via:

- `stacks/ocpp20-rust/monorepo/appfs/ebee/ocpp20`
- Rust-analyzer linked project: `stacks/ocpp20-rust/monorepo/appfs/ebee/ocpp20/Cargo.toml`

### Phase 3: Clean up legacy per-stack agent directories

If a stack still has a `.github/agents/` folder (legacy), migrate/delete it after verifying the agents exist in `stacks/STACKNAME/agents/`.

### Phase 4: Archive legacy guidance

If you still have one-off legacy notes or old agent versions, move them under `docs/` or `.archive/` and ensure all docs refer to the stack-local `.github/agents` model.

## Completion Notes

All migration steps have been completed:

- All stacks use `stacks/STACKNAME/agents/` as the primary agent location
- Legacy `.github/agents/` directories have been migrated
- Workspaces use relative paths only (no `~`, `${userHome}`, or `${env:...}`)
- Framework-level `agents/` is retained as an optional shared library
- Framework now includes 3 MCP servers (agent-registry, knowledge-search, plan-execution), 12 scripts, and 27 agents across 2 stacks
- Plan schema v2.0 with parallel execution, knowledge management, and autonomous execution via Anthropic API
