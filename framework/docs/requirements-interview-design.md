# Requirements Interview Design

Design document for the interactive requirements-gathering mode in stack creation.
Used by `@analyzer` (interview mode) and `framework/scripts/requirements-interview.py`.

## Purpose

When a user wants to create a stack for a **greenfield project** (no code exists yet),
`@analyzer` enters interview mode to gather requirements interactively. The output is
a `RequirementsProfile` that feeds the same agent-recommendation logic as file-analysis mode.

---

## Interview Questions

### Phase 1 — Project Identity (required)

| # | Question | Key | Type | Example |
|---|----------|-----|------|---------|
| 1 | What is the project name or slug? | `project_name` | string | `"live-moafunk"` |
| 2 | In one sentence, what does this project do? | `description` | string | `"Real-time EV charging session management"` |
| 3 | What is the primary domain? | `domain` | choice | `backend`, `frontend`, `firmware`, `data`, `infra`, `fullstack`, `library`, `cli` |

### Phase 2 — Tech Stack (required)

| # | Question | Key | Type | Example |
|---|----------|-----|------|---------|
| 4 | What language(s) will be used? | `languages` | multi-choice + freetext | `["Rust", "Python"]` |
| 5 | What frameworks or runtimes? | `frameworks` | multi-choice + freetext | `["Axum", "Tokio", "FastAPI"]` |
| 6 | What databases or storage systems? | `storage` | multi-choice + freetext | `["PostgreSQL", "Redis"]` |
| 7 | Any external protocols or APIs to integrate? | `integrations` | freetext | `"OCPP 2.0 over WebSocket, gRPC internal"` |

### Phase 3 — Architecture (recommended)

| # | Question | Key | Type | Example |
|---|----------|-----|------|---------|
| 8 | How would you describe the architecture? | `architecture` | choice | `microservice`, `monolith`, `library`, `firmware`, `cli`, `event-driven` |
| 9 | What are the main workstreams or modules? | `workstreams` | freetext list | `["WebSocket handler", "State machine", "DB persistence"]` |
| 10 | What testing strategy will you use? | `testing` | multi-choice | `unit`, `integration`, `e2e`, `property-based`, `load` |

### Phase 4 — Team & Scale (optional)

| # | Question | Key | Type | Example |
|---|----------|-----|------|---------|
| 11 | What is the team size? | `team_size` | choice | `solo`, `small (2-5)`, `medium (6-15)`, `large (15+)` |
| 12 | Are there any shared/cross-stack agents already available? | `shared_agents` | freetext | `"@ocpp-protocol, @documentation"` |

---

## RequirementsProfile Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RequirementsProfile",
  "description": "Structured output from the requirements interview, used to drive agent recommendations",
  "type": "object",
  "required": ["project_name", "description", "domain", "languages"],
  "properties": {
    "project_name": {
      "type": "string",
      "description": "Short slug used as the stack directory name",
      "pattern": "^[a-z0-9][a-z0-9-]*[a-z0-9]$"
    },
    "description": {
      "type": "string",
      "description": "One-sentence project description"
    },
    "domain": {
      "type": "string",
      "enum": ["backend", "frontend", "firmware", "data", "infra", "fullstack", "library", "cli", "other"]
    },
    "languages": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1,
      "description": "Primary programming languages",
      "examples": [["Rust"], ["Python", "TypeScript"]]
    },
    "frameworks": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Frameworks, runtimes, and major libraries"
    },
    "storage": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Databases, caches, message queues"
    },
    "integrations": {
      "type": "string",
      "description": "External protocols and APIs (free text)"
    },
    "architecture": {
      "type": "string",
      "enum": ["microservice", "monolith", "library", "firmware", "cli", "event-driven", "other"]
    },
    "workstreams": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Main modules or areas of work"
    },
    "testing": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["unit", "integration", "e2e", "property-based", "load", "manual"]
      }
    },
    "team_size": {
      "type": "string",
      "enum": ["solo", "small", "medium", "large"]
    },
    "shared_agents": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Existing shared agents to symlink (e.g. '@ocpp-protocol')"
    }
  }
}
```

---

## Answer → Agent Recommendation Mapping

The mapping below guides `@analyzer` in translating a `RequirementsProfile` into agent proposals.
Patterns are additive — multiple rules can match.

### Language-driven agents

| Condition | Recommended Agent | Justification |
|-----------|------------------|---------------|
| `languages` contains `"Rust"` | `@rust-expert` | Ownership, lifetimes, error handling, Cargo |
| `languages` contains `"Rust"` + `frameworks` contains `"Tokio"` | `@async-tokio` | Async runtime patterns, cancellation safety |
| `languages` contains `"Python"` | `@python-expert` | Type hints, packaging, async with asyncio |
| `languages` contains `"TypeScript"` or `"JavaScript"` | `@ts-frontend` or `@ts-backend` | Depending on domain |
| `languages` contains `"C++"` | `@cpp-expert` | C++17+, memory management, build system |
| `languages` contains `"Go"` | `@go-expert` | Goroutines, interfaces, standard library |

### Framework-driven agents

| Condition | Recommended Agent |
|-----------|------------------|
| `frameworks` contains `"Axum"` | `@axum-backend` |
| `frameworks` contains `"FastAPI"` | `@fastapi-backend` |
| `frameworks` contains `"Vue"` or `"React"` | `@vue-frontend` or `@react-frontend` |
| `frameworks` contains `"pytest"` | `@pytest-expert` |
| `frameworks` contains `"CMake"` | `@cmake-expert` |
| `frameworks` contains `"Docker"` | `@docker-deploy` |

### Storage-driven agents

| Condition | Recommended Agent |
|-----------|------------------|
| `storage` contains `"PostgreSQL"` or `"MySQL"` | `@db-expert` |
| `storage` contains `"Redis"` | include Redis scope in `@db-expert` or `@backend` |
| `storage` contains `"Neo4j"` | `@knowledge-engineer` |

### Integration-driven agents

| Condition | Recommended Agent |
|-----------|------------------|
| `integrations` contains `"OCPP"` | `@ocpp-protocol` (shared) |
| `integrations` contains `"gRPC"` | `@grpc-integration` |
| `integrations` contains `"WebSocket"` | include WS scope in backend agent |
| `integrations` contains `"GraphQL"` | `@graphql-api` |

### Domain-driven fallbacks

| Domain | Default agent set |
|--------|------------------|
| `backend` | `@[lang]-backend`, `@db-expert` |
| `frontend` | `@[framework]-frontend` |
| `firmware` | `@cpp-expert`, `@cmake-expert`, `@hal-expert` |
| `data` | `@python-expert`, `@db-expert` |
| `cli` | `@[lang]-expert` |
| `infra` | `@docker-deploy`, `@ci-cd` |

### Testing agents

| Condition | Add to scope |
|-----------|-------------|
| `testing` contains `"e2e"` or `"integration"` | `@integration-expert` or dedicated test agent |
| `testing` contains `"load"` | note in agent scope, no separate agent unless critical |

### Always included (common agents, symlinked)

- `@coordinator` — routing
- `@gitlab` — commits and MRs

---

## Interview Flow (for @analyzer)

```
1. Greet user:
   "I'll ask you a few questions to design the right agents for your stack.
    Press Enter to skip optional questions."

