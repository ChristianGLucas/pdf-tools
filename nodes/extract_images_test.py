from gen.messages_pb2 import Pdf
from nodes.extract_images import extract_images
import nodes._pdf as _pdf


def test_extracts_raw_and_jpeg_passthrough_images(ax, image_pdf):
    pdf_bytes, raw_rgb, jpeg_stub = image_pdf
    r = extract_images(ax, Pdf(data=pdf_bytes))
    assert r.error == ""
    assert r.truncated is False
    assert len(r.images) == 2

    by_name = {img.name: img for img in r.images}

    im0 = by_name["Im0"]
    assert im0.page == 1
    assert im0.width == 2 and im0.height == 2
    assert im0.bits_per_component == 8
    assert list(im0.colorspace) == ["DeviceRGB"]
    assert im0.format == "raw"
    assert im0.truncated_data is False
    # Oracle: the exact 12 raw RGB bytes we wrote, decoded with no filter.
    assert bytes(im0.data) == raw_rgb

    im1 = by_name["Im1"]
    assert im1.page == 1
    assert im1.width == 4 and im1.height == 4
    assert im1.format == "jpeg"
    # Oracle: pdfminer.six passes DCTDecode streams through untouched.
    assert bytes(im1.data) == jpeg_stub


def test_caps_image_count_and_reports_truncated(ax, image_pdf, monkeypatch):
    # Claim (axiom.yaml): "a 200-image cap." The fixture has 2 images, so a
    # cap of 1 must cut the result short and flag it.
    pdf_bytes, _, _ = image_pdf
    monkeypatch.setattr(_pdf, "MAX_IMAGES", 1)
    r = extract_images(ax, Pdf(data=pdf_bytes))
    assert r.error == ""
    assert len(r.images) == 1
    assert r.truncated is True


def test_caps_per_image_bytes_and_reports_truncated_data(ax, image_pdf, monkeypatch):
    # Claim (axiom.yaml): "a 15 MB per-image byte cap (oversized images
    # report metadata with truncated_data set and empty data)."
    pdf_bytes, _, _ = image_pdf
    monkeypatch.setattr(_pdf, "MAX_IMAGE_BYTES", 5)  # smaller than the 12-byte Im0
    r = extract_images(ax, Pdf(data=pdf_bytes))
    assert r.error == ""
    by_name = {img.name: img for img in r.images}
    im0 = by_name["Im0"]
    assert im0.truncated_data is True
    assert bytes(im0.data) == b""
    # Metadata is still populated even though the pixel data was dropped.
    assert im0.width == 2 and im0.height == 2


def test_document_without_images_returns_empty(ax, no_structure_pdf):
    r = extract_images(ax, Pdf(data=no_structure_pdf))
    assert r.error == ""
    assert len(r.images) == 0


def test_deterministic(ax, image_pdf):
    pdf_bytes, _, _ = image_pdf
    a = extract_images(ax, Pdf(data=pdf_bytes))
    b = extract_images(ax, Pdf(data=pdf_bytes))
    assert [bytes(i.data) for i in a.images] == [bytes(i.data) for i in b.images]


def test_malformed_returns_error(ax):
    r = extract_images(ax, Pdf(data=b"not a pdf at all"))
    assert r.error != ""
    assert len(r.images) == 0


def test_empty_returns_error(ax):
    r = extract_images(ax, Pdf(data=b""))
    assert r.error != ""
