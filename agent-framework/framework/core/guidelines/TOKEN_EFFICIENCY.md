# Token Efficiency Guidelines for Copilot Agents

**Version**: 1.0
**Last Updated**: 2026-01-21
**Purpose**: Minimize premium request tokens across all agents while maintaining effectiveness

## Overview

This document consolidates token efficiency optimizations across all agent types in the copilot-agents framework. Target token budgets based on invocation frequency:

| Agent Type | Daily Invocations | Target Tokens/Call | Daily Budget |
|------------|-------------------|-------------------|--------------|
| @coordinator (router) | 50-100 | 400-600 | 30,000 |
| @planner (plan creator) | 2-5 | 1500-2000 | 7,500 |
| @writer | 5-15 | <400 | 4,000 |
| @analyzer | 2-8 | <1000 | 6,000 |
| Specialist agents | 3-10 each | 300-500 | varies |

**Overall Target**: 65-85% reduction from current baseline (~125,000 → ~50,000 tokens/day)

---

## 1. Architecture: Planner/Coordinator Split

**Problem**: Single @coordinator agent loads 800-line plan schema on every routing query (50-100× daily)

**Solution**: Split into invocation-frequency-optimized agents

### @coordinator (Lightweight Router)
- **Size**: 200-300 lines
- **Frequency**: 50-100× daily
- **Responsibilities**:
  - Route incoming requests to appropriate agent
  - Execute existing plans from .copilot-agents/plans/*.json
  - Recognize "plan:" prefix → delegate to @planner
  - Share agent-discovery.md protocol with @planner
- **Token Budget**: 400-600 tokens/invocation
- **Exclusions**: No plan creation, no schema validation, no knowledge capture

### @planner (Plan Creator)
- **Size**: 800-1000 lines
- **Frequency**: 2-5× daily
- **Responsibilities**:
  - Create new plans with v1.1 schema
  - Validate plan structure and dependencies
  - Capture knowledge in plan JSON
  - Share agent-discovery.md protocol with @coordinator
- **Token Budget**: 1500-2000 tokens/invocation
- **Includes**: Full schema docs, examples, validation rules

### Shared Protocol: agent-discovery.md
Referenced by both agents to prevent 180-line duplication:

```markdown
## Agent Discovery Workflow

1. Check cache first: .copilot-agents/knowledge/stack-<name>-agents.json
   - If exists and fresh (<24 hours): Use cached capabilities (100 tokens)
   - If stale or missing: Proceed to step 2

2. Scan files with file_search:
   - Pattern: stacks/<stack>/agents/*.agent.md
   - Common agents: framework/core/common-agents/*.agent.md
   - Shared agents: framework/core/shared-agents/*.agent.md

3. Read partial files (lines 1-50 only):
   - Extract frontmatter: name, description, keywords
   - Don't read full 200-500 line agent files
   - Saves: 150 tokens per agent file

4. Build capability map:
   - Keywords → agent mappings
   - Specialty → agent mappings
   - Category → agent mappings

5. Cache results:
   - Write .copilot-agents/knowledge/stack-<name>-agents.json
   - Include timestamp for 24-hour TTL
```

**Token Impact**:
- Discovery with cache: ~100 tokens (capability map lookup)
- Discovery without cache: ~500 tokens (scan + partial reads)
- Discovery before optimization: ~1000 tokens (scan + full file reads)
- Daily savings with coordinator split: **77%** (125,000 → 30,400 tokens)

**Delegation Pattern**:
```markdown
User: "plan: optimize token usage across agents"
@coordinator: Recognizes "plan:" prefix → delegates to @planner
@planner: Creates 10-step plan, writes .copilot-agents/plans/<timestamp>_optimize-token-usage.json
@coordinator: Executes steps from plan file, delegates to specialists
```

---

## 2. @writer Efficiency Rules

**Current State**: 650-1150 tokens/invocation
**Target**: <400 tokens/invocation (67% reduction)

### Rule 2.1: Targeted File Reading

**Problem**: Reads entire files (400-500 tokens) when overview sufficient

**Solution**:
```markdown
# Before writing agents or editing files
1. Use grep_search for overview first (50-100 tokens)
2. Only use read_file if specific sections needed
3. Read smallest range sufficient (not entire file)

Example:
✓ grep_search(query="^name:|^description:", includePattern="agents/coordinator.agent.md")
✓ read_file("coordinator.agent.md", lines 1-50)  # frontmatter only
✗ read_file("coordinator.agent.md", lines 1-1302)  # entire file
```

**Savings**: 300 tokens per file

### Rule 2.2: Batch Parallel File Reads

**Problem**: Sequential tool calls add latency and overhead

**Solution**:
```markdown
# When reading multiple agent files
✓ Parallel: read_file("coordinator.agent.md", 1-50) + read_file("analyzer.agent.md", 1-50) + read_file("writer.agent.md", 1-50)
✗ Sequential: read coordinator → wait → read analyzer → wait → read writer

# When creating multiple files
✓ Use create_file in parallel for independent files
✗ Create one file, wait for response, create next file
```

**Savings**: 150 tokens per batch operation (reduced overhead)

### Rule 2.3: Reuse Patterns from Templates

**Problem**: Generating full agent examples inline (200-300 lines)

**Solution**:
```markdown
# Reference template instead of generating
✓ "Follow pattern in framework/templates/specialist-agent.template.md"
✗ Generate 200-300 line example inline

# For common patterns (stack structure, agent frontmatter, etc.)
✓ "See framework/templates/stack-structure.md for layout"
✗ Generate 150-line directory tree example
```

**Savings**: 150 tokens per generated agent, 100 tokens per structure example

### Rule 2.4: Condensed Workspace Path Documentation

**Problem**: Verbose path explanations (200 tokens)

**Current**:
```markdown
When creating files, be intentional and avoid calling the create_file tool unnecessarily.
Only create files that are essential to completing the user's request. When invoking
a tool that takes a file path, always use the absolute file path. If the file has a
scheme like untitled: or vscode-userdata:, then use a URI with the scheme. (200 tokens)
```

**Condensed**:
```markdown
File paths: Always absolute. For untitled:/vscode-userdata: use full URI. (15 tokens)
```

**Savings**: 185 tokens

### Rule 2.5: Code Generation Efficiency

**Problem**: Verbose command blocks and examples

**Solution**:
```markdown
# Compact command blocks
✓ bash
   cd stacks/ocpp20-rust && cargo build

✗ bash
   # First navigate to the stack directory
   cd stacks/ocpp20-rust
   # Now build the project
   cargo build
   # This will compile all dependencies

# Reference external docs instead of inline examples
✓ "See .copilot-agents/knowledge/testing-patterns.md"
✗ Generate 50-line pytest example inline
```

**Savings**: 100 tokens per command block, 200 tokens per external reference

### Rule 2.6: Context Management and Caching

**Problem**: Re-analyzing stack structure on every invocation

**Solution**:
```markdown
# Before analyzing stack patterns
1. Check .copilot-agents/knowledge/<stack>-patterns.md
2. If exists and fresh: Reference cached patterns
3. If missing: Analyze and cache results

# Write pattern cache after first analysis
create_file(".copilot-agents/knowledge/ocpp20-patterns.md", content="""
Stack: ocpp20-rust
Patterns:
- Agent naming: <domain>-expert.agent.md
- Test location: tests/ at monorepo root
- Build command: cargo build --workspace
Updated: 2026-01-21
""")
```

**Savings**: 250 tokens per repeat invocation

### Rule 2.7: Use multi_replace for Batch Edits

**Problem**: Sequential replace_string_in_file calls (overhead per call)

**Solution**:
```markdown
# For multiple edits in same or different files
✓ multi_replace_string_in_file([
    {file: "agent1.md", old: "v1.0", new: "v1.1"},
    {file: "agent2.md", old: "v1.0", new: "v1.1"}
  ])
✗ replace_string_in_file("agent1.md", "v1.0", "v1.1")
  replace_string_in_file("agent2.md", "v1.0", "v1.1")
```

**Savings**: 60% reduction in editing overhead

### Rule 2.8: Quiet Mode for Successful Operations

**Problem**: Verbose confirmations for simple operations

**Solution**:
```markdown
# After successful file creation
✓ "Created 3 agent files in stacks/meta-agents/agents/"
✗ "I've successfully created coordinator.agent.md with 287 lines including
   frontmatter section with name, description, keywords and main instructions..."

# After successful edit
✓ "Updated coordinator.agent.md"
✗ "I've updated the coordinator agent file to include the new routing logic
   which will now recognize the 'plan:' prefix and delegate..."
```

**Savings**: 100 tokens per operation confirmation

### @writer Efficiency Checklist

Before responding:
- [ ] Used grep_search overview before read_file?
- [ ] Batched parallel operations where possible?
- [ ] Referenced templates instead of generating examples?
- [ ] Used condensed format for paths/confirmations?
- [ ] Checked knowledge cache before re-analyzing?
- [ ] Used multi_replace for batch edits?
- [ ] Brief confirmation for successful operations?

**Projected Total Savings**: -67% (650-1150 → ~280 tokens/invocation)

---

## 3. @analyzer Efficiency Rules

**Current State**: 3300-4500 tokens/invocation
**Target**: <1000 tokens/invocation (79% reduction)

### Rule 3.1: Scoped Analysis

**Problem**: Semantic searches entire monorepo (1500-2000 tokens)

**Solution**:
```markdown
# Restrict analysis to target directory only
✓ semantic_search("agent definitions", max_results=10)  # workspace-scoped
  Then filter results to target: stacks/meta-agents/agents/
✗ semantic_search(entire monorepo without filtering)

# Use includePattern for grep_search
✓ grep_search(query="name:", includePattern="stacks/meta-agents/**", isRegexp=false)
✗ grep_search(query="name:", isRegexp=false)  # searches everything
```

**Savings**: 1500 tokens per analysis (avoid irrelevant matches)

### Rule 3.2: Pattern Recognition (grep vs semantic_search)

**Problem**: semantic_search overused when grep sufficient

**Decision Tree**:
```markdown
Need exact string/keyword match? → grep_search (100 tokens)
├─ YES: Use grep_search with includePattern
└─ NO: Structure unclear or need conceptual match? → semantic_search (500 tokens)
    ├─ YES: Use semantic_search
    └─ NO: Use file_search for filename patterns (50 tokens)

Examples:
✓ Find all "coordinator" mentions: grep_search(query="coordinator", isRegexp=false)
✓ Find agent files by name: file_search(query="**/*-expert.agent.md")
✓ Find "delegation pattern": semantic_search("how agents delegate to specialists")
```

**Savings**: 400 tokens when grep sufficient (70% of cases)

### Rule 3.3: Leverage Existing Knowledge Files

**Problem**: Re-analyzing stack structure on repeat invocations

**Solution**:
```markdown
# Before analyzing stack
1. Check .copilot-agents/knowledge/<stack>-analysis.md
2. If exists and fresh (<7 days): Reference cached analysis
3. If stale or request "fresh analysis": Re-analyze and update cache

