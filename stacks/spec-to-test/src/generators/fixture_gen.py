"""
FixtureGenerator — renders ReusableStates into conftest.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from spec_to_test.models.spec import SpecDocument

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class FixtureGenerator:
    """
    Converts ReusableState objects into a pytest conftest.py.

    Args:
        output_dir: Directory where conftest.py is written.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, spec_doc: SpecDocument) -> Path:
        """Render conftest.py and return its path."""
        self._output_dir.mkdir(parents=True, exist_ok=True)

        template = self._env.get_template("conftest.py.j2")
        content = template.render(
            spec_id=spec_doc.spec_id,
            spec_version=spec_doc.spec_version,
            generated_at=datetime.now(timezone.utc).isoformat(),
            reusable_states=spec_doc.reusable_states,
        )

        path = self._output_dir / "conftest.py"
        path.write_text(content, encoding="utf-8")
        logger.info(
            "Wrote conftest.py (%d fixtures)", len(spec_doc.reusable_states)
        )
        return path
