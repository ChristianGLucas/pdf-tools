from gen.messages_pb2 import Pdf, Page, PagesResult
from gen.axiom_context import AxiomContext
from nodes._pdf import layout_pages, page_text, safe


def extract_pages(ax: AxiomContext, input: Pdf) -> PagesResult:
    """Segment a PDF into per-page text: an ordered list of pages, each with its
    1-based page number and normalized text. Honors the page cap and reports
    truncation. Malformed input, a wrong password, or oversized input returns a
    structured error instead of raising.
    """
    def run():
        pages, truncated = layout_pages(input)
        out = [Page(number=i + 1, text=page_text(p)) for i, p in enumerate(pages)]
        return PagesResult(pages=out, page_count=len(out), truncated=truncated)

    result, err = safe(run)
    return result if not err else PagesResult(error=err)
