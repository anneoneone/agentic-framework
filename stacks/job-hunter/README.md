# Job Hunter

Automated job search platform with web crawling, intelligent scoring, web dashboard, and Telegram notifications.

## Features

- **Profile Management**: Create user profile and dream job profile with keywords, location, remote preferences
- **Keyword Expansion**: NLP-powered keyword discovery and semantic matching
- **Web Crawling**: Automated company discovery and job board scraping (Playwright + BeautifulSoup)
- **Parameterized Scoring**: Weighted multi-attribute scoring (keywords, location, remote, salary, experience)
- **Web Dashboard**: React SPA with login, search management, and scored result views
- **Telegram Bot**: Push notifications for new matches, search management via chat commands

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, SQLAlchemy 2.0, Celery |
| Frontend | React, TypeScript, Tailwind CSS, Vite, TanStack Query |
| Database | PostgreSQL, Redis |
| Scraping | Playwright, BeautifulSoup |
| NLP | spaCy / sentence-transformers |
| Bot | python-telegram-bot |

## Agents

| Agent | Domain |
|-------|--------|
| @backend-api | FastAPI REST API, auth, database, task queue |
| @scraper | Web crawling, job board integration, data extraction |
| @scoring-engine | Profile matching, keyword expansion, weighted scoring |
| @frontend | React dashboard, search UI, result views |
| @telegram-bot | Telegram notifications, bot commands, account linking |
| @coordinator | Cross-agent orchestration (common) |
| @planner | Plan creation and management (common) |
| @gitlab | Git operations and CI/CD (common) |
