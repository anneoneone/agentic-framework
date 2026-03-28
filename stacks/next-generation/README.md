# next-generation Stack

Agent stack for the **NEXTgeneration** talent agency platform — a Next.js 16 web application for a young actors agency in Berlin.

## Project

- **Type**: Linked stack (external repo)
- **Repo**: `/Users/anton/Seafile/Work/next-generation/git-project/next-generation`
- **Domain**: next-generation-schauspiel.de
- **Tech Stack**: Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, GSAP, Contao CMS
- **Deployment**: Vercel

## Agents

### Specialist Agents
| Agent | Domain |
|-------|--------|
| @nextjs-frontend | App Router pages, Server Components/Actions, API routes, ISR, SEO |
| @contao-api | Contao CMS API client, data providers, type mapping, caching |
| @ui-styling | Tailwind CSS 4, GSAP animations, component styling |
| @playwright-testing | Playwright E2E tests, form validation, anti-spam checks |

### Common Agents (symlinked)
- @coordinator, @planner, @gitlab

## Quick Start

```bash
# Open workspace
code stacks/next-generation/next-generation.code-workspace

# Restore project symlink (new machine)
python framework/scripts/link-stack.py --stack next-generation

# Validate agents
python framework/scripts/validate-agent.py --stack next-generation
```
