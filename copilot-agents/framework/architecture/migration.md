# Migration to Stack-Local Agent Architecture

## Status: In Progress

This file tracks the migration to the **stack-local agent discovery** model.

## Current Standard (target)

- **Stack-local agents (source of truth):** `stacks/STACKNAME/.github/agents/*.agent.md`
- **Workspace uses relative paths only:** `.github/agents`, `.`, and `monorepo/...`
- **Monorepo selection:** `stacks/STACKNAME/monorepo -> /absolute/path/to/clone`

> Note: The repo-level `.github/agents/` may still exist as an optional shared library, but stacks should copy/symlink what they need into their own `stacks/STACKNAME/.github/agents/` so the stack workspace stays self-contained.

## Deprecated Patterns

- Treating repo-level `.github/agents/` as the *primary* place for all agents.
- Using `~`, `${userHome}`, or `${env:...}` inside `.code-workspace` `folders[].path`.
- Using `stacks/STACKNAME/agents/` instead of `stacks/STACKNAME/.github/agents/`.

## Migration Steps

### Phase 1: Ensure stacks follow the new layout

For each stack:

1. Ensure `stacks/STACKNAME/.github/agents/` exists and contains the stack’s agents.
2. Ensure the stack workspace points to:
	- `"🤖 Agents" -> .github/agents`
	- `"📚 Stack" -> .`
	- `"📦 Service" -> monorepo/<path>`
3. Create/update `stacks/STACKNAME/monorepo` symlink to the desired clone.

### Phase 2: Fix OCPP20 Rust stack paths (example)

The OCPP 2.0 Rust stack should reference the service via:

- `stacks/ocpp20-rust/monorepo/appfs/ebee/ocpp20`
- Rust-analyzer linked project: `stacks/ocpp20-rust/monorepo/appfs/ebee/ocpp20/Cargo.toml`

### Phase 3: Clean up legacy per-stack agent directories

If a stack still has an `agents/` folder (legacy), migrate/delete it after verifying the agents exist in `stacks/STACKNAME/.github/agents/`.

### Phase 4: Archive legacy guidance

If you still have one-off legacy notes or old agent versions, move them under `docs/` or `.archive/` and ensure all docs refer to the stack-local `.github/agents` model.

## Next Steps

1. Sweep stacks for `stacks/*/agents/` and remove once migrated
2. Sweep workspaces for `~` / `${userHome}` / `${env:...}` in `folders[].path` and convert to relative + `monorepo/`
3. Keep repo-level `.github/agents/` only as optional shared library
