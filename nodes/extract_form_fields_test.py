from gen.messages_pb2 import Pdf
from nodes.extract_form_fields import extract_form_fields
import nodes._pdf as _pdf


def test_reads_known_field_values(ax, structural_pdf):
    # Oracle: AcroForm with two fields — full_name (Tx, "Ada Lovelace") and
    # subscribe (Btn, "Yes") — both widgets on page 1.
    r = extract_form_fields(ax, Pdf(data=structural_pdf))
    assert r.error == ""
    assert r.has_form is True
    assert r.truncated is False
    assert len(r.fields) == 2

    by_name = {f.name: f for f in r.fields}
    assert by_name["full_name"].field_type == "Tx"
    assert by_name["full_name"].value == "Ada Lovelace"
    assert by_name["full_name"].page == 1

    assert by_name["subscribe"].field_type == "Btn"
    assert by_name["subscribe"].value == "Yes"
    assert by_name["subscribe"].page == 1


def test_document_without_acroform_reports_has_form_false(ax, no_structure_pdf):
    r = extract_form_fields(ax, Pdf(data=no_structure_pdf))
    assert r.error == ""
    assert r.has_form is False
    assert len(r.fields) == 0


def test_caps_fields_and_reports_truncated(ax, structural_pdf, monkeypatch):
    # Claim (axiom.yaml): "Bounded to 5000 fields." The fixture has 2 fields,
    # so a cap of 1 must cut the result short and flag it.
    monkeypatch.setattr(_pdf, "MAX_FORM_FIELDS", 1)
    r = extract_form_fields(ax, Pdf(data=structural_pdf))
    assert r.error == ""
    assert len(r.fields) == 1
    assert r.truncated is True


def test_deterministic(ax, structural_pdf):
    a = extract_form_fields(ax, Pdf(data=structural_pdf))
    b = extract_form_fields(ax, Pdf(data=structural_pdf))
    assert sorted(f.name for f in a.fields) == sorted(f.name for f in b.fields)


def test_malformed_returns_error(ax):
    r = extract_form_fields(ax, Pdf(data=b"not a pdf at all"))
    assert r.error != ""
    assert len(r.fields) == 0


def test_empty_returns_error(ax):
    r = extract_form_fields(ax, Pdf(data=b""))
    assert r.error != ""
