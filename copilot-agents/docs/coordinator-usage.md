# Coordinator Usage Guide

This guide demonstrates how to use the `@coordinator` agent for implementation planning, progress tracking, and multi-agent workflow orchestration.

## Overview

The coordinator agent operates in two modes:

1. **Routing Mode** (default): Routes questions to appropriate stack agents
2. **Planning Mode** (triggered by `plan:` keyword): Generates structured implementation plans with agent delegation

## Planning Mode Features

- ✅ Dynamic agent capability discovery
- ✅ Pre-flight validation (agent existence, task-agent match, dependencies)
- ✅ Structured JSON plans with progress tracking
- ✅ One active plan per stack enforcement
- ✅ Cross-stack plan coordination
- ✅ Manual archival (never auto-archives)

## Basic Workflow

### 1. Create a Plan

Ask the coordinator to create an implementation plan:

```
@coordinator plan: Add OCPP 2.0.1 StartTransaction test
```

**What happens:**
1. Coordinator discovers agents in `systemtests-python` stack
2. Validates agent assignments against capabilities
3. Generates plan JSON with numbered steps
4. Saves to `.copilot-agents/plans/2026-01-19_14-30-00_add-ocpp-starttransaction-test.json`
5. Presents plan with validation report

**Example output:**

```
✅ Pre-flight Validation Passed
  - All 5 agents exist in systemtests-python stack
  - Task-agent assignments validated
  - No circular dependencies detected

📋 Implementation Plan: Add OCPP 2.0.1 StartTransaction test

Plan ID: 2026-01-19_14-30-00_add-ocpp-starttransaction-test
Stack: systemtests-python
Status: active

Steps:
1. @etf-library - Review OCPP 2.0.1 StartTransaction message structure
2. @pytest-async-systemtest - Create test file with fixtures
3. @etf-workbench-integration - Implement TestSuite class with requisition
4. @ocpp-protocol - Validate test assertions match spec
5. @gitlab - Commit and create MR

Next: Execute Step 1 - @etf-library
```

### 2. Execute Steps

Work through the plan step-by-step, delegating to assigned agents:

```
@etf-library Review OCPP 2.0.1 StartTransaction message structure and CSMS client methods
```

### 3. Report Progress

After completing a step, update the coordinator:

```
@coordinator step 1 completed
```

**Coordinator response:**

```
✅ Step 1 completed: Review OCPP 2.0.1 StartTransaction message structure

Progress: 20% (1/5 steps completed)

Next: Step 2 - Create test file with fixtures (@pytest-async-systemtest)
```

### 4. Handle Blockers

If a step is blocked:

```
@coordinator step 3 blocked: waiting for ETF server v2.0 deployment
```

**Coordinator response:**

```
🚫 Step 3 blocked: waiting for ETF server v2.0 deployment

Progress: 40% (2/5 steps completed, 1 blocked)

Next executable step: Step 4 - Validate test assertions (@ocpp-protocol)
```

### 5. Resume After Interruption

To see the current plan state:

```
@coordinator show-plan
```

**Coordinator response:**

```
📊 Active Plan: Add OCPP 2.0.1 StartTransaction test

Plan ID: 2026-01-19_14-30-00_add-ocpp-starttransaction-test
Created: 2026-01-19 14:30:00
Updated: 2026-01-19 16:45:00

Progress: 60% (3/5 steps completed)

Steps:
✅ 1. @etf-library - Review message structure [completed]
✅ 2. @pytest-async-systemtest - Create test file [completed]
✅ 3. @etf-workbench-integration - Implement TestSuite [completed]
⏳ 4. @ocpp-protocol - Validate assertions [pending]
⏳ 5. @gitlab - Commit and create MR [pending, depends on 4]

Next: Step 4 - Validate assertions (@ocpp-protocol)
```

### 6. Archive Completed Plan

When all steps are done:

```
@coordinator archive-plan
```

**Coordinator response:**

```
✅ Plan archived: 2026-01-19_14-30-00_add-ocpp-starttransaction-test

All 5 steps completed successfully.

You can now create a new plan.
```