# Cache structure
.copilot-agents/knowledge/
├── ocpp20-analysis.md (stack type, agent list, build commands, test patterns)
├── meta-agents-analysis.md
└── systemtests-analysis.md

# Cache content example
Stack: ocpp20-rust
Type: Rust OCPP 2.0.1 implementation
Agents: @rust-expert, @ocpp-protocol, @testing-expert
Build: cargo build --workspace
Test: cargo test --workspace
Updated: 2026-01-21
```

**Savings**: 2000 tokens for repeat analysis requests

### Rule 3.4: Condensed Output Format

**Problem**: Detailed 7-field analysis when summary sufficient

**Current** (400 tokens):
```markdown
## Analysis Results

**Stack Type**: Rust OCPP 2.0.1 implementation
**Primary Language**: Rust
**Agents Discovered**: @rust-expert, @ocpp-protocol, @testing-expert
**Build System**: Cargo workspace
**Test Framework**: Rust built-in testing + custom OCPP test harness
**Key Patterns**:
- Agent naming follows <domain>-expert.agent.md
- Tests located at monorepo root tests/ directory
- ...
```

**Condensed** (80 tokens):
```markdown
Stack: ocpp20-rust (Rust OCPP 2.0.1)
Agents: @rust-expert, @ocpp-protocol, @testing-expert
Build: cargo build --workspace
Test: cargo test --workspace
Pattern: <domain>-expert.agent.md naming

