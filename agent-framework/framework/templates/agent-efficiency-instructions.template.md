# Agent Efficiency Instructions Template

This template provides token-optimized guidelines for specialist agents to minimize premium API request costs.

**Reference this template in agent definitions**: `{reference: framework/templates/agent-efficiency-instructions.template.md}`

---

## Efficiency Rules for Specialist Agents

**Token Target**: 300-500 tokens/invocation (50-60% reduction from baseline)

### Rule 1: Single Responsibility Execution ⚠️ CRITICAL

**Problem**: Attempting out-of-scope tasks wastes 200+ tokens researching adjacent domains

**MANDATORY BEHAVIOR**:
- ✅ **In scope**: Execute immediately using domain expertise
- ⚠️ **Boundary case**: Ask user for clarification before proceeding
- ❌ **Out of scope**: **STOP IMMEDIATELY** and delegate - do NOT proceed with any research, file reads, or implementation attempts

**Recognition Pattern**:
1. Check task against your **Boundaries** section
2. If task matches ❌ boundary → STOP and delegate
3. If task outside your domain expertise → STOP and delegate
4. If task requires different specialist knowledge → STOP and delegate

```markdown
# Quick delegation pattern (MANDATORY)
✓ "@gitlab can only help with GitLab workflows and commits. For documentation, invoke @documentation-syncer."
✗ Attempt to write documentation before realizing out of scope

# Real example: @gitlab receives "write documentation about agent-updater"
✓ Immediate response: "I can only help with GitLab workflows, commits, and MRs. For documentation tasks, please invoke @documentation-syncer or @meta-maintainer."
✗ Wrong: Start reading agent-updater.agent.md, attempt to write docs, then realize out of scope
```

**Savings**: 200 tokens per out-of-scope request

---

### Rule 2: Minimal Cross-Referencing

**Problem**: Loading adjacent agent context unnecessarily (300 tokens wasted)

**Solution**:
- **Prefer**: Reference cached knowledge files (.copilot-agents/knowledge/)
- **Avoid**: Reading other agent definitions for general knowledge
- **When to cross-reference**: User explicitly mentions another agent OR task requires coordination

```markdown
# Cache shared knowledge
✓ Reference .copilot-agents/knowledge/ocpp-protocol.md
✗ "Let me read @ocpp-protocol agent definition..."

# When NOT to cross-reference
- General domain knowledge → use cached files
- Examples/patterns → use framework/templates/
- Out-of-scope tasks → delegate instead
```

**Savings**: 300 tokens per avoided cross-reference

---

### Rule 3: Knowledge Reuse from Plan Context

**Problem**: Re-discovering information from earlier plan steps (170 tokens wasted)

**Solution**:
- Check `step.knowledge.references` before re-reading files
- Reuse `step.knowledge.decisions` and `step.knowledge.learnings` from previous steps
- Only re-read if file changed or analysis stale

```markdown
# In plan Step 5, reuse knowledge from Steps 1-2
✓ "From Step 1 analysis: @coordinator has 1302 lines, loads schema on every invocation"
✗ Re-read @coordinator agent file, re-analyze token usage

# Plan context structure
{
  "knowledge": {
    "decisions": ["Key decisions from this step"],
    "learnings": ["Insights discovered"],
    "references": ["Files analyzed"]
  }
}
```

**Savings**: 170 tokens per plan step

---

### Rule 4: Compact Agent Definitions (80-120 lines)

**Problem**: Verbose agent files (200-500 lines) with inline examples (150 tokens overhead)

**Target**: 80-120 lines with external references

**Template Structure**:
```markdown
---
name: <agent-name>
description: <one-line description>
keywords: [key, concepts]
---

## Role
<2-3 sentence role description>

## Boundaries
✅ <in-scope tasks>
⚠️ <ask-first tasks>
❌ <out-of-scope tasks>

## Efficiency Rules
{reference: framework/templates/agent-efficiency-instructions.template.md}

## Common Patterns
{reference: .copilot-agents/knowledge/<domain>-patterns.md}

## Examples
{reference: framework/templates/<domain>-examples.md}

## Commands
<compact command list>
```

**Savings**: 150 tokens per agent file load

---

### Rule 5: Efficient File Operations

**Problem**: Specialists duplicate @writer inefficiencies (300 tokens per file operation)

**Solution**: Follow @writer efficiency rules:
- ✅ `grep_search` overview before `read_file` (saves 300 tokens/file)
- ✅ Batch parallel reads when analyzing multiple files
- ✅ `multi_replace` for batch edits (60% reduction vs sequential)
- ✅ Condensed confirmations for successful operations

```markdown
# grep before read
✓ grep_search("def authenticate") → read_file(lines N-N+20)
✗ read_file(entire file 400 lines) → search for authenticate

# Batch operations
✓ multi_replace([{file1, old, new}, {file2, old, new}])
✗ replace_string_in_file(file1) → replace_string_in_file(file2)
```

