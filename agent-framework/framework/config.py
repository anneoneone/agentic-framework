"""Agent Framework configuration loader.

Loads configuration from (in priority order):
1. Environment variables (ANTHROPIC_API_KEY, ANTHROPIC_MODEL)
2. Project-level config.json (framework/config.json)
3. Built-in defaults
"""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Defaults
DEFAULT_MODEL = "claude-opus-4-20250115"
DEFAULT_AGENT_DIRS = ["agents"]
DEFAULT_BATCH_TIMEOUT = 60
DEFAULT_MAX_TOKENS = 8192


@dataclass
class BatchConfig:
    """Batch API configuration."""
    enabled: bool = True
    timeout_minutes: int = DEFAULT_BATCH_TIMEOUT
    poll_interval_seconds: int = 30


@dataclass
class MCPServerConfig:
    """MCP server paths (relative to framework root)."""
    agent_registry: str = "framework/mcp-servers/agent-registry"
    knowledge_search: str = "framework/mcp-servers/knowledge-search"
    plan_execution: str = "framework/mcp-servers/plan-execution"


@dataclass
class Config:
    """Agent Framework configuration."""
    api_key: str = ""
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    agent_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_AGENT_DIRS))
    batch: BatchConfig = field(default_factory=BatchConfig)
    mcp_servers: MCPServerConfig = field(default_factory=MCPServerConfig)
    root_path: Path = field(default_factory=lambda: Path("."))

    @property
    def is_valid(self) -> bool:
        """Check if config has minimum required settings."""
        return bool(self.api_key)

    def validate(self) -> list[str]:
        """Return list of validation errors."""
        errors = []
        if not self.api_key:
            errors.append("ANTHROPIC_API_KEY not set. Export it or add to config.json.")
        if not self.root_path.exists():
            errors.append(f"Root path does not exist: {self.root_path}")
        return errors


def find_root() -> Path:
    """Find the agent-framework root directory.

    Walks up from this file's location to find the directory containing
    'framework/' and 'stacks/'.
    """
    current = Path(__file__).resolve().parent
    # config.py is at framework/config.py, so parent is framework/, parent.parent is root
    root = current.parent
    if (root / "framework").is_dir() and (root / "stacks").is_dir():
        return root

    # Fallback: walk up from cwd
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "framework").is_dir() and (parent / "stacks").is_dir():
            return parent

    return cwd


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from file + environment.

    Args:
        config_path: Explicit path to config.json. If None, auto-detect.

    Returns:
        Populated Config object.
    """
    root = find_root()
    config = Config(root_path=root)

    # Load config file
    if config_path is None:
        config_path = root / "framework" / "config.json"

    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read {config_path}: {e}", file=sys.stderr)
            data = {}

        if "model" in data:
            config.model = data["model"]
        if "max_tokens" in data:
            config.max_tokens = data["max_tokens"]
        if "agent_dirs" in data:
            config.agent_dirs = data["agent_dirs"]
        if "api_key" in data:
            config.api_key = data["api_key"]

        if "batch_api" in data:
            batch = data["batch_api"]
            config.batch.enabled = batch.get("enabled", True)
            config.batch.timeout_minutes = batch.get("timeout_minutes", DEFAULT_BATCH_TIMEOUT)
            config.batch.poll_interval_seconds = batch.get("poll_interval_seconds", 30)

        if "mcp_servers" in data:
            mcp = data["mcp_servers"]
            if "agent-registry" in mcp:
                config.mcp_servers.agent_registry = mcp["agent-registry"]
            if "knowledge-search" in mcp:
                config.mcp_servers.knowledge_search = mcp["knowledge-search"]
            if "plan-execution" in mcp:
                config.mcp_servers.plan_execution = mcp["plan-execution"]

    # Environment overrides (highest priority)
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_key:
        config.api_key = env_key

    env_model = os.environ.get("ANTHROPIC_MODEL", "")
    if env_model:
        config.model = env_model

    env_max_tokens = os.environ.get("ANTHROPIC_MAX_TOKENS", "")
    if env_max_tokens:
        try:
            config.max_tokens = int(env_max_tokens)
        except ValueError:
            pass

    return config


def resolve_agent_dirs(config: Config) -> list[Path]:
    """Resolve agent directory paths relative to root."""
    dirs = []
    for d in config.agent_dirs:
        path = config.root_path / d if not Path(d).is_absolute() else Path(d)
        dirs.append(path)
    return dirs


if __name__ == "__main__":
    cfg = load_config()
    errors = cfg.validate()
    if errors:
        print("Configuration errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"Root:       {cfg.root_path}")
        print(f"Model:      {cfg.model}")
        print(f"Max tokens: {cfg.max_tokens}")
        print(f"Agent dirs: {cfg.agent_dirs}")
        print(f"API key:    {'***' + cfg.api_key[-4:] if len(cfg.api_key) > 4 else '(not set)'}")
        print(f"Batch API:  {'enabled' if cfg.batch.enabled else 'disabled'}")