2. Ask Phase 1 questions (required — loop until answered)

3. Ask Phase 2 questions (required — loop until answered)

4. Ask Phase 3 questions (recommended — allow skip)

5. Ask Phase 4 questions (optional — allow skip)

6. Synthesize:
   - Build RequirementsProfile from answers
   - Apply mapping table to get agent list
   - Deduplicate and limit to 3-5 specialist agents
   - Add justification per agent referencing the answer that triggered it

7. Present recommendations using standard @analyzer output format:
   # Agent Recommendations for [project_name]
   ## Requirements Profile
   ...
   ## Recommended Agents
   ...

8. Ask for confirmation or adjustments before handing off to @writer
```

---

## Example Session

```
@analyzer --interview

I'll ask you a few questions to design the right agents for your stack.

Project name (slug): my-iot-gateway
What does it do? Real-time sensor data ingestion and forwarding over MQTT
Primary domain [backend/frontend/firmware/...]: backend
Languages: Python, C (for embedded client)
Frameworks: FastAPI, paho-mqtt, asyncio
Storage: PostgreSQL, Redis
Integrations: MQTT broker, REST webhooks to third-party APIs
Architecture [microservice/monolith/...]: microservice
Workstreams: MQTT ingestion, REST API, DB persistence, webhook dispatch
Testing: unit, integration
Team size [solo/small/medium/large]: small

→ RequirementsProfile built.
→ Applying recommendation mapping...

# Agent Recommendations for my-iot-gateway

## Stack Analysis
- Stack Name: my-iot-gateway
- Tech Stack: Python 3.12, FastAPI, asyncio, paho-mqtt
- Domain: Backend microservice
- Storage: PostgreSQL + Redis
- Integrations: MQTT, REST webhooks

## Recommended Agents

### Priority 1: @fastapi-backend
Purpose: FastAPI routes, async handlers, Pydantic models, webhook dispatch
Justification: frameworks contains "FastAPI"; REST API workstream identified

### Priority 2: @mqtt-ingestion
Purpose: paho-mqtt subscriber, message parsing, backpressure handling
Justification: integrations contains "MQTT"; ingestion workstream identified

### Priority 3: @db-expert
Purpose: PostgreSQL schema, SQLAlchemy models, Redis caching
Justification: storage contains "PostgreSQL" and "Redis"

### Priority 4: @integration-expert
Purpose: End-to-end testing of MQTT → API → DB pipeline
Justification: testing contains "integration"

### Common Agents (symlinked)
- @coordinator, @gitlab

Shall I proceed with stack creation? [y/n]
```

---

## File Locations

| File | Purpose |
|------|---------|
| `framework/docs/requirements-interview-design.md` | This document |
| `framework/scripts/requirements-interview.py` | CLI script for terminal interviews |
| `.claude/agents/analyzer.agent.md` | Interview mode section added here |
| `.claude/commands/create-stack.md` | `--interview` flag documented here |
