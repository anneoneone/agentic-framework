# live-moafunk Stack

Copilot agents for the **Moafunk Radio** live streaming platform.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Rust 2021 + Axum 0.7 + Tokio + SQLx (SQLite) |
| **Frontend** | Vue 3.4 + TypeScript 5.3 + Vite 5 + Pinia |
| **Storage** | AWS S3 / Cloudflare R2 |
| **Streaming** | WebSocket + HLS + FLV |
| **Deploy** | Docker + GitHub Actions + AWS Lightsail |

## Available Agents

| Agent | Expertise |
|-------|-----------|
| `@axum-backend` | Rust/Axum handlers, routing, middleware, SQLx |
| `@vue-frontend` | Vue 3 Composition API, Pinia, Vite |
| `@streaming-media` | WebSocket, HLS/FLV, audio capture |
| `@docker-deploy` | Docker, GitHub Actions, Lightsail |
| `@s3-storage` | AWS S3/R2, uploads, presigned URLs |

## Quick Start

```bash
# Open the workspace
code ~/git/copilot-agents/stacks/live-moafunk/live-moafunk.code-workspace

# In Copilot chat, agents are available:
# @axum-backend how do I add a new API endpoint?
# @vue-frontend create a composable for form validation
# @streaming-media explain the WebSocket message protocol
```

## Project Structure

```
source/                          # Symlink to live.moafunk.de
├── backend/                     # Rust backend
│   ├── src/
│   │   ├── main.rs             # App entry, router setup
│   │   ├── handlers/           # HTTP/WS handlers
│   │   ├── auth.rs             # Authentication
│   │   ├── db.rs               # Database operations
│   │   ├── storage.rs          # S3 operations
│   │   └── stream_bridge.rs    # WebSocket state
│   ├── Dockerfile
│   └── docker-compose.yml
├── frontend/                    # Vue frontend
│   ├── src/
│   │   ├── admin/              # Admin SPA
│   │   │   ├── pages/          # Page components
│   │   │   ├── composables/    # Vue composables
│   │   │   └── stores/         # Pinia stores
│   │   ├── player.ts           # Audio player
│   │   └── streamDetector.ts   # Platform detection
│   └── package.json
└── .github/workflows/           # CI/CD pipelines
```

## Documentation

- [DEPLOYMENT.md](source/DEPLOYMENT.md) - Infrastructure and deployment guide
- [backend/README.md](source/backend/README.md) - Backend-specific docs
