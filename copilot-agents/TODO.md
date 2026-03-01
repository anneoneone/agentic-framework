TODO:

- [x] Define agent commands at top of file → Added `## Commands` table to writer.agent.md v1.1
- [x] Agent description text shows subcommands (e.g. --plan Create a new plan) → Writer now documents `create-stack`, `--update STACK`, `--update --all`
- [x] writer: --update STACK which updates a certain stack after updating the meta-agents stack → Implemented in writer.agent.md v1.1 with 5-step Update Workflow
- [x] Create a general instructions file with general ruleset → Created `framework/core/guidelines/GENERAL_RULES.md` with ALWAYS DO / ASK FIRST / NEVER DO sections
  - [x] ALWAYS DO
    - [x] when creating documentation: create atomic documents
    - [x] after changing code: check if stack related documentation is up to date (update, add or remove docs)
  - [x] ASK FIRST
    - [x] before creating a new document, especially markdown docs
  - [x] NEVER DO
    - [x] write snapshot like information in docs (e.g. "50-60% reduction from baseline")
- [x] shared knowledge files should be atomic and have a very good title → Split both SHARED_KNOWLEDGE.md files into atomic docs under `docs/knowledge/`

## Completed in Phase 1 (not originally in TODO)

- [x] Agent frontmatter JSON Schema (`framework/schemas/agent-frontmatter.schema.json`)
- [x] Frontmatter added to all 19 agents (name, description, version, keywords, scope)
- [x] Plan status normalization: `done` → `completed` across 31 plan files (141 fixes)
- [x] Agent validation script (`framework/scripts/validate-agent.py`)
- [x] Specialist agent template v2.0 with validation pipeline and strict rules

## Future TODO

- [ ] Integrate MCP servers into agent definitions (Phase 2)
- [ ] Implement Anthropic Batch API for parallel plan execution (Phase 3)
- [ ] Add `@planner` subcommands: `--review`, `--replan` (Phase 2)
- [ ] JSON Plan v2.0 schema with `parallel_group`, `priority`, `estimated_tokens` (Phase 2)
- [ ] Knowledge auto-discovery: agents scan `docs/knowledge/` on startup with 24h TTL cache (Phase 2)
