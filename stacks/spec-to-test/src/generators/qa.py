"""
SemanticQA — validates generated tests against source spec sections.

For each generated test, computes cosine similarity between:
  - the test function's docstring (what was generated)
  - the source SectionChunk.markdown (what the spec says)

Tests with similarity < SIMILARITY_THRESHOLD are flagged in qa_report.json
for human review. This catches cases where the LLM extracted something
semantically different from the source.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70
MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass
class QAResult:
    test_id: str
    test_file: str
    similarity: float
    flagged: bool
    source_chunk_id: str
    reason: str = ""


class SemanticQA:
    """
    Computes semantic similarity between generated tests and source spec chunks.

    Args:
        threshold: Cosine similarity threshold below which a test is flagged.
    """

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD) -> None:
        self._threshold = threshold
        self._model = None  # lazy-loaded on first use

    def run(
        self,
        test_files: list[Path],
        chunk_index: dict[str, str],   # chunk_id → markdown
        output_path: Optional[Path] = None,
    ) -> list[QAResult]:
        """
        Run QA over all generated test files.

        Args:
            test_files:  Paths to generated .py files.
            chunk_index: Mapping from SectionChunk.id → markdown text.
            output_path: Where to write qa_report.json (optional).

        Returns:
            List of QAResult objects (all tests, flagged and passing).
        """
        self._ensure_model()
        results: list[QAResult] = []

        for test_file in test_files:
            file_results = self._check_file(test_file, chunk_index)
            results.extend(file_results)

        if output_path:
            self._write_report(results, output_path)

        flagged = [r for r in results if r.flagged]
        logger.info(
            "SemanticQA: %d tests checked, %d flagged (threshold=%.2f)",
            len(results), len(flagged), self._threshold,
        )
        return results

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(MODEL_NAME)
            logger.debug("Loaded sentence-transformers model: %s", MODEL_NAME)
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for QA. "
                "Install: pip install sentence-transformers"
            ) from exc

    def _check_file(
        self,
        test_file: Path,
        chunk_index: dict[str, str],
    ) -> list[QAResult]:
        source = test_file.read_text(encoding="utf-8")
        results: list[QAResult] = []

        for func_name, docstring, chunk_id in self._extract_test_functions(source):
            chunk_md = chunk_index.get(chunk_id, "")
            if not chunk_md:
                results.append(QAResult(
                    test_id=func_name,
                    test_file=test_file.name,
                    similarity=0.0,
                    flagged=True,
                    source_chunk_id=chunk_id,
                    reason="source chunk not found in index",
                ))
                continue

            sim = self._cosine_similarity(docstring, chunk_md)
            results.append(QAResult(
                test_id=func_name,
                test_file=test_file.name,
                similarity=round(sim, 4),
                flagged=sim < self._threshold,
                source_chunk_id=chunk_id,
                reason="similarity below threshold" if sim < self._threshold else "",
            ))

        return results

    def _extract_test_functions(
        self, source: str
    ) -> list[tuple[str, str, str]]:
        """
        Extract (function_name, docstring, chunk_id) from generated Python source.

        chunk_id is parsed from the 'Source: <chunk_id>' line in the docstring.
        """
        import re
        results = []
        func_re = re.compile(
            r"async def (test_\w+)\([^)]*\):\s+\"\"\"(.*?)\"\"\"\s",
            re.DOTALL,
        )
        for m in func_re.finditer(source):
            func_name = m.group(1)
            docstring = m.group(2).strip()

            # Extract chunk_id from "Source: TC_B01 ..." line
            source_match = re.search(r"Source:\s+(\S+)", docstring)
            chunk_id = source_match.group(1) if source_match else ""

            results.append((func_name, docstring, chunk_id))
        return results

    def _cosine_similarity(self, text_a: str, text_b: str) -> float:
        import numpy as np
        embeddings = self._model.encode([text_a, text_b])
        a, b = embeddings[0], embeddings[1]
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm == 0:
            return 0.0
        return float(np.dot(a, b) / norm)

    def _write_report(
        self,
        results: list[QAResult],
        output_path: Path,
    ) -> None:
        flagged = [r for r in results if r.flagged]
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_tests": len(results),
            "flagged_count": len(flagged),
            "threshold": self._threshold,
            "flagged": [asdict(r) for r in flagged],
            "all_results": [asdict(r) for r in results],
        }
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info("QA report written: %s", output_path)
