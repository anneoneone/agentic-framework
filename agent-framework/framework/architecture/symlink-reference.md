# Stack Setup Quick Reference

**TL;DR:** Agents are discovered from a workspace folder root that contains `agents/*.agent.md`.

In this repo, each stack is self-contained:
- Agent files live in `stacks/STACKNAME/agents/`
- The stack workspace includes `agents` and `.` as workspace folders
- The stack contains `monorepo -> /path/to/clone` so service folders don’t rely on `${env:...}` expansion

## One-Time Setup (Per Stack)

Create the directory and the monorepo symlink:

```bash
mkdir -p stacks/STACKNAME/agents
ln -snf "${EBEE_MONOREPO_ROOT}" stacks/STACKNAME/monorepo
```

## Adding Stack Agents

Create the agent files directly in the stack:

```bash
cat > stacks/STACKNAME/agents/AGENTNAME.agent.md <<’AGENT’
---
name: AGENTNAME
description: ...
---

...
AGENT
```

## Verify Agent Files

```bash
ls -la stacks/STACKNAME/agents/
```

## Workspace Configuration

Every workspace you use for agents MUST include a folder root that contains `agents`.

Recommended: use only workspace-relative paths.

```json
{
  "folders": [
    {
      "name": "🤖 Agents (STACKNAME)",
      "path": "agents"
    },
    {
      "name": "📚 Stack (STACKNAME)",
      "path": "."
    },
    {
      "name": "📦 Service Code",
      "path": "monorepo/path/to/service"
    }
    // ... other folders
  ]
}
```

## Troubleshooting Symlinks

| Issue | Solution |
|-------|----------|
| `No such file or directory` | Agent file missing. Check: `ls stacks/STACKNAME/agents/AGENTNAME.agent.md` |
| Agents not showing in workspace | 1) Reload VS Code window 2) Check agent files exist 3) Check `stacks/STACKNAME/monorepo` points to the correct clone |

## Architecture Diagram

```
Stack Workspace:
  stacks/STACKNAME/
    ├─ agents/*.agent.md       (discoverable)
    ├─ monorepo -> /path/to/clone  (service path anchor)
    └─ STACKNAME.code-workspace
```

## Environment Variable (optional)

You can still use `EBEE_MONOREPO_ROOT` to create/update the stack’s `monorepo` symlink:

```bash
ln -snf "${EBEE_MONOREPO_ROOT}" stacks/STACKNAME/monorepo
```

## Commands Reference

| Task | Command |
|------|---------|
| List stack agents | `ls -la stacks/STACKNAME/agents/` |
| Point stack at a clone | `ln -snf /path/to/clone stacks/STACKNAME/monorepo` |
| Test environment variable | `echo ${EBEE_MONOREPO_ROOT}` |

## Remember

- 🎯 **Single source of truth**: Agents stored in `stacks/STACKNAME/agents/`
- 📍 **Workspace uses relative paths**: Avoid `~` and `${userHome}` in `folders[].path`
- 🔄 **Multi-clone support**: Switch clones by updating `stacks/STACKNAME/monorepo`