## Hierarchical Planning (v2.0)

### Overview

Schema v2.0 provides hierarchical plans with automatic knowledge capture, parallel execution groups, and autonomous API-driven execution. Key features:

- **Hierarchical steps**: Break complex steps into sub-tasks (max 2 levels)
- **Parallel execution groups**: Steps in the same group run concurrently
- **Priority-based scheduling**: critical/high/normal/low with human approval gates
- **Automatic knowledge extraction**: Decisions, learnings, blockers captured from agent responses
- **Context-aware progress**: Navigate between main/sub-plan contexts
- **Artifact verification**: Auto-check file existence
- **Token budgeting**: Estimated token usage per step with budget tracking
- **Context resolution**: Steps declare needed context (file, knowledge, plan_output, mcp_query)
- **Schema migration**: v1.0 → v1.1 → v2.0 plans auto-upgrade

### Example 1: Creating Hierarchical Plan with Sub-Steps

**Scenario:** Test implementation task is too complex for a single atomic step.

```
@coordinator plan: Add OCPP StartTransaction test with error handling
```

**Initial plan** (all top-level):

```
Steps:
1. @ocpp-protocol - Review StartTransaction spec
2. @etf-library - Check library support
3. @pytest-async-systemtest - Create comprehensive test suite  ← TOO COMPLEX
4. @pytest-async-systemtest - Run tests and verify coverage
5. @gitlab - Commit and create MR
```

**Decompose step 3:**

```
@coordinator expand-step 3
```

**Coordinator prompts:**
```
Step 3 "Create comprehensive test suite" appears complex. 
Decompose into atomic sub-tasks:

Suggested breakdown:
3.1 Create test file structure and imports
3.2 Implement pytest fixtures for OCPP session
3.3 Write test cases for success scenarios
3.4 Write test cases for error scenarios

Proceed with this breakdown? (Or provide your own)
```

**User:** `yes`

**Coordinator response:**
```
✅ Step 3 expanded into 4 sub-steps
📍 Active context: step_3

Sub-plan for Step 3:
3.1 @pytest-async-systemtest - Create test file structure and imports [pending]
3.2 @pytest-async-systemtest - Implement pytest fixtures [pending, depends on 3.1]
3.3 @pytest-async-systemtest - Write success test cases [pending, depends on 3.2]
3.4 @pytest-async-systemtest - Write error test cases [pending, depends on 3.2]

Progress: 📍 Step 3: 0% (0/4 sub-steps completed)

Next: Execute 3.1 - Create test file structure
```

**Working in sub-plan context:**

```
@coordinator show-plan
```

```
📍 Step 3 Context: Create comprehensive test suite
Progress: 25% (1/4 sub-steps completed)

✅ 3.1 - Create test file structure [completed]
🔄 3.2 - Implement pytest fixtures [in-progress]
⏳ 3.3 - Write success test cases [pending, depends on 3.2]
⏳ 3.4 - Write error test cases [pending, depends on 3.2]
```

**Return to main level:**

```
@coordinator focus-main
```

```
📍 Main Plan: Add OCPP StartTransaction test
Progress: 40% (2/5 top-level steps completed)

✅ 1. Review spec [completed]
✅ 2. Check library support [completed]
🔄 3. Create comprehensive test suite [in-progress] (sub-plan: 25% complete)
⏳ 4. Run tests [pending, depends on 3]
⏳ 5. Commit and create MR [pending, depends on 4]
```

### Example 2: Maximum Nesting Depth (2 Levels)

**Scenario:** Sub-step 3.2 "Implement pytest fixtures" is still complex.

```
@coordinator focus-on 3
@coordinator expand-step 3.2
```

**Coordinator:**
```
✅ Step 3.2 expanded into sub-sub-steps
📍 Active context: step_3.2

Sub-plan for Step 3.2:
3.2.1 @pytest-async-systemtest - Add gRPC channel fixture [pending]
3.2.2 @pytest-async-systemtest - Add OCPP client fixture [pending, depends on 3.2.1]

Progress: 📍 Step 3.2: 0% (0/2 sub-steps completed)
```

