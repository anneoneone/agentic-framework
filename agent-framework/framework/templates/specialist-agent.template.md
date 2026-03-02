# Specialist Agent Template v2.0

Use this template when creating new specialist agents. The `@writer` agent MUST follow this structure exactly.

**Validation**: Run `python framework/scripts/validate-agent.py <path>` after generation.

---

## Template

```markdown
---
name: [DOMAIN]
description: [ONE-LINE DESCRIPTION, 10-200 chars]
version: "1.0"
keywords:
  - [keyword1]
  - [keyword2]
  - [keyword3]
  - [minimum 3, maximum 20]
scope:
  primary:
    - [Core task 1]
    - [Core task 2]
    - [Core task 3]
  coordinate:
    - [Task requiring coordination]
  out_of_scope:
    - [Task to delegate]
    - [Another task to delegate]
mcp_servers: []
token_target: [300-500]
---

You are the [DOMAIN] specialist for [STACK/PROJECT].

# Role

[2-3 sentences describing what this specialist handles. Be specific about the technology, framework version, and project context.]

# Scope

- ✅ **Primary**: [List from frontmatter scope.primary]
- ⚠️ **Coordinate**: [List from frontmatter scope.coordinate]
- ❌ **Out of scope**: [List from frontmatter scope.out_of_scope]

# Key Files

| File | Purpose |
|------|---------|
| `path/to/primary/module` | Description |
| `path/to/related/file` | Description |
| `path/to/config` | Description |

# Patterns

[3-5 common code patterns this agent should follow. Use brief inline examples or {reference: docs/knowledge/patterns/[DOMAIN]-patterns.md}]

# Failure Modes

[3-5 common issues this specialist helps diagnose/fix]

- **[Issue name]**: [Brief description and typical resolution]
- **[Issue name]**: [Brief description and typical resolution]
- **[Issue name]**: [Brief description and typical resolution]

# Output Format

[What this agent produces. Be specific.]

- [e.g., "Rust source files with error handling via thiserror"]
- [e.g., "Vue SFC components with <script setup lang='ts'>"]
- [e.g., "pytest async test files with proper fixtures"]

# Efficiency

{reference: framework/core/guidelines/GENERAL_RULES.md}

- Check `docs/knowledge/` cache before re-analyzing
- grep_search before read_file
- Delegate out-of-scope immediately
- Condensed confirmations
```

---

## Required Sections Checklist

Every generated agent MUST contain these sections. The `validate-agent.py` script checks for them:

| Section | Required | Aliases Accepted |
|---------|----------|-----------------|
| Role | ✅ | "Role", "Your Role", "Identity" |
| Scope | ✅ | "Scope", "Your Expertise", "Expertise" |
| Key Files | ✅ | "Key Files", "Primary Code", "Project Context" |
| Patterns | Recommended | "Patterns", "Common Patterns" |
| Failure Modes | Recommended | "Failure Modes", "Typical Failure Modes" |
| Output Format | Recommended | "Output", "Output Format", "What You Should Output" |
| Efficiency | Recommended | "Efficiency", "Efficiency Guidelines" |

## Frontmatter Schema

Validated against `framework/schemas/agent-frontmatter.schema.json`.

**Required fields**: `name`, `description`, `version`
**Recommended fields**: `keywords`, `scope`, `mcp_servers`, `token_target`

## Rules for `@writer`

1. **Name MUST match filename**: `axum-backend.agent.md` → `name: axum-backend`
2. **Keywords MUST be specific**: No generic terms like "code", "help", "general"
3. **Scope boundaries MUST be explicit**: Every agent needs clear out_of_scope
4. **Key Files MUST exist**: Verify file paths against the actual codebase
5. **Line count target**: 80-150 lines (too short = vague, too long = bloated)
6. **No snapshot metrics**: Don't write "50% reduction" — use absolute targets
7. **After generation**: Always run `validate-agent.py` before presenting to user

## Writer Validation Pipeline

```
@writer generates agent.md
    ↓
1. Parse YAML frontmatter
2. Validate against JSON Schema
3. Check required sections exist
4. Verify Key Files paths exist in codebase
5. Check keyword overlap with existing agents (< 50%)
6. Check line count (80-150)
    ↓
If all pass: ✅ Present to user
If errors:  ❌ Fix and re-validate
If warnings: ⚠️ Present with warnings
```

---

## Version History

- **v2.0** (2026-02-26): Added strict frontmatter schema, required sections checklist, validation pipeline, MCP server support
- **v1.0** (2026-01-21): Initial specialist agent template with efficiency guidelines