Use `@analyzer --detailed` for full analysis.
```

**Savings**: 320 tokens per analysis response

### Rule 3.5: External Stack Pattern Library

**Problem**: Hardcoded examples for stack types (300 tokens per agent definition)

**Current**:
```markdown
# Inline in @analyzer agent (300 tokens)
Rust stacks typically follow:
- Cargo.toml workspace at root
- Multiple crates in workspace.members
- Tests in tests/ directory
- Agent naming: <domain>-expert.agent.md
...
```

**External**:
```markdown
# In .copilot-agents/knowledge/stack-patterns.md (referenced by @analyzer)
## Rust Stacks
- Workspace: Cargo.toml with [workspace]
- Build: cargo build --workspace
- Test: cargo test --workspace
- Agents: <domain>-expert.agent.md

## Python Stacks
- Dependencies: pyproject.toml or requirements.txt
- Build: pip install -e .
- Test: pytest tests/
- Agents: <tool>-expert.agent.md
```

**In @analyzer agent** (50 tokens):
```markdown
For stack type patterns, see .copilot-agents/knowledge/stack-patterns.md
```

**Savings**: 250 tokens per agent load (referenced instead of embedded)

### Rule 3.6: Batch Parallel Analysis Operations

**Problem**: Sequential file reads during analysis

**Solution**:
```markdown
# When analyzing multiple agents
✓ Parallel: read_file(agent1, 1-50) + read_file(agent2, 1-50) + read_file(agent3, 1-50)
✗ Sequential: read agent1 → wait → read agent2 → wait → read agent3

