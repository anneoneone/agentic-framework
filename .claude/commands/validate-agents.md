# Validate Agents

Validate all agent files against the frontmatter schema.

If `$ARGUMENTS` is provided, validate that specific stack:
```bash
python framework/scripts/validate-agent.py --stack $ARGUMENTS
```

Otherwise validate all agents:
```bash
python framework/scripts/validate-agent.py --all
```

Report the results and offer to fix any errors found.
