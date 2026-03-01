# Repository structure overview

This repository contains GitHub Copilot agents and workspace configurations for the ebee monorepo.

## Directory Layout

- **[stacks/](stacks/)** - Stack workspaces
  - Stack agents live in `stacks/STACKNAME/.github/agents/*.agent.md`
  - Each stack has `monorepo -> /path/to/clone` symlink for service paths

- **[.github/agents/](.github/agents/)** - Legacy global discovery directory (optional)
  - Kept for migration/backward compatibility only

- **[docs/](docs/)** - Documentation
  - `multi-clone-setup.md` - Multi-clone configuration guide
  - `stack-map.md` - Monorepo architecture reference
  - `usage-guide.md` - How to use the agents
  - `ANALYSIS_ebee_rust_agents.md` - Architecture analysis

- **[workspaces/](workspaces/)** - VS Code workspace files
  - `rust-ebee.code-workspace` - Rust development
  - `python-test.code-workspace` - Python testing
  - `cpp-firmware.code-workspace` - C++ firmware
  - `docs.code-workspace` - Documentation

- **[scripts/](scripts/)** - Utility scripts
  - `setup-ebee-agents.sh` - Legacy helper (not required for stack-local workspaces)

## Quick Navigation

- **Getting started:** See [README.md](README.md)
- **Multi-clone setup:** See [docs/multi-clone-setup.md](docs/multi-clone-setup.md)
- **Understanding agents:** See [docs/usage-guide.md](docs/usage-guide.md)
- **Monorepo structure:** See [docs/stack-map.md](docs/stack-map.md)