# When analyzing stack structure
✓ Parallel: list_dir("stacks/ocpp20-rust") + file_search("**/Cargo.toml") + grep_search("workspace")
✗ Sequential: list → wait → search files → wait → grep
```

**Savings**: 150 tokens per batch operation

### Rule 3.7: Sample Files Instead of Exhaustive Analysis

**Problem**: Reading 100+ files when 3-5 representative files sufficient

**Solution**:
```markdown
# Statistical sampling approach
✓ Read 3-5 representative agent files to infer patterns
✗ Read all 47 agent files in framework/

# Example: Analyzing specialist agent patterns
1. file_search("**/*-expert.agent.md") → 15 results
2. Sample 3 files: pytest-expert, rust-expert, gitlab-expert
3. Infer pattern from samples
4. Note: "Pattern inferred from 3/15 agents. Use --exhaustive for full scan."

# When to use exhaustive
- User explicitly requests "analyze ALL agents"
- Validating consistency across files
- Generating comprehensive inventory
```

**Savings**: 1000 tokens (3 files @ 200 tokens vs 15 files @ 200 tokens)

### @analyzer Efficiency Checklist

Before responding:
- [ ] Analysis scoped to target directory (not entire monorepo)?
- [ ] Used grep_search for exact matches instead of semantic_search?
- [ ] Checked knowledge cache before re-analyzing?
- [ ] Used condensed output format (summary-first)?
- [ ] Referenced external stack-patterns.md instead of inline examples?
- [ ] Batched parallel operations?
- [ ] Used statistical sampling (3-5 files) instead of exhaustive?

**Projected Total Savings**: -79% (3300-4500 → ~850 tokens/invocation)

---

## 4. Specialist Agent Efficiency Rules

**Current State**: Varies by agent (500-1500 tokens/invocation)
**Target**: 300-500 tokens/invocation (50-60% reduction)

### Rule 4.1: Single Responsibility Execution

**Problem**: Trying to handle out-of-scope tasks (200 tokens wasted)

**Solution**:
```markdown
# Quick delegation for out-of-scope tasks
✓ "@pytest-expert can only help with Python testing. For Rust testing, invoke @rust-expert."
✗ Attempt to research Rust testing patterns, load Rust docs, then realize out of scope

