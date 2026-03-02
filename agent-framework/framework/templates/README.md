# Templates

This directory contains **boilerplate and templates** for creating new stacks, agents, and documentation.

## Contents

### Stack Templates
- [stack-creation-template.md](stack-creation-template.md) - Template for creating new stacks

### Agent Templates
- Future: `agent-template.md` - Template for new agent files
- Future: `language-expert-template.md` - Template for language-specific experts
- Future: `protocol-handler-template.md` - Template for protocol handlers

### Documentation Templates
- Future: `README-template.md` - Template for stack README files
- Future: `SHARED_KNOWLEDGE-template.md` - Template for stack knowledge bases

## Usage

These templates are used by:
- **@writer** agent when generating new stacks
- **@template-generator** agent when creating new agent templates
- Developers manually creating new components

## Template Conventions

All templates use:
- **Placeholders**: `[STACKNAME]`, `[DESCRIPTION]`, `[AUTHOR]`, etc.
- **Comments**: `<!-- TODO: ... -->` for guidance
- **Sections**: Clear structure with explanatory comments
- **Examples**: Concrete examples where helpful

## Related Documentation

- **Architecture**: See [../architecture/](../architecture/) for design rationale
- **User Guides**: See [../docs/](../docs/) for usage instructions
- **Quick Start**: See [../README.md](../README.md) for framework overview

## Adding New Templates

When creating templates:
1. Use clear, descriptive placeholders
2. Include comments explaining each section
3. Provide concrete examples
4. Follow the pattern of existing templates
5. Test with actual generation/usage
