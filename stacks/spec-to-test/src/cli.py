"""
spec-to-test CLI — convert a PDF test specification to pytest files.

Extraction modes (choose one):
  default           asyncio parallel real-time API  (fastest wall-clock, full price)
  --no-parallel     sequential real-time API         (slowest, full price, simple)
  --batch           Anthropic Batch API              (50% cost, async, ≤24h)
  --batch --no-wait submit batch only, exit          (non-blocking CI integration)

Caching:
  --cache-ir PATH   save/restore SpecDocument JSON   (skip re-extraction entirely)
  --extraction-cache DIR  chunk-level LLM cache       (skip individual LLM calls)
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click

logger = logging.getLogger(__name__)


@click.command()
@click.argument("pdf_path", required=False,
                type=click.Path(exists=True, dir_okay=False))
@click.option("--adapter", default="ocpp", show_default=True,
              help="Spec adapter. Available: ocpp")
@click.option("--out", default="./tests/generated/", show_default=True,
              help="Output directory for generated pytest files.")
@click.option("--llm-model", default="claude-sonnet-4-6", show_default=True,
              help="Anthropic model ID for LLM extraction.")
@click.option("--parallel/--no-parallel", default=True, show_default=True,
              help="Async parallel extraction (ignored when --batch is set).")
@click.option("--batch", is_flag=True,
              help="Use Anthropic Batch API (50%% cost, async). Implies --no-parallel.")
@click.option("--no-wait", is_flag=True,
              help="With --batch: submit and exit immediately (print batch_id).")
@click.option("--collect", default=None, metavar="BATCH_ID",
              help="Collect a previously submitted batch by ID, then generate code.")
@click.option("--dry-run", is_flag=True,
              help="Extract + model only — skip code generation.")
@click.option("--verbose", "-v", is_flag=True, help="Debug logging.")
@click.option("--cache-ir", default=None, type=click.Path(),
              help="Path to write/read SpecDocument JSON (skip re-extraction if exists).")
@click.option("--extraction-cache", default=None, type=click.Path(),
              help="Directory for chunk-level extraction cache (skip individual LLM calls).")
def main(
    pdf_path: str | None,
    adapter: str,
    out: str,
    llm_model: str,
    parallel: bool,
    batch: bool,
    no_wait: bool,
    collect: str | None,
    dry_run: bool,
    verbose: bool,
    cache_ir: str | None,
    extraction_cache: str | None,
) -> None:
    """
    Generate pytest test files from a PDF test-specification document.

    PDF_PATH is required unless --collect is used to retrieve a prior batch.
    """
    _setup_logging(verbose)

    import anthropic

    from spec_to_test.adapters.registry import get_adapter, list_adapters
    from spec_to_test.extractors.pipeline import PdfExtractionPipeline
    from spec_to_test.generators.fixture_gen import FixtureGenerator
    from spec_to_test.generators.pytest_gen import PytestGenerator
    from spec_to_test.generators.qa import SemanticQA
    from spec_to_test.ir.mapper import RawToIRMapper
    from spec_to_test.llm.batch_extractor import BatchExtractor
    from spec_to_test.llm.extraction_cache import ExtractionCache
    from spec_to_test.llm.extractor import LLMExtractor
    from spec_to_test.llm.schema_retriever import SchemaRetriever
    from spec_to_test.models.spec import SpecDocument

    # --collect requires no pdf_path
    if collect and pdf_path is None:
        pdf_path = ""  # will be loaded from cache_ir or batch state
    elif pdf_path is None:
        raise click.UsageError("PDF_PATH is required (or use --collect BATCH_ID)")

    # 1. Resolve adapter
    try:
        spec_adapter = get_adapter(adapter)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        click.echo(f"Available adapters: {', '.join(list_adapters())}", err=True)
        sys.exit(1)

    mode = "batch" if batch else ("parallel" if parallel else "sequential")
    click.echo(
        f"spec-to-test | adapter={spec_adapter.spec_id} {spec_adapter.spec_version} "
        f"| model={llm_model} | mode={mode}"
    )

    # 2. Build extraction cache (optional)
    ext_cache: ExtractionCache | None = None
    if extraction_cache:
        ext_cache = ExtractionCache(cache_dir=extraction_cache, model_id=llm_model)
        click.echo(f"  Extraction cache: {ext_cache.size()} entries loaded")

    # 3. Try loading cached SpecDocument IR
    spec_doc: SpecDocument | None = None
    if cache_ir and Path(cache_ir).exists():
        click.echo(f"Loading cached IR from {cache_ir} …")
        spec_doc = SpecDocument.model_validate_json(Path(cache_ir).read_text())
        click.echo(spec_doc.summary())

    chunks = []

    if spec_doc is None:
        # 4. Extract PDF sections
        if not pdf_path:
            raise click.UsageError("PDF_PATH required when no cached IR exists")
        click.echo(f"Extracting sections from {pdf_path} …")
        chunks = PdfExtractionPipeline().extract(pdf_path, spec_adapter)
        click.echo(f"  → {len(chunks)} sections detected")

        retriever = SchemaRetriever(adapter=spec_adapter)

        # ----------------------------------------------------------- #
        # BATCH MODE                                                    #
        # ----------------------------------------------------------- #
        if batch or collect:
            sync_client = anthropic.Anthropic()
            batch_ext = BatchExtractor(
                client=sync_client,
                model=llm_model,
                cache=ext_cache,
            )

            if collect:
                # Collect a previously submitted batch
                batch_id = collect
                click.echo(f"Collecting batch {batch_id} …")
            else:
                # Submit new batch
                batch_id = batch_ext.submit(chunks, retriever)
                if not batch_id:
                    click.echo("All chunks served from cache — skipping batch.")
                elif no_wait:
                    click.echo(
                        f"\nBatch submitted: {batch_id}\n"
                        f"Retrieve results with:\n"
                        f"  spec-to-test {pdf_path} --collect {batch_id} "
                        f"--cache-ir {cache_ir or '/tmp/ir.json'}"
                    )
                    return

            if batch_id:
                click.echo("Waiting for batch results (polls every 30s) …")
                test_cases, failed_ids = batch_ext.wait_and_collect(batch_id, chunks)
            else:
                test_cases, failed_ids = batch_ext.collect("", chunks)

            # Assemble SpecDocument from batch results + rule-based RS extraction
            from spec_to_test.ir.mapper import RawToIRMapper
            mapper = RawToIRMapper(
                adapter=spec_adapter,
                extractor=None,  # type: ignore[arg-type]
                retriever=retriever,
            )
            spec_doc = mapper._empty_doc(len(chunks))
            spec_doc.test_cases = test_cases
            spec_doc.failed_chunk_ids = failed_ids
            spec_doc.low_confidence_count = sum(
                1 for tc in test_cases if tc.low_confidence
            )
            for chunk in chunks:
                if chunk["section_type"] == "reusable_state":
                    spec_doc.reusable_states.append(
                        mapper._extract_reusable_state(chunk)
                    )

        # ----------------------------------------------------------- #
        # REAL-TIME MODE (parallel or sequential)                      #
        # ----------------------------------------------------------- #
        else:
            if parallel:
                anth_client = anthropic.AsyncAnthropic()
            else:
                anth_client = anthropic.Anthropic()

            llm_extractor = LLMExtractor(client=anth_client, model=llm_model)

            # Wrap extractor with cache if provided
            if ext_cache:
                llm_extractor = _CachedExtractor(llm_extractor, ext_cache)  # type: ignore[assignment]

            mapper = RawToIRMapper(
                adapter=spec_adapter,
                extractor=llm_extractor,
                retriever=retriever,
            )
            click.echo(f"Mapping to IR via LLM ({mode}) …")
            if parallel:
                spec_doc = asyncio.run(mapper.map_async(chunks))
            else:
                spec_doc = mapper.map(chunks)

        spec_doc.source_pdf = pdf_path or ""
        click.echo(f"  → {spec_doc.summary()}")

        if cache_ir:
            Path(cache_ir).write_text(
                spec_doc.model_dump_json(indent=2), encoding="utf-8"
            )
            click.echo(f"  → IR cached to {cache_ir}")

    if dry_run:
        click.echo("\n--dry-run: skipping code generation.")
        click.echo(spec_doc.summary())
        if spec_doc.failed_chunk_ids:
            click.echo(f"⚠️  Failed: {', '.join(spec_doc.failed_chunk_ids)}", err=True)
        return

    # 5. Generate pytest files
    out_path = Path(out)
    click.echo(f"Generating pytest files to {out_path} …")

    conftest_path = FixtureGenerator(output_dir=out_path).generate(spec_doc)
    click.echo(f"  → {conftest_path.name}")

    test_files = PytestGenerator(output_dir=out_path).generate(spec_doc)
    for f in test_files:
        click.echo(f"  → {f.name}")

    # 6. Semantic QA
    click.echo("Running semantic QA …")
    chunk_index = {}
    if spec_doc.source_pdf:
        try:
            qa_chunks = PdfExtractionPipeline().extract(spec_doc.source_pdf, spec_adapter)
            chunk_index = {c["id"]: c["markdown"] for c in qa_chunks}
        except Exception as exc:
            logger.warning("Could not re-extract chunks for QA: %s", exc)

    qa = SemanticQA()
    qa_report_path = out_path / "qa_report.json"
    results = qa.run(test_files, chunk_index, output_path=qa_report_path)
    flagged = [r for r in results if r.flagged]
    if flagged:
        click.echo(
            f"\n⚠️  QA: {len(flagged)}/{len(results)} flagged. See {qa_report_path}",
            err=True,
        )
    else:
        click.echo(f"  → QA passed: {len(results)} tests")

    click.echo("\nDone.")


# ------------------------------------------------------------------ #
# Cache-wrapping shim for real-time extractor                        #
# ------------------------------------------------------------------ #

class _CachedExtractor:
    """Wraps LLMExtractor to serve cache hits without calling the API."""

    def __init__(self, extractor: LLMExtractor, cache: ExtractionCache) -> None:
        self._extractor = extractor
        self._cache = cache

    def extract(self, chunk, schema_context):
        cached = self._cache.get(chunk["markdown"])
        if cached is not None:
            return cached
        result = self._extractor.extract(chunk, schema_context)
        self._cache.put(chunk["markdown"], result)
        return result

    async def extract_async(self, chunk, schema_context):
        cached = self._cache.get(chunk["markdown"])
        if cached is not None:
            return cached
        result = await self._extractor.extract_async(chunk, schema_context)
        self._cache.put(chunk["markdown"], result)
        return result


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s", level=level)
