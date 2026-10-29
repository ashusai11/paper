# Offline Agent 1 — Air-Gapped Document Parser

Fully offline document parser. Extracts a document's original content to
Markdown + JSON with per-page provenance. No network, no LLM, no API keys.

## Stack

- [Firecrawl AnyDoc](https://github.com/firecrawl/anydoc) (`firecrawl-anydoc`) — documents → GitHub-Flavored Markdown, fully local.
- [RapidOCR](https://github.com/RapidAI/RapidOCR) (`rapidocr-onnxruntime`) — OCR for scanned pages; ONNX models are bundled in the wheel, so no model download.
- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) — PDF page splitting, page-object inspection, and rasterization.

## Install

```bash
uv venv .venv
uv pip install -r requirements.txt
```

## Usage

CLI:

```bash
.venv/bin/python -m agent1_offline.main path/to/document.pdf --output-dir output
```

Python:

```python
from agent1_offline.main import parse_document

result = parse_document("path/to/document.pdf", output_dir="output")
```

Writes `output/<stem>.md` and `output/<stem>.json`.

## How PDFs are handled

Each PDF page is classified using multiple signals (native text length **and**
image-area coverage), so a sparse page such as a signature page is not mistaken
for a scanned one:

- **native_text** → converted by AnyDoc.
- **scanned** → rasterized and OCR'd by RapidOCR.
- **empty** → recorded with empty text.

Non-PDF formats (docx, xlsx, pptx, csv, rtf, epub, odt, …) are converted whole
by AnyDoc as a single native page.

Format detection is content-first with extension fallback: content detection
handles files with magic bytes (even under a wrong extension), and the
extension resolves signature-less formats such as CSV.

## Output

See `agent1_offline/schemas/parsed_document.schema.json` for the JSON contract.
Each page records `extraction_method` (`native`/`rapidocr`), `is_scanned`,
`ocr_confidence`, `char_count`, and `text`, so downstream consumers know
whether a fact came from native text or OCR. `full_markdown` holds the same
Markdown written to the `.md` file, with per-page provenance comments.

## Scope

This agent preserves original content only. Structured supplier-field
extraction and vector-store ingestion (Agent 2) are intentionally out of scope.