**Attempting to go deeper is rejected:**

```
@coordinator expand-step 3.2.1
```

```
❌ Maximum nesting depth reached (2 levels)

Step 3.2.1 cannot have sub-steps.

Suggestions:
- Keep step 3.2.1 atomic (single responsibility)
- If truly complex, create separate linked plan
- Collapse current sub-plan and restructure
```

### Example 3: Automatic Knowledge Capture

**Scenario:** Agent responses automatically populate knowledge objects.

**User executes step:**
```
@ocpp-protocol Review OCPP 2.0.1 StartTransaction specification
```

**Agent response:**
```
The StartTransaction message in OCPP 2.0.1 spec version B07 has changed from 1.6:
- transactionId is now in the initial event, not in the response
- idToken is mandatory and must include idTokenType
- groupIdToken is optional for fleet operations

I recommend using spec version B07 as reference for implementation.

See: https://openchargealliance.org/protocols/ocpp-201/
```

**User marks complete:**
```
@coordinator step 1 completed
```

**Coordinator automatically extracts knowledge:**
```
✅ Step 1 completed: Review StartTransaction spec

📚 Knowledge captured:
- Decision: "Use OCPP 2.0.1 spec version B07 as reference"
- Learning: "StartTransaction requires transactionId in initial event, not in response"
- Reference: https://openchargealliance.org/protocols/ocpp-201/

Progress: 20% (1/5 steps completed)
Next: Step 2
```

**View captured knowledge in plan JSON:**
```json
{
  "step_id": "1",
  "knowledge": {
    "decisions": [
      "Use OCPP 2.0.1 spec version B07 as reference"
    ],
    "learnings": [
      "StartTransaction requires transactionId in initial event, not in response",
      "idToken must include idTokenType (mandatory in 2.0.1)"
    ],
    "blockers": [],
    "references": [
      "https://openchargealliance.org/protocols/ocpp-201/"
    ]
  }
}
```

### Example 4: Correcting Misextracted Knowledge

**Scenario:** Coordinator incorrectly extracts knowledge.

**Agent response:**
```
The session-scoped fixtures significantly reduce overhead. In my testing,
connection time went from 500ms to 100ms per test. This is a huge improvement!
```

**Coordinator auto-extracts:**
```
📚 Knowledge captured:
- Learning: "Connection time went from 500ms to 100ms per test"
```

**User notices this is too specific (not a general learning):**
```
@coordinator step 3.2 ignore-last-knowledge
```

**Coordinator:**
```
✅ Last knowledge entry removed from step 3.2

You can add correct knowledge manually:
@coordinator step 3.2 add-knowledge: Session-scoped fixtures reduce gRPC channel overhead by 80%
```

### Example 5: Blocker with Automatic Knowledge Capture

**Scenario:** Step blocked, resolution captured automatically.

```
@coordinator step 2 blocked: ETF server v2.0 doesn't support StatusNotification context
```

**Coordinator:**
```
🚫 Step 2 blocked

📚 Blocker captured:
- Issue: "ETF server v2.0 doesn't support StatusNotification context"
- Blocked at: 2026-01-19T15:00:00Z

Parent step 3 status updated to: blocked
```

**When resolved:**
```
@coordinator step 2 in progress
@etf-library <implement workaround or upgrade>
... agent suggests: "Upgrade ETF dependency to v2.1.0"
@coordinator step 2 completed
```

**Coordinator automatically updates blocker:**
```
✅ Step 2 completed

📚 Blocker resolved:
- Issue: "ETF server v2.0 doesn't support StatusNotification context"
- Resolution: "Upgraded ETF dependency to v2.1.0"
- Resolved at: 2026-01-19T15:30:00Z

Knowledge persisted in plan for future reference.
```

### Example 6: Artifact Verification

**Scenario:** Coordinator auto-verifies file artifacts exist.

