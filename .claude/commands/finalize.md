# Finalize

Run post-plan completion tasks: lint, test, commit, and optionally merge.

## Input

`$ARGUMENTS` can be:
- Empty: finalize the most recently completed plan
- A plan file path
- `--skip-lint`: skip linting
- `--skip-tests`: skip tests
- `--no-commit`: do everything except commit

## Workflow

### Step 1: Find completed plan

Load the plan and verify it's completed (all steps done or skipped).
If the plan still has pending/in-progress steps, warn and ask if user wants to proceed anyway.

### Step 2: Gather changes

Review what was modified during plan execution:
- Collect `output.files_modified` and `output.files_created` from all completed steps
- Run `git status` to see actual working tree changes
- Show a summary of all changes

### Step 3: Lint (unless --skip-lint)

Detect the project's linting setup and run appropriate linters:
- **Python**: `ruff check --fix` or `flake8`
- **Rust**: `cargo clippy --fix`
- **JavaScript/TypeScript**: `npm run lint -- --fix` or `npx eslint --fix`
- **Go**: `golangci-lint run --fix`

If linting produces errors that can't be auto-fixed, show them and ask user how to proceed.

### Step 4: Test (unless --skip-tests)

Detect and run the project's test suite:
- **Python**: `pytest`
- **Rust**: `cargo test`
- **JavaScript/TypeScript**: `npm test`
- **Go**: `go test ./...`

If tests fail:
1. Show failing tests
2. Ask if user wants to fix them now or commit anyway
3. If fixing, identify the relevant step/agent and suggest a fix approach

### Step 5: Commit (unless --no-commit)

1. Stage all relevant files (from step 2)
2. Generate a commit message based on the plan:
   - Use plan description as the commit subject
   - List key changes in the body
   - Reference the plan ID
3. Ask user to confirm or edit the commit message
4. Create the commit

### Step 6: Knowledge export

After finalization:
1. Record completion in memento:
   ```
   memento-knowledge.add_decision(
     content="Plan <plan_id> completed and finalized. Changes: <summary>",
     stack="<stack>",
     agent="@planner"
   )
   ```
2. Archive the plan: set `overall_status: "archived"` in the plan JSON
3. Show final summary

### Output

```
Finalization complete:
- Lint: [passed/fixed N issues/skipped]
- Tests: [passed/N failures/skipped]
- Commit: [hash] "<message>"
- Plan archived: <plan_id>
```
