"""Offline Agent 1 orchestrator.

Extracts a document's original content to Markdown + JSON with per-page
provenance, fully offline. PDFs are split per page (pypdfium2); native pages
go through AnyDoc, scanned pages through RapidOCR. Non-PDF formats go through
AnyDoc whole-file as a single native page.
"""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium

from agent1_offline import __version__
from agent1_offline.processors import anydoc_processor, rapidocr_processor
from agent1_offline.processors.anydoc_processor import AnyDocError
from agent1_offline.processors.rapidocr_processor import OcrError, OcrUnavailableError
from agent1_offline.utils import file_detector, page_detector

OCR_RENDER_SCALE = 2.0


def _provenance_comment(page_num: int, method: str, is_scanned: bool) -> str:
    label = f"{method} (scanned)" if is_scanned else method
    return f"<!-- page {page_num} | {label} -->"


def _single_page_pdf_bytes(src: "pdfium.PdfDocument", index: int) -> bytes:
    out = pdfium.PdfDocument.new()
    out.import_pages(src, [index])
    buf = io.BytesIO()
    out.save(buf)
    return buf.getvalue()


def _ocr_page(page) -> tuple[str, float | None]:
    bitmap = page.render(scale=OCR_RENDER_SCALE)
    image = np.asarray(bitmap.to_pil().convert("RGB"))
    return rapidocr_processor.ocr_image(image)


def _process_pdf(data: bytes) -> list[dict]:
    src = pdfium.PdfDocument(data)
    pages: list[dict] = []
    for index in range(len(src)):
        page = src[index]
        page_num = index + 1
        page_type = page_detector.classify_page(page)

        entry = {
            "page": page_num,
            "extraction_method": "native",
            "is_scanned": False,
            "char_count": 0,
            "ocr_confidence": None,
            "text": "",
            "error": None,
        }

        if page_type == "native_text":
            try:
                text = anydoc_processor.markdown_from_bytes(
                    _single_page_pdf_bytes(src, index), file_detector.PDF_FORMAT
                )
                entry["text"] = text
            except AnyDocError as exc:
                entry["error"] = f"anydoc: {exc}"
        elif page_type == "scanned":
            entry["extraction_method"] = "rapidocr"
            entry["is_scanned"] = True
            try:
                text, conf = _ocr_page(page)
                entry["text"] = text
                entry["ocr_confidence"] = conf
            except OcrUnavailableError as exc:
                entry["error"] = f"ocr_unavailable: {exc}"
            except OcrError as exc:
                entry["error"] = f"ocr_error: {exc}"
        # else empty page -> defaults (native, empty text)

        entry["char_count"] = len(entry["text"])
        entry["_page_type"] = page_type  # internal, stripped before output
        pages.append(entry)
    return pages


def _process_non_pdf(path) -> list[dict]:
    entry = {
        "page": 1,
        "extraction_method": "native",
        "is_scanned": False,
        "char_count": 0,
        "ocr_confidence": None,
        "text": "",
        "error": None,
        "_page_type": "native_text",
    }
    try:
        entry["text"] = anydoc_processor.markdown_from_path(path)
    except AnyDocError as exc:
        entry["error"] = f"anydoc: {exc}"
        entry["_page_type"] = "empty"
    entry["char_count"] = len(entry["text"])
    return [entry]


def _build_full_markdown(pages: list[dict]) -> str:
    blocks = []
    for entry in pages:
        comment = _provenance_comment(
            entry["page"], entry["extraction_method"], entry["is_scanned"]
        )
        body = entry["text"].strip()
        blocks.append(f"{comment}\n{body}".rstrip())
    return "\n\n".join(blocks).strip() + "\n"


def _build_stats(pages: list[dict]) -> dict:
    stats = {"native_pages": 0, "scanned_pages": 0, "empty_pages": 0}
    for entry in pages:
        page_type = entry["_page_type"]
        if page_type == "native_text":
            stats["native_pages"] += 1
        elif page_type == "scanned":
            stats["scanned_pages"] += 1
        else:
            stats["empty_pages"] += 1
    return stats


def parse_document(path, output_dir="output") -> dict:
    """Parse a document fully offline into Markdown + JSON.

    Writes <output_dir>/<stem>.md and <output_dir>/<stem>.json, and returns the
    JSON dict (conforming to schemas/parsed_document.schema.json)."""
    path = Path(path)
    print(f"[Agent 1 offline] Parsing: {path}")
    fmt = file_detector.detect_format(path)

    if fmt == file_detector.PDF_FORMAT:
        pages = _process_pdf(path.read_bytes())
    else:
        pages = _process_non_pdf(path)

    stats = _build_stats(pages)
    full_markdown = _build_full_markdown(pages)

    for entry in pages:
        entry.pop("_page_type", None)

    result = {
        "source_file": path.name,
        "format": fmt,
        "parser": {
            "agent": "agent1_offline",
            "anydoc_version": anydoc_processor.ANYDOC_VERSION,
            "rapidocr": rapidocr_processor.RAPIDOCR_VERSION,
        },
        "page_count": len(pages),
        "full_markdown": full_markdown,
        "pages": pages,
        "stats": stats,
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    (out_dir / f"{stem}.md").write_text(full_markdown, encoding="utf-8")
    (out_dir / f"{stem}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(
        f"[Agent 1 offline] Done. format={fmt} pages={len(pages)} "
        f"native={stats['native_pages']} scanned={stats['scanned_pages']} "
        f"empty={stats['empty_pages']} -> {out_dir}/{stem}.(md|json)"
    )
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent1_offline",
        description="Offline (air-gapped) document parser -> Markdown + JSON.",
    )
    parser.add_argument("path", help="Path to the document to parse")
    parser.add_argument(
        "--output-dir", default="output", help="Directory for .md/.json output"
    )
    parser.add_argument("--version", action="version", version=f"agent1_offline {__version__}")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.path):
        print(f"error: file not found: {args.path}")
        return 1

    parse_document(args.path, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
