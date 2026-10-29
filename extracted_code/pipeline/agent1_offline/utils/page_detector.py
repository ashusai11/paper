"""Per-page classification for PDFs: native_text | scanned | empty.

Uses multiple signals (native text length AND image-area coverage), not text
length alone, so a legitimately sparse page (e.g. a signature page) is not
misread as a scanned page.
"""

import pypdfium2 as pdfium

MIN_TEXT_CHARS = 20
IMAGE_COVER_THRESHOLD = 0.5

_IMAGE_OBJ_TYPE = pdfium.raw.FPDF_PAGEOBJ_IMAGE


def classify(char_count: int, image_coverage: float) -> str:
    """Pure decision logic. Meaningful native text wins first; otherwise a
    large image region means scanned; otherwise empty."""
    if char_count >= MIN_TEXT_CHARS:
        return "native_text"
    if image_coverage >= IMAGE_COVER_THRESHOLD:
        return "scanned"
    return "empty"


def page_signals(page) -> tuple[int, float]:
    """Extract (char_count, image_coverage) from a pypdfium2 page.

    image_coverage is the fraction of the page area covered by image objects,
    clamped to [0.0, 1.0]. Bounding boxes are clamped to the page box before
    their areas are summed."""
    width, height = page.get_size()
    page_area = max(width * height, 1.0)

    textpage = page.get_textpage()
    try:
        char_count = len(textpage.get_text_bounded().strip())
    finally:
        textpage.close()

    image_area = 0.0
    for obj in page.get_objects():
        if obj.type != _IMAGE_OBJ_TYPE:
            continue
        left, bottom, right, top = obj.get_bounds()
        w = max(0.0, min(right, width) - max(left, 0.0))
        h = max(0.0, min(top, height) - max(bottom, 0.0))
        image_area += w * h

    coverage = min(image_area / page_area, 1.0)
    return char_count, coverage


def classify_page(page) -> str:
    """Classify a pypdfium2 page using its extracted signals."""
    return classify(*page_signals(page))
