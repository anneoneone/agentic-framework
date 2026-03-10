"""
spec-to-test CLI — convert a PDF test specification to pytest files.

Usage:
    spec-to-test path/to/spec.pdf --adapter ocpp --out ./tests/generated/
    spec-to-test path/to/spec.pdf --dry-run   # extract + model only, no files written
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click

logger = logging.getLogger(__name__)


@click.command()
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--adapter", default="ocpp", show_default=True,
              help="Spec adapter to use. Available: ocpp")
@click.option("--out", default="./tests/generated/", show_default=True,
              help="Output directory for generated pytest files.")
@click.option("--llm-model", default="claude-sonnet-4-6", show_default=True,
              help="Anthropic model ID for LLM extraction.")
@click.option("--parallel/--no-parallel", default=True, show_default=True,
              help="Use async parallel extraction (recommended for large specs).")
@click.option("--dry-run", is_flag=True,
              help="Extract and model only — skip code generation. Prints SpecDocument summary.")
@click.option("--verbose", "-v", is_flag=True,
              help="Enable debug logging.")
@click.option("--cache-ir", default=None, type=click.Path(),
              help="Path to write/read cached SpecDocument JSON (skip re-extraction if exists).")
def main(
    pdf_path: str,
    adapter: str,
    out: str,
    llm_model: str,
    parallel: bool,
    dry_run: bool,
    verbose: bool,
    cache_ir: str | None,
) -> None:
    """
    Generate pytest test files from a PDF test-specification document.

    PDF_PATH is the path to the specification PDF (e.g. OCPP-2.0.1 Part 6).
    """
    _setup_logging(verbose)

    # --- Imports deferred to avoid heavy startup cost on --help ---
    import anthropic

    from spec_to_test.adapters.registry import get_adapter, list_adapters
    from spec_to_test.extractors.pipeline import PdfExtractionPipeline
    from spec_to_test.generators.fixture_gen import FixtureGenerator
    from spec_to_test.generators.pytest_gen import PytestGenerator
    from spec_to_test.generators.qa import SemanticQA
    from spec_to_test.ir.mapper import RawToIRMapper
    from spec_to_test.llm.extractor import LLMExtractor
    from spec_to_test.llm.schema_retriever import SchemaRetriever
    from spec_to_test.models.spec import SpecDocument

    # 1. Resolve adapter
    try:
        spec_adapter = get_adapter(adapter)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        click.echo(f"Available adapters: {', '.join(list_adapters())}", err=True)
        sys.exit(1)

    click.echo(
        f"spec-to-test | adapter={spec_adapter.spec_id} {spec_adapter.spec_version} "
        f"| model={llm_model} | parallel={'on' if parallel else 'off'}"
    )

    # 2. Try loading cached IR
    spec_doc: SpecDocument | None = None
    if cache_ir and Path(cache_ir).exists():
        click.echo(f"Loading cached IR from {cache_ir} …")
        spec_doc = SpecDocument.model_validate_json(Path(cache_ir).read_text())
        click.echo(spec_doc.summary())

    if spec_doc is None:
        # 3. Extract sections from PDF
        click.echo(f"Extracting sections from {pdf_path} …")
        extractor = PdfExtractionPipeline()
        chunks = extractor.extract(pdf_path, spec_adapter)
        click.echo(f"  → {len(chunks)} sections detected")

        # 4. Map to IR via LLM (parallel async or sequential sync)
        click.echo(f"Mapping to IR via LLM {'(parallel)' if parallel else '(sequential)'} …")
        if parallel:
            anth_client = anthropic.AsyncAnthropic()
        else:
            anth_client = anthropic.Anthropic()
        llm_extractor = LLMExtractor(client=anth_client, model=llm_model)
        retriever = SchemaRetriever(adapter=spec_adapter)
        mapper = RawToIRMapper(
            adapter=spec_adapter,
            extractor=llm_extractor,
            retriever=retriever,
        )
        if parallel:
            spec_doc = asyncio.run(mapper.map_async(chunks))
        else:
            spec_doc = mapper.map(chunks)
        spec_doc.source_pdf = pdf_path
        click.echo(f"  → {spec_doc.summary()}")

        # Optionally cache the IR
        if cache_ir:
            Path(cache_ir).write_text(
                spec_doc.model_dump_json(indent=2), encoding="utf-8"
            )
            click.echo(f"  → IR cached to {cache_ir}")

    if dry_run:
        click.echo("\n--dry-run: skipping code generation.")
        click.echo(spec_doc.summary())
        if spec_doc.failed_chunk_ids:
            click.echo(
                f"⚠️  Failed chunks: {', '.join(spec_doc.failed_chunk_ids)}", err=True
            )
        return

    # 5. Generate pytest files
    out_path = Path(out)
    click.echo(f"Generating pytest files to {out_path} …")

    fixture_gen = FixtureGenerator(output_dir=out_path)
    conftest_path = fixture_gen.generate(spec_doc)
    click.echo(f"  → {conftest_path.name}")

    test_gen = PytestGenerator(output_dir=out_path)
    test_files = test_gen.generate(spec_doc)
    for f in test_files:
        click.echo(f"  → {f.name}")

    # 6. Semantic QA
    click.echo("Running semantic QA …")
    chunk_index = {}
    # Re-extract chunks only if we need them for QA (avoid double parsing)
    # If cached, we don't have chunks — skip QA gracefully
    if spec_doc.source_pdf:
        try:
            chunks_for_qa = PdfExtractionPipeline().extract(
                spec_doc.source_pdf, spec_adapter
            )
            chunk_index = {c["id"]: c["markdown"] for c in chunks_for_qa}
        except Exception as exc:
            logger.warning("Could not re-extract chunks for QA: %s", exc)

    qa = SemanticQA()
    qa_report_path = out_path / "qa_report.json"
    results = qa.run(test_files, chunk_index, output_path=qa_report_path)

    flagged = [r for r in results if r.flagged]
    if flagged:
        click.echo(
            f"\n⚠️  QA: {len(flagged)}/{len(results)} tests flagged "
            f"(similarity < {qa._threshold}). See {qa_report_path}",
            err=True,
        )
    else:
        click.echo(f"  → QA passed: all {len(results)} tests above threshold")

    click.echo("\nDone.")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        format="%(levelname)s %(name)s: %(message)s",
        level=level,
    )