# Boundaries from agent definition
@pytest-expert:
- ✅ Write pytest test cases, fixtures, parametrization
- ⚠️ Ask before: Test architecture decisions (might need @analyzer)
- ❌ Never: Rust testing, JavaScript testing, deployment

# In specialist agent definition (10 tokens)
Out of scope? Delegate immediately. Don't research adjacent domains.
```

**Savings**: 200 tokens per out-of-scope request

### Rule 4.2: Minimal Cross-Referencing

**Problem**: Loading adjacent agent context unnecessarily

**Solution**:
```markdown
# Cache shared knowledge instead of cross-referencing
✓ Reference .copilot-agents/knowledge/ocpp-protocol.md (shared by @ocpp-protocol agent)
✗ "Let me read @ocpp-protocol agent definition to understand protocol details..."

# When to cross-reference
- User explicitly mentions another agent
- Task requires coordination (e.g., @coordinator delegating)
- Shared protocol needs synchronization

# When NOT to cross-reference
- General domain knowledge (use cached knowledge files)
- Examples/patterns (use templates)
- Out-of-scope tasks (delegate instead)
```

**Savings**: 300 tokens per avoided cross-reference

### Rule 4.3: Knowledge Reuse from Plan Context

**Problem**: Re-discovering information from earlier plan steps

**Solution**:
```markdown
# In plan Step 5, reuse knowledge from Steps 1-2
✓ "From Step 1 analysis: @coordinator has 1302 lines, loads schema on every invocation"
✗ Re-read @coordinator agent file, re-analyze token usage

# Plan context includes
{
  "knowledge": {
    "decisions": ["Key decisions from this step"],
    "learnings": ["Insights discovered"],
    "references": ["Files analyzed"]
  }
}

# In specialist agent instructions (20 tokens)
If executing plan step, check step.knowledge.references first before re-reading files.
```

**Savings**: 170 tokens per plan step (avoid re-reading referenced files)

### Rule 4.4: Compact Agent Definitions

**Problem**: Verbose agent files (200-500 lines) with inline examples

**Target**: 80-120 lines with external references

**Template Structure**:
```markdown
---
name: pytest-expert
description: Python testing specialist using pytest framework
keywords: [pytest, testing, python, fixtures, parametrization]
---

## Role
Python testing specialist. Write pytest test cases, fixtures, and parametrized tests.

## Boundaries
✅ pytest test cases, fixtures, mocking, parametrization
⚠️ Test architecture (coordinate with @analyzer)
❌ Other languages, deployment, CI/CD

