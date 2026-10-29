"""Thin wrapper over rapidocr-onnxruntime: page image -> (text, confidence).

The ONNX models ship inside the wheel, so this runs fully offline. The engine
is built once per process and cached (mirrors the lazy-client pattern used by
the cloud agents)."""

import importlib.metadata

from agent1_offline.utils.text_cleaner import clean_text


class OcrUnavailableError(Exception):
    """Raised when the RapidOCR engine cannot be built (import or construction
    failure)."""


class OcrError(Exception):
    """Raised when a built RapidOCR engine fails during inference."""


try:
    RAPIDOCR_VERSION = "rapidocr-onnxruntime==" + importlib.metadata.version(
        "rapidocr-onnxruntime"
    )
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    RAPIDOCR_VERSION = "unknown"

_engine = None


def get_engine():
    """Build and cache the RapidOCR engine on first use. Raises
    OcrUnavailableError if the engine cannot be built for any reason (missing
    package, or failure while constructing it)."""
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR

            _engine = RapidOCR()
        except Exception as exc:  # pragma: no cover
            raise OcrUnavailableError(str(exc)) from exc
    return _engine


def ocr_image(image) -> tuple[str, float | None]:
    """Run OCR on an RGB numpy image. Returns (cleaned_text, mean_confidence);
    ("", None) when nothing is detected.

    RapidOCR returns (result, elapse) where result is a list of
    [box, text, confidence] entries, or None when no text is found."""
    engine = get_engine()
    try:
        result, _elapse = engine(image)
    except Exception as exc:
        raise OcrError(str(exc)) from exc
    if not result:
        return "", None

    texts = [entry[1] for entry in result if entry and len(entry) >= 2]
    confidences = [
        float(entry[2]) for entry in result if entry and len(entry) >= 3
    ]
    text = clean_text("\n".join(texts))
    if not text:
        return "", None
    mean_conf = sum(confidences) / len(confidences) if confidences else None
    return text, mean_conf
