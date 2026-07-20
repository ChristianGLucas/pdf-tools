import nodes._pdf as _pdf
from gen.messages_pb2 import Pdf
from nodes.extract_text import extract_text


def test_recovers_exact_hand_authored_text(ax, simple_pdf):
    # Oracle: 'Hello Axiom' is exactly what we drew into the PDF by hand.
    r = extract_text(ax, Pdf(data=simple_pdf))
    assert r.error == ""
    assert r.text == "Hello Axiom"
    assert r.page_count == 1
    assert r.truncated is False


def test_joins_all_pages_in_order(ax, three_page_pdf):
    r = extract_text(ax, Pdf(data=three_page_pdf))
    assert r.error == ""
    assert r.page_count == 3
    assert r.text == "Page one alpha\n\nPage two beta\n\nPage three gamma"


def test_deterministic(ax, simple_pdf):
    a = extract_text(ax, Pdf(data=simple_pdf))
    b = extract_text(ax, Pdf(data=simple_pdf))
    assert a.text == b.text and a.page_count == b.page_count


def test_truncates_at_page_cap(ax, three_page_pdf):
    r = extract_text(ax, Pdf(data=three_page_pdf, max_pages=2))
    assert r.error == ""
    assert r.page_count == 2
    assert r.truncated is True
    assert "Page three" not in r.text


def test_malformed_input_returns_error_not_crash(ax):
    r = extract_text(ax, Pdf(data=b"this is not a pdf"))
    assert r.text == ""
    assert r.error != ""
    assert "PDF" in r.error


def test_empty_input_returns_error(ax):
    r = extract_text(ax, Pdf(data=b""))
    assert r.error != ""


def test_size_cap_enforced_before_parsing(ax, monkeypatch):
    # Lower the cap so we can exercise the bound without allocating 30 MB.
    monkeypatch.setattr(_pdf, "MAX_PDF_BYTES", 8)
    r = extract_text(ax, Pdf(data=b"%PDF-1.4 padding beyond the tiny cap"))
    assert r.error != ""
    assert "size limit" in r.error
