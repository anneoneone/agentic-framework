export interface Project {
  title: string
  description: string
  tags: string[]
  url?: string
  highlight?: boolean
}

export const webProjects: Project[] = [
  {
    title: 'Portfolio Site',
    description: 'This site — React + Vite SPA with GLSL shader animations and GSAP scroll choreography.',
    tags: ['React', 'TypeScript', 'R3F', 'GLSL', 'GSAP'],
    highlight: true,
  },
  {
    title: 'SaaS Dashboard',
    description: 'Real-time analytics dashboard with WebSocket data feeds and interactive charts.',
    tags: ['Next.js', 'TypeScript', 'tRPC', 'Prisma', 'Recharts'],
  },
  {
    title: 'E-commerce Platform',
    description: 'Headless storefront with custom CMS integration and edge-cached product pages.',
    tags: ['Astro', 'Sanity', 'Stripe', 'Cloudflare'],
  },
]

export const toolProjects: Project[] = [
  {
    title: 'Agentic Framework v2',
    description: 'Multi-agent orchestration system with plan execution, knowledge graphs, and MCP servers.',
    tags: ['Python', 'Neo4j', 'MCP', 'Claude API'],
    highlight: true,
  },
  {
    title: 'Dev Toolkit CLI',
    description: 'Personal CLI tool consolidating git workflows, project scaffolding, and env management.',
    tags: ['Python', 'Click', 'Rich', 'Shell'],
  },
  {
    title: 'Log Analyzer',
    description: 'TUI application for real-time log parsing with pattern detection and alerting.',
    tags: ['Python', 'Textual', 'Regex', 'asyncio'],
  },
]

export const aiProjects: Project[] = [
  {
    title: 'Multi-Agent Framework',
    description: 'Stack-based specialist agent system with knowledge persistence and cross-stack learning.',
    tags: ['Claude API', 'Neo4j', 'MCP', 'Python'],
    highlight: true,
  },
  {
    title: 'Knowledge Search MCP',
    description: 'TF-IDF/BM25 search server exposing project knowledge to Claude agents.',
    tags: ['MCP', 'Python', 'JSONL', 'TypeScript'],
  },
  {
    title: 'Plan Execution Engine',
    description: 'Dependency-aware plan executor with wave-based parallel step execution.',
    tags: ['Python', 'Anthropic SDK', 'JSON Schema'],
  },
]
