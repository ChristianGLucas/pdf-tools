from gen.messages_pb2 import Pdf, EmbeddedImage, ImagesResult
from gen.axiom_context import AxiomContext
from nodes._pdf import embedded_images, safe


def extract_images(ax: AxiomContext, input: Pdf) -> ImagesResult:
    """Extract every embedded raster image: page, placement bounding box,
    source pixel dimensions, colorspace, and the image bytes themselves.
    JPEG/JPEG2000-filtered images pass through as their native file bytes
    (`format` "jpeg"/"jp2"); other filters are fully decompressed to raw
    interleaved samples (`format` "raw"); filters pdfminer.six can't decode
    (CCITT fax, JBIG2) report `format` "unsupported" with empty data. Honors
    the page cap, an image-count cap, and a per-image byte cap (oversized
    images are reported with metadata but `truncated_data = true` and empty
    data). Malformed input returns a structured error instead of raising.
    """
    def run():
        images, truncated = embedded_images(input)
        out = [
            EmbeddedImage(
                page=i["page"], name=i["name"],
                x0=i["x0"], y0=i["y0"], x1=i["x1"], y1=i["y1"],
                width=i["width"], height=i["height"],
                bits_per_component=i["bits_per_component"],
                colorspace=i["colorspace"], format=i["format"],
                data=i["data"], truncated_data=i["truncated_data"],
            )
            for i in images
        ]
        return ImagesResult(images=out, truncated=truncated)

    result, err = safe(run)
    return result if not err else ImagesResult(error=err)