**Step with file artifact:**
```json
{
  "step_id": "3.1",
  "artifacts": [
    {
      "type": "file",
      "path": "tests/suites/test_ocpp_starttransaction.py",
      "verification": "auto",
      "verified_at": null,
      "auto_verified": false
    }
  ]
}
```

**After step completion:**
```
@coordinator step 3.1 completed
```

**Coordinator auto-verifies:**
```
✅ Step 3.1 completed

🔍 Artifact verification:
  ✅ tests/suites/test_ocpp_starttransaction.py (exists, verified automatically)

Artifact status updated in plan.
```

**Manual verification for entire plan:**
```
@coordinator verify-artifacts
```

```
🔍 Verifying artifacts for all steps...

✅ Step 3.1: tests/suites/test_ocpp_starttransaction.py (exists)
⏳ Step 3.3: tests/suites/test_ocpp_starttransaction.py#L50-L200 (pending, step not complete)
❌ Step 5: https://gitlab.com/ebee_smart/systemtests/-/merge_requests/NNN (URL, manual verification required)

2/3 artifacts verified automatically
1/3 requires manual verification
```

### Example 7: Exporting Knowledge for Documentation

**Scenario:** Plan completed, export captured knowledge for team documentation.

```
@coordinator export-knowledge
```

**Output file:** `.copilot-agents/knowledge/2026-01-19_add-ocpp-test.md`

```markdown
# Knowledge Captured: Add OCPP Test

**Plan**: 2026-01-19_14-30-00_add-ocpp-test
**Stack**: systemtests-python
**Exported**: 2026-01-19T16:00:00Z

## Step 1: Review Protocol Spec (@ocpp-protocol)

### Decisions
- Used OCPP 2.0.1 spec version B07 as reference

### Learnings
- StartTransaction requires transactionId in initial event

### References
- https://openchargealliance.org/protocols/ocpp-201/

## Step 3: Create Test Suite (@pytest-async-systemtest)

### Step 3.2: Implement Fixtures

#### Decisions
- Use session-scoped fixture for gRPC channel

#### Learnings
- Session-scoped fixtures reduce gRPC channel overhead by 80%

#### Blockers Encountered
- **Issue**: ETF server v2.0 didn't support StatusNotification context
- **Resolution**: Upgraded to ETF v2.1.0
- **Resolved**: 2026-01-19T15:30:00Z

## Summary

Total knowledge entries: 6
- Decisions: 3
- Learnings: 3
- Blockers resolved: 1
```

**Use exported knowledge for:**
- Team documentation
- ADRs (Architecture Decision Records)
- Retrospectives
- Onboarding materials

### Example 8: Searching Knowledge Across Plans

**Scenario:** Facing similar problem, search past knowledge.

```
@coordinator search-knowledge gRPC channel overhead
```

```
🔍 Found 2 matches for "gRPC channel overhead":

Plan: 2026-01-18_add-grpc-method (archived)
Step 2: Implement gRPC Client
- Learning: "gRPC channel reuse critical for performance"

Plan: 2026-01-19_add-ocpp-test (active)  
Step 3.2: Add Fixtures
- Learning: "Session-scoped fixtures reduce gRPC channel overhead by 80%"

Tip: Read plan files for full context
```

### Example 9: Resuming After Interruption (Context Preserved)

**Scenario:** Work interrupted, resume later with context intact.

**Before interruption:**
- Working in step 3's sub-plan (active_context: "step_3")
- Step 3.2 in progress

**Resume session:**
```
@coordinator show-plan
```

**Coordinator restores context:**
```
📍 Step 3 Context: Create comprehensive test suite
Progress: 50% (2/4 sub-steps completed)

✅ 3.1 - Create test file [completed]
✅ 3.2 - Implement fixtures [completed]
🔄 3.3 - Write success tests [in-progress]  ← Resume here
⏳ 3.4 - Write error tests [pending]

Context automatically restored from active_context field.
```

**View main plan:**
```
@coordinator show-plan --full
```

