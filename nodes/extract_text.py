from gen.messages_pb2 import Pdf, TextResult
from gen.axiom_context import AxiomContext
from nodes._pdf import layout_pages, page_text, safe


def extract_text(ax: AxiomContext, input: Pdf) -> TextResult:
    """Extract the full normalized plain text of a PDF in pdfminer.six's
    layout-analyzed reading order, pages joined by a blank line. Reports the
    number of pages processed and whether the page cap truncated the document.
    Malformed input, a wrong password, or oversized input (>30 MB) returns a
    structured error instead of raising.
    """
    def run():
        pages, truncated = layout_pages(input)
        text = "\n\n".join(page_text(p) for p in pages)
        return TextResult(text=text, page_count=len(pages), truncated=truncated)

    result, err = safe(run)
    return result if not err else TextResult(error=err)
