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
import itertools

from pdfminer.high_level import extract_pages
from pdfminer.layout import (
    LAParams, LTChar, LTFigure, LTImage, LTTextContainer, LTTextLine,
)
from pdfminer.pdfdocument import PDFDocument, PDFNoOutlines, PDFPasswordIncorrect
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFObjRef, list_value, resolve1

# Hard cost bounds on untrusted input, enforced before parsing.
MAX_PDF_BYTES = 30 * 1024 * 1024      # 30 MB decoded
DEFAULT_MAX_PAGES = 500               # applied when caller passes 0
HARD_MAX_PAGES = 2000                 # ceiling even if caller asks for more

# Additional cost bounds for the structural-extraction helpers below. Each
# caps a distinct cost dimension the caller can drive via crafted input,
# checked incrementally (never after materializing an unbounded collection).
MAX_OUTLINE_ENTRIES = 2000            # bookmark/TOC entries processed
MAX_ANNOTATIONS = 5000                # annotations processed across all pages
MAX_FORM_FIELDS = 5000                # AcroForm fields processed
MAX_IMAGES = 200                      # embedded images processed
MAX_IMAGE_BYTES = 15 * 1024 * 1024    # decoded size cap per image
MAX_WALK_ITEMS = 500_000              # layout-tree nodes visited per page walk
                                       # (guards pathological XObject/figure nesting)

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
    try:
        doc = PDFDocument(parser, password=_password(pdf))
    except PDFPasswordIncorrect:
        # The document is encrypted and we lack the (correct) password. We can't
        # read its pages or metadata, but "it is encrypted" is exactly the fact
        # GetInfo exists to report here — surface it rather than a bare error.
        return True, {}, 0, False
    encrypted = getattr(doc, "encryption", None) is not None

    info = {}
    if getattr(doc, "info", None):
        raw_info = doc.info[0] if isinstance(doc.info, list) else doc.info
        if isinstance(raw_info, dict):
            for k, v in raw_info.items():
                info[str(k)] = _decode_val(v)

    # Count pages, peeking one past the cap so an exactly-cap-sized document is
    # not falsely marked truncated. Iteration is bounded to HARD_MAX_PAGES + 1.
    count = 0
    truncated = False
    for _ in PDFPage.create_pages(doc):
        count += 1
        if count > HARD_MAX_PAGES:
            count = HARD_MAX_PAGES
            truncated = True
            break
    return encrypted, info, count, truncated


def _open_document(pdf):
    """Open a bounded, parsed PDFDocument for low-level access (outlines,
    annotations, AcroForm) shared by the structural-extraction helpers below.

    Mirrors doc_info's open sequence. The returned PDFDocument keeps its
    PDFParser (and therefore the BytesIO `fp`) alive via its own `_parser`
    attribute for as long as the PDFDocument itself is reachable, so it is
    safe to return just `doc` here — lazy object/stream reads after this
    function returns still have a live stream to read from.
    """
    raw = load_bytes(pdf)
    fp = io.BytesIO(raw)
    parser = PDFParser(fp)
    return PDFDocument(parser, password=_password(pdf))


def _page_number_map(doc):
    """Return {page objid: 1-based page number}, bounded to HARD_MAX_PAGES."""
    mapping = {}
    for i, page in enumerate(itertools.islice(PDFPage.create_pages(doc), HARD_MAX_PAGES)):
        mapping[page.pageid] = i + 1
    return mapping


def _dest_to_page(doc, page_map, dest):
    """Resolve a raw Dest value (a name, or an explicit [pageref, ...] array)
    to a 1-based page number, or 0 if it can't be resolved to a local page."""
    if dest is None:
        return 0
    dest = resolve1(dest)
    if isinstance(dest, (bytes, str)):
        name = dest if isinstance(dest, str) else dest.decode("latin-1", "replace")
        try:
            dest = doc.get_dest(name)
        except Exception:
            return 0
        dest = resolve1(dest)
    if isinstance(dest, (list, tuple)) and dest:
        target = dest[0]
        if isinstance(target, PDFObjRef):
            return page_map.get(target.objid, 0)
        if isinstance(target, int):
            return page_map.get(target, 0)
    return 0


def _action_target(doc, page_map, action):
    """Return (page, uri) from a PDF action dict (/A entry): a GoTo action
    resolves to a local page, a URI action returns its target URI. Any other
    or unresolvable action returns (0, "")."""
    action = resolve1(action)
    if not isinstance(action, dict):
        return 0, ""
    sname = getattr(resolve1(action.get("S")), "name", None)
    if sname == "URI":
        uri = resolve1(action.get("URI"))
        if isinstance(uri, bytes):
            uri = uri.decode("latin-1", "replace")
        return 0, (uri or "") if isinstance(uri, str) else ""
    if sname == "GoTo":
        return _dest_to_page(doc, page_map, action.get("D")), ""
    return 0, ""