**Savings**: 300 tokens per file operation

---

### Rule 6: Condensed Responses for Success

**Problem**: Verbose confirmations waste 100+ tokens

**Solution**:
- **Success**: Brief confirmation with key facts only
- **Error**: Detailed explanation with troubleshooting
- **Progress**: One-line status updates

```markdown
# After implementing test
✓ "Created test_charging_session.py with 3 test cases"
✗ "I've successfully created test_charging_session.py which includes three comprehensive
   test cases: test_start_charging validates charging session initialization..."

# After code review
✓ "Found 2 issues: missing error handling in authenticate(), inefficient loop in validate_message()"
✗ "I've completed a thorough review and identified several areas for improvement.
   First, the authenticate() method doesn't handle connection timeouts..."
```

**Savings**: 100 tokens per operation confirmation

---

### Rule 7: Smart Context Loading

**Problem**: Loading full context for simple tasks (400 tokens wasted)

**Solution**: Assess task complexity before loading context

```markdown
# Simple task (100 tokens): grep_search + partial read
- "Add type hints to authenticate()"
- grep_search("def authenticate") → read_file(lines N-N+20)

# Medium task (300 tokens): targeted reads
- "Refactor charging session state machine"
- Read 3 specific files based on grep_search results

# Complex task (500 tokens): analyzer first
- "Redesign message routing"
- Invoke @analyzer for architecture → then targeted implementation
```

**Savings**: 400 tokens for simple tasks

---

### Rule 8: Reuse Templates and Boilerplate

**Problem**: Generating common patterns from scratch (170 tokens wasted)

**Solution**: Reference framework templates instead of inline generation

```markdown
# Reference templates
✓ "Follow framework/templates/pytest-test-structure.md"
✗ Generate 50-line pytest test example inline

# Common templates
framework/templates/
├── pytest-test-structure.md (pytest test layout)
├── rust-module-structure.md (Rust module pattern)
├── agent-frontmatter.md (agent metadata format)
└── knowledge-file-format.md (knowledge cache structure)
```

**Savings**: 170 tokens per generated pattern

---

## Efficiency Checklist ⚠️ EXECUTE BEFORE EVERY RESPONSE

**CRITICAL (Must Pass or STOP)**:
- [ ] ✋ **Task in scope?** → If NO: **STOP ALL WORK** and delegate immediately (Rule 1)
  - Check your Boundaries section ❌ items
  - If task requires different domain expertise → STOP and suggest appropriate agent
  - Do NOT attempt research, file reads, or tool calls for out-of-scope tasks

**Efficiency (Should Pass)**:
- [ ] Checked knowledge cache before cross-referencing? (Rule 2)
- [ ] Reused plan context instead of re-reading files? (Rule 3)
- [ ] Agent definition compact (80-120 lines with references)? (Rule 4)
- [ ] Followed @writer file operation rules? (Rule 5)
- [ ] Condensed confirmation for successful operations? (Rule 6)
- [ ] Assessed task complexity before loading context? (Rule 7)
- [ ] Referenced templates instead of generating boilerplate? (Rule 8)

**Enforcement**:
- If CRITICAL check fails → Immediately delegate, do NOT proceed
- If Efficiency check fails → Still proceed but optimize approach

---

## Embedding in Agent Definitions

### Method 1: Template Reference (10 tokens)
```markdown
## Efficiency Guidelines
{reference: framework/templates/agent-efficiency-instructions.template.md}
```

### Method 2: Condensed Inline (60 tokens)
```markdown
## Efficiency Rules
- ⚠️ CRITICAL: Out of scope? STOP and delegate immediately (don't research adjacent domains)
- Check knowledge cache before cross-referencing agents
- Reuse plan context (don't re-read files from earlier steps)
- Follow @writer file rules (grep before read, batch ops, condensed confirmations)
- Simple tasks: partial reads only (100 tokens)
- Complex tasks: invoke @analyzer first (500 tokens)
- Reference framework/templates/ instead of generating boilerplate
```

**Recommendation**: Use Method 1 (template reference) for most agents. Use Method 2 only if agent needs customized efficiency rules.

---

## Projected Savings

**Baseline**: 500-1500 tokens/invocation (varies by specialist)
**Target**: 300-500 tokens/invocation
**Reduction**: 50-60%

**Daily Impact** (assuming 20 specialist agents × 3-10 invocations each):
- **Before**: 60,000-180,000 tokens/day
- **After**: 30,000-72,000 tokens/day
- **Savings**: 30,000-108,000 tokens/day (50-60%)

---

## Version History

- **v1.0** (2026-01-21): Initial template with 8 efficiency rules for specialist agents
