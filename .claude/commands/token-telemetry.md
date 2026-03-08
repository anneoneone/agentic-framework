# Token Telemetry

Show token usage statistics across plan executions.

## Input

`$ARGUMENTS` can be:
- Empty or `dashboard`: show key metrics summary
- `report`: detailed usage report (tokens by stack, agent, plan)
- `agent-stats`: per-agent statistics
- `agent-stats @agent-name`: detailed stats for one agent
- `budget-accuracy`: compare estimated vs actual token usage
- `collect`: scan all plans and update the telemetry database

## Workflow

### Dashboard (default)

```bash
python framework/scripts/token-telemetry.py dashboard
```

Shows: total tokens, steps completed, top agents, budget accuracy.

### Report

```bash
python framework/scripts/token-telemetry.py report
```

Shows: tokens by stack, top agents, most expensive plans, accuracy metrics.

### Agent Stats

```bash
python framework/scripts/token-telemetry.py agent-stats [--agent @name]
```

### Budget Accuracy

```bash
python framework/scripts/token-telemetry.py budget-accuracy
```

Compares estimated_tokens vs actual tokens_used per agent, with recommendations to adjust estimates.

### Collect

```bash
python framework/scripts/token-telemetry.py collect stacks/
```

Scans all plan JSON files in stacks/*/plans/ and writes new records to `framework/telemetry/token-usage.jsonl`.
