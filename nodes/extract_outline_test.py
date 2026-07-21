from gen.messages_pb2 import Pdf
from nodes.extract_outline import extract_outline
import nodes._pdf as _pdf


def test_resolves_internal_and_uri_targets(ax, structural_pdf):
    # Oracle: "Intro" -> Dest [6 0 R ...] (page 2's object); "External Ref"
    # -> a /URI action, unresolvable to a page.
    r = extract_outline(ax, Pdf(data=structural_pdf))
    assert r.error == ""
    assert r.truncated is False
    assert len(r.entries) == 2

    intro, external = r.entries
    assert intro.title == "Intro"
    assert intro.page == 2
    assert intro.uri == ""

    assert external.title == "External Ref"
    assert external.page == 0
    assert external.uri == "https://example.com/ref"


def test_no_outline_returns_empty_not_error(ax, no_structure_pdf):
    r = extract_outline(ax, Pdf(data=no_structure_pdf))
    assert r.error == ""
    assert len(r.entries) == 0


def test_caps_entries_and_reports_truncated(ax, structural_pdf, monkeypatch):
    # Claim (axiom.yaml): "Bounded to 2000 entries." Prove the cap actually
    # fires rather than just existing as an unenforced constant.
    monkeypatch.setattr(_pdf, "MAX_OUTLINE_ENTRIES", 1)
    r = extract_outline(ax, Pdf(data=structural_pdf))
    assert r.error == ""
    assert len(r.entries) == 1
    assert r.truncated is True


def test_deterministic(ax, structural_pdf):
    a = extract_outline(ax, Pdf(data=structural_pdf))
    b = extract_outline(ax, Pdf(data=structural_pdf))
    assert list(a.entries) == list(b.entries)


def test_malformed_returns_error(ax):
    r = extract_outline(ax, Pdf(data=b"not a pdf at all"))
    assert r.error != ""
    assert len(r.entries) == 0


def test_empty_returns_error(ax):
    r = extract_outline(ax, Pdf(data=b""))
    assert r.error != ""
