# Multi-Clone Setup for Copilot Agents

This guide explains how to use your personal Copilot agents across multiple monorepo clones.

## 🎯 Solution Overview

**Stack-local approach (recommended):**
- 🧷 Each stack contains a `monorepo` symlink pointing at the clone you want to work on
- 📁 Stack workspaces use relative paths (`monorepo/...`) so they don’t depend on `${env:...}` expansion
- 🤖 Agents live inside the stack at `stacks/STACKNAME/.github/agents/`

## 🚀 Quick Start

### 1. Point a stack at a clone

```bash
ln -snf "$HOME/0_git/0_ebee_meta_projects/monorepo" stacks/STACKNAME/monorepo
```

### 2. Open the stack workspace

```bash
code stacks/STACKNAME/STACKNAME.code-workspace
```

## 🔄 Switching Between Clones

Update the stack’s `monorepo` symlink:

```bash
# Switch stack to feature clone
ln -snf "$HOME/0_git/feature-123-clone" stacks/STACKNAME/monorepo

# Switch stack back to main clone
ln -snf "$HOME/0_git/0_ebee_meta_projects/monorepo" stacks/STACKNAME/monorepo
```

## 📝 How It Works

### Workspace Files (Shared)
```json
{
  "folders": [
    {"name": "🤖 Agents", "path": ".github/agents"},
    {"name": "📦 Service", "path": "monorepo/appfs/ebee/ocpp20"},
    {"name": "📚 Stack", "path": "."}
  ]
}
```

Same workspace file works with any clone by updating `stacks/STACKNAME/monorepo`.

## 🔧 Adding New Clones

```bash
ln -snf "/path/to/new-clone" stacks/STACKNAME/monorepo
```

## ✅ Verification

Check setup worked:

```bash
# 1. Verify the stack points to the desired clone
ls -la stacks/STACKNAME/monorepo

# 2. Test workspace opens
code stacks/STACKNAME/STACKNAME.code-workspace
```

## 🎨 Workflow Examples

### Daily Work
```bash
# Morning: Work on feature clone
ln -snf "$HOME/0_git/feature-456-clone" stacks/STACKNAME/monorepo
code stacks/STACKNAME/STACKNAME.code-workspace

# Afternoon: Review colleague's MR clone
ln -snf "$HOME/0_git/mr-review-clone" stacks/STACKNAME/monorepo
code stacks/STACKNAME/STACKNAME.code-workspace
```

### Backporting
```bash
# Implement on main
ln -snf "$HOME/0_git/main-clone" stacks/STACKNAME/monorepo
code stacks/STACKNAME/STACKNAME.code-workspace

# Backport to v1.2.x
ln -snf "$HOME/0_git/v1.2.x-clone" stacks/STACKNAME/monorepo
code stacks/STACKNAME/STACKNAME.code-workspace
```

## 📚 Reference

- **Stacks:** `stacks/STACKNAME/`
- **Stack agents:** `stacks/STACKNAME/.github/agents/`
- **Clone selection:** `stacks/STACKNAME/monorepo -> /path/to/clone`
