# Knowledge Sync

Sync knowledge from completed plan steps to the knowledge graph and JSONL files.

## Input

`$ARGUMENTS` can be:
- Empty: sync the most recently completed plan in the current stack
- A plan file path: `stacks/<stack>/plans/<plan_id>.json`
- `--import <stack>`: import all existing JSONL/MD knowledge for a stack into Neo4j
- `--import-all`: import knowledge for all stacks
- `--dry-run`: show what would be synced without writing

## Workflow

### Step 1: Determine mode

- If `--import` or `--import-all`, run bulk import mode (Step 5)
- Otherwise, find the plan to sync

### Step 2: Load plan

If no path given, find the most recently completed plan in the current stack's `plans/` directory.
Read the plan JSON and identify completed steps.

### Step 3: Extract knowledge

For each completed step, extract knowledge items from:
1. **Explicit**: `step.knowledge.decisions[]`, `step.knowledge.learnings[]`
2. **Output summary**: If no explicit knowledge, create a note from `step.output.summary`

Show the user what was found:
```
Knowledge items found: N
  [D] Decision about X...
  [L] Learned that Y...
  [N] Step completed: Z...
```

### Step 4: Sync to storage

1. **JSONL**: Write items to `stacks/<stack>/docs/knowledge/plan-<plan_id>-knowledge.jsonl`
2. **Neo4j** (if available): Push via memento-knowledge MCP:
   ```
   memento-knowledge.add_decision(content="...", stack="...", plan_id="...", agent="...")
   memento-knowledge.add_learning(content="...", stack="...", category="...", agent="...")
   ```
   If Neo4j is unavailable, knowledge is still saved to JSONL.

3. Show sync summary:
```
Synced: N items (D decisions, L learnings, N notes)
JSONL: stacks/<stack>/docs/knowledge/plan-<id>-knowledge.jsonl
Neo4j: synced / unavailable
```

### Step 5: Bulk import mode

For `--import <stack>` or `--import-all`:
```bash
python framework/scripts/knowledge-sync.py --import-stack <stack>
# or
python framework/scripts/knowledge-sync.py --import-all
```

This reads all existing JSONL and Markdown files from `stacks/<stack>/docs/knowledge/`
and imports them into the Neo4j knowledge graph with relationship inference.

### Rules

- Always write to JSONL (works offline, no Neo4j required)
- Neo4j sync is best-effort — don't fail if unavailable
- Deduplicate: don't re-import items that already exist in JSONL
- After sync, suggest running `/show-plan` to verify updated knowledge
