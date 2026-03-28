# Stack: anton-kress

Personal portfolio website for Anton Kress — artsy, shader-driven SPA showcasing web development, tool development, and AI development services.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 18 + TypeScript + Vite |
| 3D / Shaders | React Three Fiber, @react-three/drei, GLSL |
| Animation | GSAP + ScrollTrigger, Framer Motion, Lenis |
| Styling | Tailwind CSS |
| State | Zustand |
| Contact | EmailJS |
| Analytics | Plausible |
| Deployment | Vercel |

## Agents

| Agent | Role |
|-------|------|
| [@react-frontend](agents/react-frontend.agent.md) | React components, TypeScript, Vite, Tailwind, Zustand |
| [@webgl-shader-expert](agents/webgl-shader-expert.agent.md) | GLSL shaders, R3F scene graph, WebGL performance |
| [@animation-expert](agents/animation-expert.agent.md) | GSAP timelines, ScrollTrigger, Framer Motion, Lenis |
| [@deployment-integrations](agents/deployment-integrations.agent.md) | Vercel, EmailJS, Plausible, Lighthouse optimization |
| [@coordinator](agents/coordinator.agent.md) | Task routing (common) |
| [@planner](agents/planner.agent.md) | Plan creation (common) |
| [@gitlab](agents/gitlab.agent.md) | Commits and MRs (common) |

## Site Structure

```
Hero (shader scene)
  ↓
About (short bio)
  ↓
Service Selector (interactive 3D)
  ├── Web Development
  ├── Tool Development
  └── AI Development
  ↓
Contact (EmailJS form)
```

## Quick Start

```bash
# Single task
/task @react-frontend "scaffold the Vite + React + Tailwind project"

# Complex plan
/plan "build the Hero section with fullscreen GLSL shader"
/execute-plan
```

## Knowledge

See [docs/knowledge/index.md](docs/knowledge/index.md) for architecture decisions and learnings.
