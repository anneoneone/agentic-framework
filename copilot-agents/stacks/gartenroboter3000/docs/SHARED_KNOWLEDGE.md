# Shared Knowledge - Gartenroboter3000

Cross-cutting knowledge that all agents should understand.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Container (DI)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Telegram  │  │  Scheduler  │  │   Weather   │             │
│  │     Bot     │  │             │  │   Service   │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Watering Engine                       │   │
│  │   (Checks conditions, decides when/where to water)       │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│         ┌──────────────────┼──────────────────┐                │
│         ▼                  ▼                  ▼                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Sensors   │    │    Pump     │    │  Database   │        │
│  │   Manager   │    │  Controller │    │  (SQLite)   │        │
│  └──────┬──────┘    └──────┬──────┘    └─────────────┘        │
│         │                  │                                   │
│         └────────┬─────────┘                                   │
│                  ▼                                              │
│           ┌─────────────┐                                      │
│           │ GpioInterface│ ←─── MockGpio (dev) / RealGpio (Pi) │
│           └─────────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Key Concepts

### Watering Decision Logic

The watering engine checks these conditions in order:

1. **Pi Temperature** - Skip if > 70°C (thermal protection)
2. **Water Level** - Skip if < 15% (barrel empty)
3. **Time of Day** - Skip if before sunset (avoid evaporation)
4. **Rain Forecast** - Skip if rain expected today
5. **Pump Cooldown** - Skip if pump ran recently (< 5 min)
6. **Soil Moisture** - Water if < 30% (dry)

### Sensor Types

| Sensor | Interface | Measurement | Range |
|--------|-----------|-------------|-------|
| Soil Moisture (x4) | MCP3008 ADC CH0-3 | Capacitive | 0-100% |
| Water Level | HC-SR04 Ultrasonic | Distance to surface | 0-400cm |
| Pi Temperature | `/sys/class/thermal` | CPU temp | 0-85°C |

### Calibration

Soil sensors need calibration:
- **Dry value**: ADC reading when sensor is in dry air (~850-950)
- **Wet value**: ADC reading when sensor is in water (~200-300)
- **Formula**: `percent = (dry - raw) / (dry - wet) * 100`

Water level sensor needs calibration:
- **Empty distance**: Distance to water when barrel is empty
- **Full distance**: Distance to water when barrel is full
- **Formula**: `percent = (empty - current) / (empty - full) * 100`

## Configuration Hierarchy

```
Environment Variables (.env)
         ↓
    pydantic-settings loads
         ↓
    Settings object
         ↓
    config.json overrides (runtime)
         ↓
    Final runtime config
```

## Error Handling Philosophy

1. **Fail gracefully**: Log errors, notify user, continue running
2. **Safety first**: Always stop pump on any error
3. **Self-healing**: Scheduler retries failed tasks
4. **Visibility**: Send Telegram alerts for critical issues

## Testing Strategy

| Level | Scope | Hardware | Speed |
|-------|-------|----------|-------|
| Unit | Single function/class | MockGpio | Fast |
| Integration | Multiple components | MockGpio + real DB | Medium |
| Hardware | Full system | RealGpio on Pi | Slow |

## Common Patterns

### Dependency Injection

```python
container = Container(
    settings=settings,
    gpio=create_gpio(settings.gpio, mock_mode=True),
    sensors=SensorManager(gpio, settings),
    pump=PumpController(gpio, settings),
    ...
)
```

### Async Context Management

```python
async def run_app(container: Container) -> None:
    try:
        await container.telegram_bot.start()
        await container.shutdown_event.wait()
    finally:
        await container.telegram_bot.stop()
        await container.pump.emergency_stop()
```

### Hardware Abstraction

```python
class GpioInterface(ABC):
    @abstractmethod
    async def read_adc_channel(self, channel: int) -> int: ...
    @abstractmethod
    async def set_relay(self, state: bool) -> None: ...

# Real implementation for Pi, Mock for development
gpio = create_gpio(settings, mock_mode=not_on_pi)
```

## Version Information

- **Python**: 3.11+
- **python-telegram-bot**: 21.x
- **Pydantic**: 2.x
- **pytest-asyncio**: 0.23+
- **Package Manager**: uv

## External APIs

| Service | Purpose | Rate Limit |
|---------|---------|------------|
| Telegram Bot API | User interface, notifications | 30 msg/sec |
| OpenWeather API | Sunset times, rain forecast | 60 calls/min (free tier) |

## GPIO Pin Assignments

| Pin | BCM | Function |
|-----|-----|----------|
| 11 | GPIO17 | Pump Relay |
| 16 | GPIO23 | Ultrasonic Trigger |
| 18 | GPIO24 | Ultrasonic Echo (via voltage divider!) |
| 19 | GPIO10 | SPI MOSI (to MCP3008) |
| 21 | GPIO9 | SPI MISO (from MCP3008) |
| 23 | GPIO11 | SPI SCLK |
| 24 | GPIO8 | SPI CE0 (MCP3008 chip select) |
