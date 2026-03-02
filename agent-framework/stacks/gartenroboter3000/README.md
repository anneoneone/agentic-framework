# 🌱 Gartenroboter3000 Stack

Raspberry Pi-based garden automation system with intelligent watering control.

## Quick Start

```bash
# Open this workspace
code ~/git/copilot-agents/stacks/gartenroboter3000/gartenroboter3000.code-workspace

# Run in development mode
cd source
uv run gartenroboter --mock --debug
```

## Available Agents

| Agent | Focus |
|-------|-------|
| **@async-python** | asyncio patterns, event loops, concurrent programming |
| **@telegram-bot** | python-telegram-bot v21, handlers, bot security |
| **@raspi-hardware** | GPIO, SPI, sensors, hardware abstraction |
| **@pytest-async** | async testing, mock fixtures, test organization |
| **@pydantic-config** | Pydantic v2, settings, environment config |

## Project Structure

```
source/
├── src/gartenroboter/
│   ├── app.py               # Application factory, Container
│   ├── config/              # Pydantic settings
│   ├── core/                # Business logic (sensors, pump, watering)
│   ├── services/            # External services (telegram, weather)
│   └── infra/               # Infrastructure (gpio, database, scheduler)
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
└── pyproject.toml           # Project config
```

## Common Tasks

### Development

```bash
# Run locally with mock hardware
uv run gartenroboter --mock --debug

# Run tests
uv run pytest -v

# Type check
uv run mypy src

# Lint and format
uv run ruff check src tests
uv run ruff format src tests
```

### Deployment to Raspberry Pi

```bash
# SSH to Pi
ssh pi@gartenroboter.local

# Pull latest
cd /opt/gartenroboter3000
git pull

# Restart service
sudo systemctl restart gartenroboter

# View logs
journalctl -u gartenroboter -f
```

## Agent Usage Examples

### @async-python

```
@async-python How do I add a new background task to the scheduler?
@async-python Review the shutdown logic in app.py for race conditions
```

### @telegram-bot

```
@telegram-bot Add a /zones command to show all zone statuses
@telegram-bot How do I add an inline keyboard for zone selection?
```

### @raspi-hardware

```
@raspi-hardware Add support for a BME280 temperature/humidity sensor
@raspi-hardware The ultrasonic sensor returns -1.0, how do I debug?
```

### @pytest-async

```
@pytest-async Write tests for the new /zones command
@pytest-async How do I test the watering engine with mocked sensors?
```

### @pydantic-config

```
@pydantic-config Add a new setting for watering duration per zone
@pydantic-config How do I validate that GPIO pins are unique?
```

## Links

- **Source Repository**: [source/](source/)
- **Shared Knowledge**: [docs/SHARED_KNOWLEDGE.md](docs/SHARED_KNOWLEDGE.md)
- **README**: [source/README.md](source/README.md)
