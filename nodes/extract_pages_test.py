from gen.messages_pb2 import Pdf
from nodes.extract_pages import extract_pages


def test_segments_pages_with_numbers_and_text(ax, three_page_pdf):
    r = extract_pages(ax, Pdf(data=three_page_pdf))
    assert r.error == ""
    assert r.page_count == 3
    assert [p.number for p in r.pages] == [1, 2, 3]
    assert r.pages[0].text == "Page one alpha"
    assert r.pages[1].text == "Page two beta"
    assert r.pages[2].text == "Page three gamma"


def test_single_page(ax, simple_pdf):
    r = extract_pages(ax, Pdf(data=simple_pdf))
    assert r.page_count == 1
    assert r.pages[0].number == 1
    assert r.pages[0].text == "Hello Axiom"


def test_truncates_at_cap(ax, three_page_pdf):
    r = extract_pages(ax, Pdf(data=three_page_pdf, max_pages=1))
    assert r.page_count == 1
    assert r.truncated is True
    assert len(r.pages) == 1
    assert r.pages[0].text == "Page one alpha"


def test_malformed_returns_error(ax):
    r = extract_pages(ax, Pdf(data=b"%PDF-1.4 but truncated garbage \x00\x01"))
    # No valid pages -> either empty pages or a structured error; never a crash.
    assert len(r.pages) == 0
