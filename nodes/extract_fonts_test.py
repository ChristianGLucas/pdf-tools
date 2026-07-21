from gen.messages_pb2 import Pdf
from nodes.extract_fonts import extract_fonts


def test_reports_known_font_size_char_counts(ax, fonts_pdf):
    pdf_bytes, title, body = fonts_pdf
    r = extract_fonts(ax, Pdf(data=pdf_bytes))
    assert r.error == ""
    assert r.truncated is False
    assert r.page_count == 1

    page = r.pages[0]
    assert page.number == 1
    usage = {(f.name, round(f.size, 2)): f.char_count for f in page.fonts}
    # Oracle: exact character counts of the two Tj runs we wrote.
    assert usage[("Helvetica", 24.0)] == len(title)
    assert usage[("Helvetica", 12.0)] == len(body)
    # Ordered by descending usage: the longer (body) run comes first.
    assert page.fonts[0].char_count >= page.fonts[1].char_count


def test_deterministic(ax, fonts_pdf):
    pdf_bytes, _, _ = fonts_pdf
    a = extract_fonts(ax, Pdf(data=pdf_bytes))
    b = extract_fonts(ax, Pdf(data=pdf_bytes))
    assert [(f.name, f.size, f.char_count) for f in a.pages[0].fonts] == \
           [(f.name, f.size, f.char_count) for f in b.pages[0].fonts]


def test_malformed_returns_error(ax):
    r = extract_fonts(ax, Pdf(data=b"not a pdf at all"))
    assert r.error != ""
    assert r.page_count == 0


def test_empty_returns_error(ax):
    r = extract_fonts(ax, Pdf(data=b""))
    assert r.error != ""