```
📋 Full Plan Hierarchy

Main Level (40% complete):
✅ 1. Review spec
✅ 2. Check library
🔄 3. Create test suite (sub-plan: 50% complete)
   ✅ 3.1 Create test file
   ✅ 3.2 Implement fixtures
      ✅ 3.2.1 Add gRPC channel fixture
      ✅ 3.2.2 Add OCPP client fixture
   🔄 3.3 Write success tests ← Current
   ⏳ 3.4 Write error tests
⏳ 4. Run tests
⏳ 5. Commit and create MR
```

### Example 10: v1.0 Plan Auto-Migration

**Scenario:** Opening old v1.0 plan.

**Old plan file** (v1.0 structure):
```json
{
  "schema_version": "1.0",
  "plan_id": "2026-01-15_old-task",
  "steps": [
    {
      "id": 1,
      "artifacts": ["file1.py", "file2.py"],
      "status": "completed"
    }
  ]
}
```

**User opens plan:**
```
@coordinator show-plan
```

**Coordinator auto-migrates:**
```
🔄 Migrating plan from v1.0 → v2.0...

Migrations applied:
- ✅ Converted numeric step IDs to strings (1 → "1")
- ✅ Upgraded artifacts to object format with verification
- ✅ Added empty knowledge objects
- ✅ Added active_context: "main"
- ✅ Added parallel_group, priority, estimated_tokens, context_needed fields
- ✅ Updated schema_version to "2.0"

Plan loaded successfully.

📋 Plan: old-task
Progress: 100% (all steps completed)

✅ 1. [completed]

Artifacts:
  ✅ file1.py (auto-verified)
  ✅ file2.py (auto-verified)
```

**Migrated plan saved automatically** - original backed up as `*.v1.0.backup.json`

## Autonomous Execution

### Overview

Plans can be executed autonomously via the `plan-execution` MCP server or the `plan-executor.py` script. This uses the Anthropic Messages API (sequential) or Batch API (parallel waves).

### Via Coordinator Commands

```
@coordinator execute-step 1              # Execute single step via Messages API
@coordinator execute-plan                # Execute all steps sequentially
@coordinator execute-plan --batch        # Execute parallel waves via Batch API
@coordinator execution-status            # Check execution progress
```

### Via Plan Executor Script

```bash
# Dry-run: show execution schedule without calling APIs
python framework/scripts/plan-executor.py plan.json --mode dry-run

# Sequential: one step at a time via Messages API
python framework/scripts/plan-executor.py plan.json --mode sequential

# Batch: parallel waves via Batch API
python framework/scripts/plan-executor.py plan.json --mode batch

# Skip approval prompts for CI/headless use
python framework/scripts/plan-executor.py plan.json --mode sequential --auto-approve

# Resume from where you left off
python framework/scripts/plan-executor.py plan.json --mode sequential --resume
```

### Via MCP Tools

```
plan-execution.execute_step(plan_path="plan.json", step_id="1")
plan-execution.execute_wave(plan_path="plan.json", wave_number=1)
plan-execution.get_execution_status(plan_path="plan.json")
plan-execution.resume_execution(plan_path="plan.json")
plan-execution.validate_plan_for_execution(plan_path="plan.json")
```

### Human Approval Gates

Steps with `priority: "critical"` or `"high"` pause for human approval by default. Options: approve (`y`), skip (`s`), or abort (`a`). Use `--auto-approve` to bypass for CI.

## Advanced Examples

### Example 1: Cross-Stack Plan

**Task:** Add new OCPP feature requiring both Rust implementation and Python test

```
@coordinator plan: Add OCPP 2.0.1 CancelReservation support
```

**Coordinator creates two linked plans:**

**Plan 1:** `ocpp20-rust/.copilot-agents/plans/2026-01-19_15-00-00_add-cancelreservation.json`
```json
{
  "plan_id": "2026-01-19_15-00-00_add-cancelreservation",
  "stack": "ocpp20-rust",
  "description": "Implement OCPP 2.0.1 CancelReservation handler",
  "related_plans": ["systemtests-python:2026-01-19_15-00-00_add-cancelreservation"],
  "steps": [
    {
      "id": 1,
      "agent": "@transaction-lifecycle-expert",
      "task": "Design reservation cancellation state machine"
    },
    {
      "id": 2,
      "agent": "@websocket-protocol-handler",
      "task": "Implement CancelReservation message handler"
    }
  ]
}
```

