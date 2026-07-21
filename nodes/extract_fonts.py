from gen.messages_pb2 import Pdf, FontUsage, PageFonts, FontsResult
from gen.axiom_context import AxiomContext
from nodes._pdf import page_fonts, safe


def extract_fonts(ax: AxiomContext, input: Pdf) -> FontsResult:
    """Inventory the (font, size) pairs actually used on each page, with a
    per-pair character count, ordered by descending usage. Built from
    pdfminer.six's per-character font/size data, this is the raw material
    for heading/style detection (font-size clusters), font audits, and
    embedded-subset compliance checks. Honors the page cap. Malformed input
    returns a structured error instead of raising.
    """
    def run():
        pages, truncated = page_fonts(input)
        out = [
            PageFonts(
                number=p["number"],
                fonts=[
                    FontUsage(name=f["name"], size=f["size"], char_count=f["char_count"])
                    for f in p["fonts"]
                ],
            )
            for p in pages
        ]
        return FontsResult(pages=out, page_count=len(out), truncated=truncated)

    result, err = safe(run)
    return result if not err else FontsResult(error=err)
