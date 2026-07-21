from gen.messages_pb2 import Pdf
from nodes.extract_annotations import extract_annotations
import nodes._pdf as _pdf


def test_finds_link_text_and_widget_annotations(ax, structural_pdf):
    # Oracle: page 1 has 4 annotations — Link (URI), Text (comment+author),
    # and two Widget annotations (the AcroForm's field widgets).
    r = extract_annotations(ax, Pdf(data=structural_pdf))
    assert r.error == ""
    assert r.truncated is False
    assert len(r.annotations) == 4

    by_subtype = {}
    for a in r.annotations:
        by_subtype.setdefault(a.subtype, []).append(a)

    link = by_subtype["Link"][0]
    assert link.page == 1
    assert link.uri == "https://example.com/report"
    assert (link.x0, link.y0, link.x1, link.y1) == (72.0, 680.0, 200.0, 710.0)

    text = by_subtype["Text"][0]
    assert text.page == 1
    assert text.contents == "Reviewer note here"
    assert text.author == "Ada Lovelace"
    assert text.uri == ""

    assert len(by_subtype["Widget"]) == 2
    for w in by_subtype["Widget"]:
        assert w.page == 1
        # /T on a Widget is the AcroForm field's NAME, not an annotation
        # author — that distinction belongs to ExtractFormFields, not here.
        assert w.author == ""


def test_no_annotations_on_unreferenced_page(ax, structural_pdf):
    r = extract_annotations(ax, Pdf(data=structural_pdf))
    assert all(a.page != 3 for a in r.annotations)


def test_document_without_annotations_returns_empty(ax, no_structure_pdf):
    r = extract_annotations(ax, Pdf(data=no_structure_pdf))
    assert r.error == ""
    assert len(r.annotations) == 0


def test_caps_annotations_and_reports_truncated(ax, structural_pdf, monkeypatch):
    # Claim (axiom.yaml): "a 5000-annotation cap." Prove it fires: the fixture
    # has 4 annotations, so a cap of 2 must cut the result short and flag it.
    monkeypatch.setattr(_pdf, "MAX_ANNOTATIONS", 2)
    r = extract_annotations(ax, Pdf(data=structural_pdf))
    assert r.error == ""
    assert len(r.annotations) == 2
    assert r.truncated is True


def test_deterministic(ax, structural_pdf):
    a = extract_annotations(ax, Pdf(data=structural_pdf))
    b = extract_annotations(ax, Pdf(data=structural_pdf))
    assert len(a.annotations) == len(b.annotations)
    assert [x.uri for x in a.annotations] == [x.uri for x in b.annotations]


def test_malformed_returns_error(ax):
    r = extract_annotations(ax, Pdf(data=b"not a pdf at all"))
    assert r.error != ""
    assert len(r.annotations) == 0


def test_empty_returns_error(ax):
    r = extract_annotations(ax, Pdf(data=b""))
    assert r.error != ""
