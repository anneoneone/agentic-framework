# spec-to-test

Agent stack for the `spec-to-test` project — a PDF test-specification to pytest code generator.

## What it does

Converts structured PDF test specifications (like OCPP 2.0.1 Part 6) into runnable Python pytest files.

**Input**: A ~500-page PDF describing datatypes, test cases, and reusable states
**Output**: `conftest.py` + pytest test modules, ready to run

## Pipeline

```
PDF → Extract → Model (IR) → Generate → pytest files
```

| Stage | Agent | Key library |
|-------|-------|------------|
| PDF extraction | @pdf-extractor | pdfplumber, pypdf |
| IR modeling | @ir-modeler | Pydantic v2 |
| Code generation | @pytest-generator | Jinja2 |
| Spec-specific rules | @spec-adapter | (pure Python) |

## Agents

| Agent | Role |
|-------|------|
| `@pdf-extractor` | PDF parsing, section detection, table extraction |
| `@ir-modeler` | Maps raw extractions to typed Pydantic IR models |
| `@pytest-generator` | Generates pytest files from IR using Jinja2 templates |
| `@spec-adapter` | Pluggable adapter for spec-specific patterns and vocabulary |
| `@coordinator` | Task routing and plan execution |
| `@planner` | Creates JSON execution plans |
| `@gitlab` | Git commits and MR creation |

## Supported Specs

- **OCPP 2.0.1 Part 6** — Test Cases & Examples (first supported spec)
- Generic adapter interface for future specs

## Project Structure (planned)

```
src/
  extractors/    # pdf-extractor domain
  models/        # ir-modeler domain
  generators/    # pytest-generator domain
  adapters/      # spec-adapter domain
  cli.py
tests/
pyproject.toml
```

## Usage (planned)

```bash
spec-to-test OCPP-2.0.1_part6.pdf --adapter ocpp --out ./tests/
```

## Knowledge

See [docs/knowledge/index.md](docs/knowledge/index.md) for architecture decisions and learnings.