**Plan 2:** `systemtests-python/.copilot-agents/plans/2026-01-19_15-00-00_add-cancelreservation.json`
```json
{
  "plan_id": "2026-01-19_15-00-00_add-cancelreservation",
  "stack": "systemtests-python",
  "description": "Add integration test for CancelReservation",
  "related_plans": ["ocpp20-rust:2026-01-19_15-00-00_add-cancelreservation"],
  "steps": [
    {
      "id": 1,
      "agent": "@pytest-async-systemtest",
      "task": "Create test_cancel_reservation.py",
      "cross_stack_dependencies": [
        {
          "plan": "ocpp20-rust:2026-01-19_15-00-00_add-cancelreservation",
          "step": 2,
          "description": "Wait for Rust handler implementation"
        }
      ],
      "status": "blocked"
    }
  ]
}
```

**Workflow:**
1. Switch to `ocpp20-rust` workspace
2. Execute Rust implementation steps
3. Switch to `systemtests-python` workspace
4. Test becomes unblocked when Rust step 2 completes
5. Archive both plans when complete

### Example 2: Multi-Agent Collaboration

**Task:** Add gRPC method and update ETF client wrapper

```
@coordinator plan: Add gRPC GetChargingProfiles method with ETF client wrapper
```

**Generated plan includes multi-agent step:**

```json
{
  "id": 3,
  "agent": "@grpc-protobuf-python",
  "task": "Implement gRPC client method (consult @etf-library for API patterns, then @etf-workbench-integration for TestSuite integration)",
  "dependencies": [1, 2],
  "artifacts": ["clients.py updated", "workbench.py updated"]
}
```

**Execution:**
1. Primary agent (`@grpc-protobuf-python`) implements the gRPC client
2. Consult `@etf-library` for API design patterns
3. Consult `@etf-workbench-integration` for TestSuite integration
4. One step, multiple agents collaborating

### Example 3: Handling Pre-flight Validation Failures

**User:** `@coordinator plan: Write Rust unit test`

**Coordinator response:**

```
❌ Pre-flight Validation Failed

Issues:
1. ❌ Agent not found: @rust-unittest-expert
   - No agent with unit testing expertise in systemtests-python stack
   
2. ⚠️  Stack mismatch detected
   - Task mentions "Rust" but current stack is systemtests-python
   - Did you mean ocpp20-rust stack?

Suggestions:
1. Switch to ocpp20-rust workspace
2. Try: @coordinator plan: Write unit test for CancelReservation handler

No plan created.
```

### Example 4: Listing All Plans

```
@coordinator list-plans
```

**Response:**

```
📁 Plans in systemtests-python stack:

Active:
✅ 2026-01-19_14-30-00_add-ocpp-starttransaction-test (60% complete)

Archived:
📦 2026-01-18_10-15-00_refactor-conftest-fixtures (100% complete)
📦 2026-01-17_16-00-00_add-heartbeat-test (100% complete)
📦 2026-01-15_09-30-00_update-grpc-stubs (100% complete)

Total: 4 plans (1 active, 3 archived)
```

### Example 5: Modifying a Plan Mid-Execution

Plans are JSON files. You can manually edit them if needed:

```bash
# Open the active plan
code .copilot-agents/plans/2026-01-19_14-30-00_add-ocpp-starttransaction-test.json

# Edit steps, add new ones, reorder, etc.
# Update the updated_at timestamp
# Save

# Tell coordinator to reload
@coordinator show-plan
```

**Note:** Manual edits bypass validation. Use with caution.

## Plan File Structure

Plans are stored in `.copilot-agents/plans/` within each stack:

