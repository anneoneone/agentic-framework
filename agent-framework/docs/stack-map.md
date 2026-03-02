# Monorepo Stack Map

Generated: 2026-01-14

## Rust Stack

**Workspace Root**: `appfs/ebee/`  
**Workspace File**: `rust-ebee.code-workspace`

### Projects:
- `charger/` - Main charger application (also has C++ components)
- `cli/` - Command-line interface tools
- `helpers/build-helper/` - Build utilities
- `instrumentation/` - Instrumentation and metrics
- `libebee-error/` - Error handling library
- `libpstore-settings/` - Persistent storage settings library
- `libservice-utils/` - Service utilities
- `libsettings-store/` - Settings storage library
- `ocpp20/` - **OCPP 2.0 implementation** (primary focus)
- `ocsp/` - OCSP certificate validation
- `rauc-helpers/` - RAUC update helpers (also has CMake)
- `service-registry/` - Service registry
- `session/` - Session management
- `settings-store/` - Settings store service (also has CMake)
- `settings/` - Settings library

**Total Rust projects**: 16

## Python Stack

**Workspace Root**: `tests/python/`, `appfs/charger/simulation/`, `doc/`, `helpers/`  
**Workspace File**: `python-test.code-workspace`

### Projects:
- `tests/python/` - **Integration test suite**
- `appfs/charger/simulation/` - Charging simulation tools
- `appfs/web-ui/tools/` - Web UI build tools
- `appfs/libebee-evsim15118/` - EV simulator (ISO 15118)
- `doc/architecture/` - Architecture documentation generation
- `doc/devbook/` - Developer handbook
- `helpers/ebee-cryptomaterial/` - Crypto material generation
- `helpers/release-notes/` - Release notes generator
- `helpers/samba-port-monitor/` - Samba port monitoring

**Total Python projects**: 9

## C++ Stack

**Workspace Root**: `appfs/charger/`, `appfs/libebee-*/`, `appfs/ebee/`  
**Workspace File**: `cpp-firmware.code-workspace`

### Projects:
- `appfs/charger/` - Main charger (C++ core + Rust services)
- `appfs/charger/test/unittests/` - C++ unit tests
- `appfs/libebee-common/` - Common C++ library
- `appfs/libebee-error/` - Error handling (C++)
- `appfs/libebee-hal/` - Hardware abstraction layer
- `appfs/libebee-proto/` - Protobuf definitions
- `appfs/libebee-resources/` - Resource management
- `appfs/libebee-updater/` - Firmware updater
- `appfs/nss-ebee-users/` - NSS user management
- `appfs/system-scripts/` - System scripts
- `appfs/vendor/keo-connectivity/eebus/` - EEBUS integration
- `appfs/vendor/siemens/v2g/` - Vehicle-to-Grid (V2G)
- `appfs/libebee-evsim15118/` - EV simulator (C++)
- `appfs/system-certificates/` - Certificate management
- `appfs/stm32-eo-tools/` - STM32 embedded tools

**Total C++ projects**: 15+

## Documentation Stack

**Workspace Root**: `doc/`  
**Workspace File**: `docs.code-workspace`

### Directories:
- `doc/architecture/` - Architecture docs (Python-based generation)
- `doc/devbook/` - Developer handbook
- Root-level markdown files

## Web UI Stack

**Workspace Root**: `appfs/web-ui/`  
**Workspace File**: `webui.code-workspace`

### Projects:
- `app/wasmutils/` - WASM utilities (Rust)
- `tools/` - Build tools (Python)

## Mixed/Hybrid Projects

Some projects combine multiple languages:

- **charger**: C++ core + Rust services
- **rauc-helpers**: Rust + CMake
- **settings-store**: Rust + CMake
- **libebee-evsim15118**: Python + C++

## Recommended Workspace Structure

1. **rust-ebee.code-workspace** - All Rust projects under `appfs/ebee/`
2. **python-test.code-workspace** - Python testing + simulation
3. **cpp-firmware.code-workspace** - C++ libraries + firmware
4. **docs.code-workspace** - Documentation

## Cross-Stack Dependencies

- **Rust → C++**: FFI through `libebee-proto` (protobuf/gRPC)
- **Python → Rust**: Integration tests call Rust services
- **C++ → Rust**: Legacy charger calls Rust services
- **All → Proto**: Shared protobuf definitions in `libebee-proto`
