"""Shared pdfminer.six helpers for the pdf-tools package.

Single place that turns a canonical `Pdf` envelope into bounded, layout-analyzed
pdfminer.six objects, and the single place that enforces the input-cost bounds.

Untrusted-input discipline (PDFs are a classic resource-exhaustion surface):
  * `load_bytes` caps the RAW decoded input at MAX_PDF_BYTES *before* any parsing
    or allocation, and rejects anything without a `%PDF-` header in its first 1KB.
  * `page_limit` clamps the caller's page request into [1, HARD_MAX_PAGES] with a
    sane default, and every page iterator peeks exactly one page past the limit so
    we never materialize an unbounded number of pages.
pdfminer.six is pure Python, so a hostile document raises a *catchable* exception
(RecursionError/MemoryError/parse errors) rather than crashing the process; nodes
wrap extraction in `safe()` to convert any such failure into a structured error.
"""
import io

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextContainer, LTTextLine
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

# Hard cost bounds on untrusted input, enforced before parsing.
MAX_PDF_BYTES = 30 * 1024 * 1024      # 30 MB decoded
DEFAULT_MAX_PAGES = 500               # applied when caller passes 0
HARD_MAX_PAGES = 2000                 # ceiling even if caller asks for more

_LAPARAMS = LAParams()


def load_bytes(pdf):
    """Validate and return the raw PDF bytes from a `Pdf` message.

    Raises ValueError (never returns partial state) on empty input, input over
    MAX_PDF_BYTES, or input without a `%PDF-` header in the first 1KB. The size
    check runs on the raw bytes before any parser touches them.
    """
    raw = bytes(pdf.data)
    if not raw:
        raise ValueError("Pdf.data is empty")
    if len(raw) > MAX_PDF_BYTES:
        raise ValueError(
            f"PDF exceeds size limit: {len(raw)} bytes > {MAX_PDF_BYTES} byte cap"
        )
    if b"%PDF-" not in raw[:1024]:
        raise ValueError("input is not a PDF (no %PDF- header in first 1KB)")
    return raw


def page_limit(pdf):
    """Clamp the caller's max_pages into [1, HARD_MAX_PAGES]; 0 -> default."""
    m = int(getattr(pdf, "max_pages", 0) or 0)
    if m <= 0:
        return DEFAULT_MAX_PAGES
    return min(m, HARD_MAX_PAGES)


def _password(pdf):
    return getattr(pdf, "password", "") or ""


def layout_pages(pdf):
    """Yield up to `page_limit` LTPage layout objects; report truncation.

    Returns (pages, truncated). Consumes at most limit+1 pages from pdfminer so
    the page dimension is bounded regardless of the document's declared count.
    """
    raw = load_bytes(pdf)
    limit = page_limit(pdf)
    fp = io.BytesIO(raw)
    gen = extract_pages(fp, password=_password(pdf), laparams=_LAPARAMS)
    pages = []
    truncated = False
    for i, ltpage in enumerate(gen):
        if i >= limit:
            truncated = True
            break
        pages.append(ltpage)
    return pages, truncated


def page_text(ltpage):
    """Concatenate the text of every text container on a layout page."""
    parts = []
    for el in ltpage:
        if isinstance(el, LTTextContainer):
            parts.append(el.get_text())
    return _normalize("".join(parts))


def page_blocks(ltpage):
    """Return this page's text blocks as dicts of text + bbox + line list."""
    blocks = []
    for el in ltpage:
        if not isinstance(el, LTTextContainer):
            continue
        x0, y0, x1, y1 = el.bbox
        lines = []
        for line in el:
            if isinstance(line, LTTextLine):
                lx0, ly0, lx1, ly1 = line.bbox
                lines.append({
                    "text": line.get_text(),
                    "x0": float(lx0), "y0": float(ly0),
                    "x1": float(lx1), "y1": float(ly1),
                })
        blocks.append({
            "text": el.get_text(),
            "x0": float(x0), "y0": float(y0),
            "x1": float(x1), "y1": float(y1),
            "lines": lines,
        })
    return blocks


def doc_info(pdf):
    """Return (encrypted, info_dict, page_count, truncated) for a PDF.

    page_count is bounded at HARD_MAX_PAGES; truncated is True if the count was
    stopped at that cap. Metadata values are decoded to str.
    """
    raw = load_bytes(pdf)
    fp = io.BytesIO(raw)
    parser = PDFParser(fp)
    doc = PDFDocument(parser, password=_password(pdf))
    encrypted = getattr(doc, "encryption", None) is not None

    info = {}
    if getattr(doc, "info", None):
        raw_info = doc.info[0] if isinstance(doc.info, list) else doc.info
        if isinstance(raw_info, dict):
            for k, v in raw_info.items():
                info[str(k)] = _decode_val(v)

    count = 0
    truncated = False
    for _ in PDFPage.create_pages(doc):
        count += 1
        if count >= HARD_MAX_PAGES:
            truncated = True
            break
    return encrypted, info, count, truncated


def _decode_val(v):
    """Decode a PDF info value (bytes possibly UTF-16BE, or PSLiteral) to str."""
    if isinstance(v, bytes):
        if v[:2] == b"\xfe\xff":
            return v[2:].decode("utf-16-be", "replace")
        if v[:2] == b"\xff\xfe":
            return v[2:].decode("utf-16-le", "replace")
        return v.decode("latin-1", "replace")
    name = getattr(v, "name", None)
    if name is not None:
        return str(name)
    return str(v)


def _normalize(text):
    """Light normalization: unify newlines, strip trailing spaces per line."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines).strip("\n")


def safe(fn):
    """Run fn() and return (result, "") or (None, message) on any failure.

    Converts a pdfminer.six blow-up on hostile input into a structured error
    instead of a node crash. RecursionError/MemoryError are caught explicitly.
    """
    try:
        return fn(), ""
    except (RecursionError, MemoryError) as exc:  # hostile-structure guards
        return None, f"input too complex to process: {type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001 — deterministic structured error contract
        return None, f"{type(exc).__name__}: {exc}"
