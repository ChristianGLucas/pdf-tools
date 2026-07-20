from gen.messages_pb2 import Pdf, LayoutResult, PageLayout, TextBlock, TextLine
from gen.axiom_context import AxiomContext
from nodes._pdf import layout_pages, page_blocks, safe


def extract_layout(ax: AxiomContext, input: Pdf) -> LayoutResult:
    """Extract positional layout for each page: page dimensions plus the text
    blocks pdfminer.six's layout analysis groups from character positions, each
    block and its lines carrying an (x0,y0,x1,y1) bounding box in PDF points with
    the origin at the page's bottom-left. The geometry is the raw material for
    table, column, and heading detection. Malformed or oversized input returns a
    structured error instead of raising.
    """
    def run():
        pages, truncated = layout_pages(input)
        page_layouts = []
        for i, p in enumerate(pages):
            blocks = []
            for b in page_blocks(p):
                lines = [TextLine(**ln) for ln in b["lines"]]
                blocks.append(TextBlock(
                    text=b["text"], x0=b["x0"], y0=b["y0"],
                    x1=b["x1"], y1=b["y1"], lines=lines,
                ))
            page_layouts.append(PageLayout(
                number=i + 1, width=float(p.width), height=float(p.height),
                blocks=blocks,
            ))
        return LayoutResult(
            pages=page_layouts, page_count=len(page_layouts), truncated=truncated,
        )

    result, err = safe(run)
    return result if not err else LayoutResult(error=err)
