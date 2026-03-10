"""
PytestGenerator — renders TestCases into pytest test modules.

One output file per test-case group (grouped by TC category letter: TC_B*, TC_C*, etc.).
Each file begins with the AUTO-GENERATED header.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from spec_to_test.models.spec import SpecDocument
from spec_to_test.models.testcase import TestCase

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_TC_CATEGORY_RE = re.compile(r"TC_([A-Z])\d+", re.IGNORECASE)


class PytestGenerator:
    """
    Converts a SpecDocument into pytest test files.

    Args:
        output_dir: Directory where generated .py files are written.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, spec_doc: SpecDocument) -> list[Path]:
        """
        Render all test cases and return list of written file paths.

        Groups test cases by category letter (TC_B → test_tc_b.py, etc.).
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        groups = self._group_by_category(spec_doc.test_cases)
        written: list[Path] = []

        for category, test_cases in groups.items():
            path = self._render_group(
                category=category,
                test_cases=test_cases,
                spec_doc=spec_doc,
            )
            written.append(path)
            logger.info("Wrote %s (%d tests)", path.name, len(test_cases))

        return written

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _group_by_category(
        self, test_cases: list[TestCase]
    ) -> dict[str, list[TestCase]]:
        groups: dict[str, list[TestCase]] = {}
        for tc in test_cases:
            m = _TC_CATEGORY_RE.search(tc.id)
            category = m.group(1).upper() if m else "misc"
            groups.setdefault(category, []).append(tc)
        return groups

    def _render_group(
        self,
        category: str,
        test_cases: list[TestCase],
        spec_doc: SpecDocument,
    ) -> Path:
        template = self._env.get_template("test_module.py.j2")
        low_confidence_ids = [tc.id for tc in test_cases if tc.low_confidence]

        # Collect reusable state refs used in this group
        state_refs: set[str] = set()
        for tc in test_cases:
            for pre in tc.preconditions:
                if pre.reusable_state_ref:
                    state_refs.add(pre.reusable_state_ref)

        content = template.render(
            spec_id=spec_doc.spec_id,
            spec_version=spec_doc.spec_version,
            generated_at=datetime.now(timezone.utc).isoformat(),
            test_cases=test_cases,
            low_confidence_ids=low_confidence_ids,
            reusable_state_ids=sorted(state_refs),
        )

        filename = f"test_tc_{category.lower()}.py"
        path = self._output_dir / filename
        path.write_text(content, encoding="utf-8")
        return path
