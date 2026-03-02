# Architecture Documentation

This directory contains **framework design documentation** for maintainers and contributors.

## Contents

### Core Architecture
- [stack-architecture.md](stack-architecture.md) - Core framework design and three-tier agent system
- [structure.md](structure.md) - Directory layout and organization rationale
- [migration.md](migration.md) - Migration patterns and history
- [symlink-reference.md](symlink-reference.md) - Symlink strategies and patterns

### Design Decisions
- Future: `design-decisions.md` - Architecture Decision Records (ADRs)

## Audience

These documents are for:
- Framework maintainers
- Contributors making structural changes
- Developers understanding "why" decisions were made

## Related Documentation

- **User Guides**: See [../docs/](../docs/) for how-to guides and tutorials
- **Templates**: See [../templates/](../templates/) for boilerplate and scaffolding
- **Quick Start**: See [../README.md](../README.md) for framework overview

## Guidelines

When adding architecture documentation:
- Focus on **design rationale**, not implementation details
- Document **trade-offs** and alternatives considered
- Explain **why**, not just **what**
- Keep user-facing docs separate (those go in `docs/`)
