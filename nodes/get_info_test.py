from gen.messages_pb2 import Pdf
from nodes.get_info import get_info


def test_reads_known_metadata(ax, pdf_with_metadata):
    # Oracle: these values are exactly what we wrote into the /Info dictionary.
    r = get_info(ax, Pdf(data=pdf_with_metadata))
    assert r.error == ""
    assert r.page_count == 2
    assert r.encrypted is False
    assert r.title == "Quarterly Report"
    assert r.author == "Ada Lovelace"
    assert r.subject == "Finance"
    assert r.creator == "AxiomTest"
    assert r.producer == "pdf-tools-test"
    assert r.keywords == "q1 finance report"


def test_counts_pages_without_metadata(ax, three_page_pdf):
    r = get_info(ax, Pdf(data=three_page_pdf))
    assert r.error == ""
    assert r.page_count == 3
    assert r.encrypted is False
    assert r.title == ""  # no /Info dictionary in this document
    assert r.author == ""


def test_deterministic(ax, pdf_with_metadata):
    a = get_info(ax, Pdf(data=pdf_with_metadata))
    b = get_info(ax, Pdf(data=pdf_with_metadata))
    assert a.title == b.title and a.page_count == b.page_count


def test_malformed_returns_error(ax):
    r = get_info(ax, Pdf(data=b"not a pdf at all"))
    assert r.error != ""
    assert r.page_count == 0


def test_empty_returns_error(ax):
    r = get_info(ax, Pdf(data=b""))
    assert r.error != ""