def outline_entries(pdf):
    """Return (entries, truncated) — the document's bookmark/TOC tree.

    Each entry is a dict {level, title, page, uri}. `doc.get_outlines()` is a
    recursive generator with no built-in entry cap, so it is consumed through
    `itertools.islice` — that bounds how many items are ever pulled from it
    regardless of how large a crafted /Outlines tree claims to be.
    """
    doc = _open_document(pdf)
    page_map = _page_number_map(doc)
    entries = []
    truncated = False
    try:
        raw_iter = doc.get_outlines()
    except PDFNoOutlines:
        return entries, truncated
    for i, (level, title, dest, action, _se) in enumerate(
        itertools.islice(raw_iter, MAX_OUTLINE_ENTRIES + 1)
    ):
        if i >= MAX_OUTLINE_ENTRIES:
            truncated = True
            break
        page = _dest_to_page(doc, page_map, dest) if dest is not None else 0
        uri = ""
        if page == 0 and action is not None:
            a_page, a_uri = _action_target(doc, page_map, action)
            page = page or a_page
            uri = a_uri
        entries.append({"level": level, "title": title or "", "page": page, "uri": uri})
    return entries, truncated


def page_annotations(pdf):
    """Return (annotations, truncated) for every processed page.

    Honors the same page cap as the other nodes (`page_limit`), plus its own
    MAX_ANNOTATIONS cap on the total number of annotation dicts resolved.
    """
    doc = _open_document(pdf)
    page_map = _page_number_map(doc)
    limit = page_limit(pdf)
    out = []
    truncated = False
    count = 0
    for pnum, page in enumerate(
        itertools.islice(PDFPage.create_pages(doc), limit), start=1
    ):
        annots = resolve1(page.annots)
        if not annots:
            continue
        for ref in list_value(annots):
            if count >= MAX_ANNOTATIONS:
                truncated = True
                break
            a = resolve1(ref)
            if not isinstance(a, dict):
                continue
            count += 1
            subtype = _decode_val(a.get("Subtype")) if "Subtype" in a else ""
            x0 = y0 = x1 = y1 = 0.0
            if "Rect" in a:
                try:
                    rx = [float(resolve1(v)) for v in list_value(resolve1(a["Rect"]))]
                    x0, y0, x1, y1 = (
                        min(rx[0], rx[2]), min(rx[1], rx[3]),
                        max(rx[0], rx[2]), max(rx[1], rx[3]),
                    )
                except Exception:
                    pass
            contents = _decode_val(a.get("Contents")) if "Contents" in a else ""
            # /T means "author" on a markup annotation but "field name" on a
            # Widget (form-field) annotation — that's ExtractFormFields' job,
            # so don't mislabel a field name as an author here.
            author = (
                _decode_val(a.get("T"))
                if "T" in a and subtype != "Widget" else ""
            )
            uri, dest_page = "", 0
            if "A" in a:
                dest_page, uri = _action_target(doc, page_map, a.get("A"))
            elif "Dest" in a:
                dest_page = _dest_to_page(doc, page_map, a.get("Dest"))
            out.append({
                "page": pnum, "subtype": subtype,
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "contents": contents, "author": author,
                "uri": uri, "dest_page": dest_page,
            })
        if truncated:
            break
    return out, truncated


def form_fields(pdf):
    """Return (fields, truncated, has_form) — the AcroForm's interactive
    field values, flattened from its (possibly nested, radio/checkbox-group)
    field tree into fully-qualified dotted names.
    """
    doc = _open_document(pdf)
    catalog = doc.catalog
    acro = resolve1(catalog.get("AcroForm"))
    if not isinstance(acro, dict):
        return [], False, False

    limit = page_limit(pdf)
    widget_page = {}
    for pnum, page in enumerate(
        itertools.islice(PDFPage.create_pages(doc), limit), start=1
    ):
        annots = resolve1(page.annots)
        if not annots:
            continue
        for ref in list_value(annots):
            if isinstance(ref, PDFObjRef):
                widget_page[ref.objid] = pnum

    fields_root = list_value(resolve1(acro.get("Fields", [])))
    out = []
    truncated = False
    seen = set()
    stack = [(f, "") for f in reversed(fields_root)]
    while stack:
        if len(out) >= MAX_FORM_FIELDS:
            truncated = True
            break
        ref, parent_name = stack.pop()
        objid = ref.objid if isinstance(ref, PDFObjRef) else None
        if objid is not None:
            if objid in seen or len(seen) >= MAX_FORM_FIELDS * 4:
                continue
            seen.add(objid)
        d = resolve1(ref)
        if not isinstance(d, dict):
            continue
        name_part = _decode_val(d.get("T")) if "T" in d else ""
        full_name = (
            f"{parent_name}.{name_part}" if parent_name and name_part
            else (name_part or parent_name)
        )
        kids = d.get("Kids")
        if kids:
            for k in list_value(resolve1(kids)):
                stack.append((k, full_name))
            # A pure grouping node (no own /FT or /V) isn't itself a field.
            if "FT" not in d and "V" not in d:
                continue
        field_type = _decode_val(d.get("FT")) if "FT" in d else ""
        value = _decode_val(d.get("V")) if "V" in d else ""
        page = widget_page.get(objid, 0)
        out.append({
            "name": full_name or "(unnamed)", "field_type": field_type,
            "value": value, "page": page,
        })
    return out, truncated, True