## Efficiency Rules
{reference: framework/core/guidelines/TOKEN_EFFICIENCY.md#4-specialist-agent-efficiency-rules}

## Common Patterns
{reference: .copilot-agents/knowledge/testing-patterns.md}

## Examples
{reference: framework/templates/pytest-examples.md}

(Total: 80-100 lines vs 200-500 lines)
```

**Savings**: 150 tokens per specialist agent file load

### Rule 4.5: Efficient File Operations

**Problem**: Specialists duplicate @writer inefficiencies

**Solution**:
```markdown
# Follow @writer rules when reading/editing files
✓ grep_search overview before read_file
✓ Batch parallel reads
✓ multi_replace for batch edits
✓ Condensed confirmations

# Embedded in specialist agents (30 tokens)
File operations: Follow @writer efficiency rules (grep before read, batch parallels, multi_replace, brief confirmations).
```

**Savings**: Follow @writer savings (300 tokens per file operation)

### Rule 4.6: Condensed Responses for Success

**Problem**: Verbose success confirmations

**Solution**:
```markdown
# After implementing test
✓ "Created test_charging_session.py with 3 test cases"
✗ "I've successfully created test_charging_session.py which includes three comprehensive
   test cases: test_start_charging validates charging session initialization,
   test_stop_charging ensures proper session termination, and test_charging_metrics
   verifies meter value reporting. Each test uses fixtures from conftest.py..."

# After code review
✓ "Found 2 issues: missing error handling in authenticate(), inefficient loop in validate_message()"
✗ "I've completed a thorough review of the code and identified several areas for improvement.
   First, the authenticate() method doesn't handle connection timeouts which could cause..."
```

**Savings**: 100 tokens per operation confirmation

### Rule 4.7: Smart Context Loading

**Problem**: Loading full context for simple tasks

**Solution**:
```markdown
# Assess complexity before loading context
Simple task (function signature, single file): grep_search + partial read (100 tokens)
├─ "Add type hints to authenticate()"
└─ grep_search("def authenticate") → read_file(lines N-N+20)

Medium task (multi-file, 2-3 functions): targeted reads (300 tokens)
├─ "Refactor charging session state machine"
└─ Read 3 specific files based on grep_search results

Complex task (architecture, 5+ files): analyzer first (500 tokens)
├─ "Redesign message routing"
└─ Invoke @analyzer for architecture → then targeted implementation
```

**Savings**: 400 tokens for simple tasks (avoid unnecessary context)

### Rule 4.8: Reuse Templates and Boilerplate

**Problem**: Generating common patterns from scratch

**Solution**:
```markdown
# Reference framework templates
✓ "Follow framework/templates/pytest-test-structure.md"
✗ Generate 50-line pytest test example inline

# Common templates
framework/templates/
├── pytest-test-structure.md (pytest test layout)
├── rust-module-structure.md (Rust module pattern)
├── agent-frontmatter.md (agent metadata format)
└── knowledge-file-format.md (knowledge cache structure)

# In specialist agent (15 tokens)
Common patterns: See framework/templates/<domain>-*.md
```

**Savings**: 170 tokens per generated pattern

### Specialist Agent Efficiency Checklist

Before responding:
- [ ] Task in scope? If not, delegate immediately
- [ ] Checked knowledge cache before cross-referencing?
- [ ] Reused plan context instead of re-reading files?
- [ ] Agent definition compact (80-120 lines with references)?
- [ ] Followed @writer file operation rules?
- [ ] Condensed confirmation for successful operations?
- [ ] Assessed task complexity before loading context?
- [ ] Referenced templates instead of generating boilerplate?

**Projected Total Savings**: 50-60% reduction in specialist agent token usage

### Propagation Strategy

**Step 6-7**: Embed efficiency instructions in all specialist agents

Method 1: Template reference (10 tokens per agent):
```markdown
## Efficiency Guidelines
{reference: framework/core/guidelines/TOKEN_EFFICIENCY.md#4-specialist-agent-efficiency-rules}
```

Method 2: Condensed inline (60 tokens per agent):
```markdown
## Efficiency Rules
- Out of scope? Delegate immediately (don't research adjacent domains)
- Check knowledge cache before cross-referencing agents
- Reuse plan context (don't re-read files from earlier steps)
- Follow @writer file rules (grep before read, batch ops, condensed confirmations)
- Simple tasks: partial reads only (100 tokens)
- Complex tasks: invoke @analyzer first (500 tokens)
- Reference framework/templates/ instead of generating boilerplate
```

**Recommendation**: Use Method 1 (template reference) for 50-token savings per agent × 20-30 agents = 1000-1500 tokens saved per specialist agent load.

---

## 5. Anti-Patterns

### Anti-Pattern 1: Loading Full Agent Files
```markdown
❌ read_file("coordinator.agent.md", lines 1-1302)  # 2300 tokens
✓ grep_search(query="name:|description:", includePattern="coordinator.agent.md")  # 50 tokens
✓ read_file("coordinator.agent.md", lines 1-50)  # 200 tokens (frontmatter only)
```

### Anti-Pattern 2: Sequential Tool Calls
```markdown
❌ read_file(agent1) → wait → read_file(agent2) → wait → read_file(agent3)
✓ read_file(agent1) + read_file(agent2) + read_file(agent3) in parallel
```

### Anti-Pattern 3: Verbose Confirmations
```markdown
❌ "I've successfully created coordinator.agent.md with 287 lines including frontmatter
   section with name, description, keywords and main instructions for routing logic..."
✓ "Created coordinator.agent.md (287 lines)"
```

### Anti-Pattern 4: Re-analyzing Cached Knowledge
```markdown
❌ User: "What agents exist in ocpp20-rust stack?"
   Agent: semantic_search + read 15 agent files → 2000 tokens
✓ User: "What agents exist in ocpp20-rust stack?"
   Agent: read .copilot-agents/knowledge/ocpp20-analysis.md → 150 tokens
```

### Anti-Pattern 5: semantic_search for Exact Matches
```markdown
❌ semantic_search("coordinator agent") → 500 tokens
✓ grep_search(query="coordinator", includePattern="**/*.agent.md", isRegexp=false) → 100 tokens
```

### Anti-Pattern 6: Generating Examples Inline
```markdown
❌ Generate 200-line pytest test example in agent definition → 350 tokens
✓ "See framework/templates/pytest-examples.md" → 15 tokens
```

### Anti-Pattern 7: Out-of-Scope Task Handling
```markdown
❌ @pytest-expert: "Let me research Rust testing... cargo test... #[test] attribute..." → 500 tokens
✓ @pytest-expert: "@rust-expert handles Rust testing. Delegating." → 20 tokens
```

### Anti-Pattern 8: Exhaustive File Analysis
```markdown
❌ Read all 47 agent files to analyze patterns → 9400 tokens
✓ Sample 3-5 representative agents, infer patterns → 1000 tokens
```

---

## 6. Implementation Checklist

### Phase 1: Architecture (Steps 3-5)
- [ ] Create @planner agent (800-1000 lines with full schema)
- [ ] Refactor @coordinator to router (200-300 lines, reference agent-discovery.md)
- [ ] Update @writer with efficiency rules 2.1-2.8
- [ ] Update @analyzer with efficiency rules 3.1-3.7

### Phase 2: Templates (Step 6)
- [ ] Create framework/templates/agent-efficiency-instructions.template.md
- [ ] Create framework/templates/specialist-agent.template.md (compact 80-120 lines)
- [ ] Create framework/templates/knowledge-cache-format.md

### Phase 3: Propagation (Steps 7-8)
- [ ] Update all specialist agents in framework/core/shared-agents/ with efficiency rules
- [ ] Update all specialist agents in framework/core/common-agents/ with efficiency rules
- [ ] Update all specialist agents in stacks/*/agents/ with efficiency rules
- [ ] Use template reference method: {reference: framework/core/guidelines/TOKEN_EFFICIENCY.md#4}

### Phase 4: Validation (Steps 9-10)
- [ ] Test @planner creates plans with v1.1 schema
- [ ] Test @coordinator delegates "plan:" requests to @planner
- [ ] Verify agent discovery cache works (24-hour TTL)
- [ ] Verify @writer uses grep before read, batches operations
- [ ] Verify @analyzer uses condensed output, scoped searches
- [ ] Measure actual token usage vs targets
- [ ] Document results and iterate

---

## 7. Measurement and Monitoring

### Token Budget Tracking

Create .copilot-agents/knowledge/token-usage-log.md:

```markdown
# Token Usage Log

## 2026-01-21 (Baseline - Before Optimization)
- @coordinator: 2300-2900 tokens/call × 75 calls = 172,500 tokens
- @writer: 650-1150 tokens/call × 10 calls = 9,000 tokens
- @analyzer: 3300-4500 tokens/call × 5 calls = 19,000 tokens
- Specialists: 500-1500 tokens/call × 15 calls = 15,000 tokens
**Daily Total**: ~215,500 tokens

## 2026-01-22 (After Phase 1 - Architecture)
- @coordinator (router): 400-600 tokens/call × 75 calls = 37,500 tokens
- @planner: 1500-2000 tokens/call × 3 calls = 5,250 tokens
- @writer: 280-400 tokens/call × 10 calls = 3,400 tokens
- @analyzer: 850-1000 tokens/call × 5 calls = 4,625 tokens
- Specialists: (unchanged) 15,000 tokens
**Daily Total**: ~65,775 tokens (-69%)

## 2026-01-23 (After Phase 3 - Specialist Propagation)
- @coordinator (router): 37,500 tokens
- @planner: 5,250 tokens
- @writer: 3,400 tokens
- @analyzer: 4,625 tokens
- Specialists: 300-500 tokens/call × 15 calls = 6,000 tokens
**Daily Total**: ~56,775 tokens (-74%)
```

### Success Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| @coordinator tokens/call | 2300-2900 | 400-600 | Compare before/after split |
| @planner tokens/call | N/A | 1500-2000 | New agent |
| @writer tokens/call | 650-1150 | <400 | grep usage, batch ops |
| @analyzer tokens/call | 3300-4500 | <1000 | Condensed output |
| Specialist tokens/call | 500-1500 | 300-500 | Template references |
| Daily token total | ~215,000 | <60,000 | Sum all agent calls |
| Cache hit rate | 0% | >70% | knowledge/*.json usage |

---

## 8. Quick Reference Card

**For @coordinator**:
- Route only, don't create plans (delegate to @planner)
- Use agent-discovery.md protocol (cache-first)
- Target: 400-600 tokens/call

**For @planner**:
- Create plans with v1.1 schema
- Use agent-discovery.md protocol (cache-first)
- Target: 1500-2000 tokens/call

**For @writer**:
- grep_search before read_file (save 300 tokens)
- Batch parallel operations (save 150 tokens)
- Reference templates (save 150 tokens)
- Condensed confirmations (save 100 tokens)
- Target: <400 tokens/call

**For @analyzer**:
- Scope to target directory (save 1500 tokens)
- grep for exact matches (save 400 tokens)
- Check knowledge cache (save 2000 tokens for repeats)
- Condensed output (save 320 tokens)
- Sample 3-5 files (save 1000 tokens)
- Target: <1000 tokens/call

**For Specialists**:
- Delegate out-of-scope immediately (save 200 tokens)
- Reference external knowledge (save 300 tokens)
- Compact definitions 80-120 lines (save 150 tokens)
- Follow @writer file rules (save 300 tokens)
- Condensed confirmations (save 100 tokens)
- Target: 300-500 tokens/call

---

## 9. Versioning and Updates

**Current Version**: 1.0 (2026-01-21)

**Update Protocol**:
1. Measure actual token usage after implementation
2. Identify additional inefficiencies
3. Update this document with new rules
4. Propagate changes to affected agents
5. Re-measure and validate improvements

**Change Log**:
- 2026-01-21 v1.0: Initial token efficiency guidelines
  - Planner/coordinator split architecture
  - 8 writer rules, 7 analyzer rules, 8 specialist rules
  - Anti-patterns and implementation checklist
  - Target: 65-85% reduction from baseline

**Next Review**: After Phase 4 validation (Step 10)

---

## 10. References

- Plan: .copilot-agents/plans/2026-01-21_00-00-00_optimize-token-usage-across-agents.json
- Analysis: .copilot-agents/knowledge/token-usage-analysis.md
- Architecture: .copilot-agents/knowledge/planner-coordinator-architecture.md
- Agent Discovery: .copilot-agents/knowledge/agent-discovery.md
- Writer Rules: .copilot-agents/knowledge/writer-efficiency-rules.md
- Analyzer Rules: .copilot-agents/knowledge/analyzer-efficiency-rules.md
- Specialist Rules: .copilot-agents/knowledge/specialist-efficiency-rules.md

---

**End of Token Efficiency Guidelines v1.0**