```
stacks/systemtests-python/
├── .copilot-agents/
│   └── plans/
│       ├── 2026-01-19_14-30-00_add-ocpp-starttransaction-test.json  (active)
│       ├── 2026-01-18_10-15-00_refactor-conftest-fixtures.json      (archived)
│       └── 2026-01-17_16-00-00_add-heartbeat-test.json              (archived)
```

**Filename format:** `YYYY-MM-DD_HH-MM-SS_<task-slug>.json`

**Benefits:**
- Chronologically sorted by default
- Human-readable task names
- Easy to find recent plans
- Manual cleanup when needed

## Commands Reference

| Command | Description |
|---------|-------------|
| `@coordinator plan: <task>` | Create new implementation plan |
| `@coordinator show-plan` | Display active plan and progress |
| `@coordinator list-plans` | List all plans in current stack |
| `@coordinator step <N> completed` | Mark step as completed |
| `@coordinator step <N> blocked: <reason>` | Mark step as blocked |
| `@coordinator step <N> in progress` | Mark step as in-progress |
| `@coordinator step <N> skipped: <reason>` | Skip a step |
| `@coordinator expand-step <N>` | Decompose step into sub-steps |
| `@coordinator focus-on <N>` | Navigate to sub-plan context |
| `@coordinator focus-main` | Return to main plan context |
| `@coordinator archive-plan` | Archive active plan (manual only) |
| `@coordinator execute-step <N>` | Execute single step via Messages API |
| `@coordinator execute-plan` | Execute all steps sequentially |
| `@coordinator execute-plan --batch` | Execute parallel waves via Batch API |
| `@coordinator execution-status` | Check execution progress |
| `@coordinator search-knowledge <query>` | Search captured knowledge |
| `@coordinator export-knowledge` | Export knowledge to markdown |

## Best Practices

### ✅ Do

- Create plans for multi-step tasks
- Update progress after each step completion
- Report blockers immediately
- Review completed work before archiving
- Use descriptive task names for readable filenames
- Check `show-plan` after returning to a task

### ❌ Don't

- Create multiple active plans in same stack (will be rejected)
- Expect auto-archival (always manual)
- Skip progress updates (coordinator can't track otherwise)
- Edit plan JSON without updating `updated_at`
- Rely on hardcoded agent names (let coordinator discover)

## Troubleshooting

### "Active plan already exists"

**Problem:** Tried to create new plan while one is active

**Solution:**
```
@coordinator archive-plan
@coordinator plan: <new task>
```

### "Agent not found in stack"

**Problem:** Pre-flight validation failed

**Solution:**
1. Check which stack you're in
2. Verify agent exists: `ls .github/agents/`
3. Switch stacks if needed
4. Let coordinator discover agents dynamically

### "Can't find active plan"

**Problem:** Plan file deleted or corrupted

**Solution:**
```
# List all plans to find it
@coordinator list-plans

# Create new plan if needed
@coordinator plan: <task>
```

### Plan file disappeared

**Problem:** Plan JSON file was deleted

**Solution:** Plans are just JSON files. Git restore if committed, or recreate:
```bash
git restore .copilot-agents/plans/2026-01-19_14-30-00_add-test.json
```

## Integration with GitLab Workflow

Combine coordinator plans with the `@gitlab` agent workflow:

```
# Start work
@coordinator plan: Add feature X

# Execute steps 1-4
...

# Final step: commit and create MR
@coordinator step 5 in progress
@gitlab
# (gitlab creates Notion entry, commits, creates MR)

# Update coordinator
@coordinator step 5 completed

# Archive when MR merged
@coordinator archive-plan
```

This creates full traceability from plan → implementation → commit → MR → Notion.

## See Also

- [framework/core/common-agents/coordinator.agent.md](../framework/core/common-agents/coordinator.agent.md) — Full coordinator agent specification
- [docs/usage-guide.md](usage-guide.md) — Day-to-day workflows
- [framework/schemas/plan-v2.schema.json](../framework/schemas/plan-v2.schema.json) — Plan schema v2.0
- [framework/architecture/structure.md](../framework/architecture/structure.md) — Repository structure
- [GETTING_STARTED.md](../GETTING_STARTED.md) — Setup walkthrough