_JPEG_FILTER_NAMES = {"DCTDecode", "DCT"}
_JPX_FILTER_NAMES = {"JPXDecode"}
_UNSUPPORTED_FILTER_NAMES = {"CCITTFaxDecode", "CCF", "JBIG2Decode"}


def _image_payload(img):
    """Return (data, format, truncated_data) for one LTImage's stream,
    applying the per-image byte cap AFTER decode (pdfminer.six owns filter
    decoding; we bound what we hand back, not how it decodes)."""
    try:
        stream = img.stream
        filters = stream.get_filters()
        names = {getattr(f, "name", f) for f, _params in filters}
        if names & _UNSUPPORTED_FILTER_NAMES:
            return b"", "unsupported", False
        fmt = "raw"
        if names & _JPEG_FILTER_NAMES:
            fmt = "jpeg"
        elif names & _JPX_FILTER_NAMES:
            fmt = "jp2"
        data = stream.get_data()
    except Exception:
        return b"", "unsupported", False
    if len(data) > MAX_IMAGE_BYTES:
        return b"", fmt, True
    return data, fmt, False


def embedded_images(pdf):
    """Return (images, truncated) — every embedded raster image on the
    processed pages, walking each page's layout tree (LTFigure nesting) with
    an explicit stack rather than recursion, and bounding both the number of
    images returned (MAX_IMAGES) and total tree nodes visited (MAX_WALK_ITEMS)."""
    pages, pages_truncated = layout_pages(pdf)
    out = []
    truncated = pages_truncated
    for pnum, ltpage in enumerate(pages, start=1):
        stack = list(ltpage)
        visited = 0
        while stack:
            if len(out) >= MAX_IMAGES:
                truncated = True
                break
            visited += 1
            if visited > MAX_WALK_ITEMS:
                truncated = True
                break
            item = stack.pop()
            if isinstance(item, LTImage):
                data, fmt, img_truncated = _image_payload(item)
                x0, y0, x1, y1 = item.bbox
                colorspace = [
                    _decode_val(c) for c in (item.colorspace or []) if c is not None
                ]
                out.append({
                    "page": pnum, "name": item.name or "",
                    "x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1),
                    "width": int(item.srcsize[0] or 0), "height": int(item.srcsize[1] or 0),
                    "bits_per_component": int(item.bits or 0),
                    "colorspace": colorspace, "format": fmt,
                    "data": data, "truncated_data": img_truncated,
                })
            elif isinstance(item, LTFigure):
                stack.extend(list(item))
        if len(out) >= MAX_IMAGES:
            break
    return out, truncated


def page_fonts(pdf):
    """Return (pages, truncated) — per-page (font, size) usage counts.

    Walks each page's full layout tree down to LTChar with an explicit stack
    (not recursion, to avoid native stack depth as a cost vector), bounded by
    MAX_WALK_ITEMS per page.
    """
    pages, truncated = layout_pages(pdf)
    out = []
    for pnum, ltpage in enumerate(pages, start=1):
        usage = {}
        stack = list(ltpage)
        visited = 0
        while stack:
            visited += 1
            if visited > MAX_WALK_ITEMS:
                break
            item = stack.pop()
            if isinstance(item, LTChar):
                key = (item.fontname, round(float(item.size), 2))
                usage[key] = usage.get(key, 0) + 1
                continue
            try:
                children = list(item)
            except TypeError:
                continue
            stack.extend(children)
        fonts = sorted(
            ({"name": n, "size": s, "char_count": c} for (n, s), c in usage.items()),
            key=lambda f: -f["char_count"],
        )
        out.append({"number": pnum, "fonts": fonts})
    return out, truncated


def _decode_val(v):
    """Decode a PDF value (bytes possibly UTF-16BE, a PSLiteral name, or an
    indirect reference to either) to str. Resolves one level of indirection
    first since dict/array entries throughout a PDF may be indirect refs."""
    v = resolve1(v)
    if v is None:
        return ""
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
