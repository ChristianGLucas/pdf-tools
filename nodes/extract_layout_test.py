from gen.messages_pb2 import Pdf
from nodes.extract_layout import extract_layout


def test_page_dimensions_and_block_geometry(ax, simple_pdf):
    # Oracle: we drew 'Hello Axiom' at (72, 700) on a 612x792 page. pdfminer must
    # report a block/line whose bbox matches that ground truth within font metrics.
    r = extract_layout(ax, Pdf(data=simple_pdf))
    assert r.error == ""
    assert r.page_count == 1
    page = r.pages[0]
    assert page.number == 1
    assert abs(page.width - 612.0) < 0.01
    assert abs(page.height - 792.0) < 0.01
    assert len(page.blocks) == 1

    block = page.blocks[0]
    assert block.text.strip() == "Hello Axiom"
    # Left edge sits exactly where we placed the text; baseline near y=700.
    assert abs(block.x0 - 72.0) < 2.0
    assert 690.0 <= block.y0 <= 700.0
    assert 710.0 <= block.y1 <= 725.0
    assert block.x1 > 150.0  # 11 glyphs at 24pt span well past x=150
    assert block.x1 > block.x0 and block.y1 > block.y0


def test_block_contains_lines_with_bboxes(ax, simple_pdf):
    r = extract_layout(ax, Pdf(data=simple_pdf))
    line = r.pages[0].blocks[0].lines[0]
    assert line.text.strip() == "Hello Axiom"
    assert abs(line.x0 - 72.0) < 2.0
    assert line.y1 > line.y0 and line.x1 > line.x0


def test_multipage_layout(ax, three_page_pdf):
    r = extract_layout(ax, Pdf(data=three_page_pdf))
    assert r.page_count == 3
    assert [p.number for p in r.pages] == [1, 2, 3]
    assert r.pages[2].blocks[0].text.strip() == "Page three gamma"


def test_truncates_at_cap(ax, three_page_pdf):
    r = extract_layout(ax, Pdf(data=three_page_pdf, max_pages=2))
    assert r.page_count == 2
    assert r.truncated is True


def test_malformed_returns_error(ax):
    r = extract_layout(ax, Pdf(data=b"definitely not a pdf"))
    assert r.error != ""
    assert len(r.pages) == 0
