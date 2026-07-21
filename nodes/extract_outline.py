from gen.messages_pb2 import Pdf, OutlineEntry, OutlineResult
from gen.axiom_context import AxiomContext
from nodes._pdf import outline_entries, safe


def extract_outline(ax: AxiomContext, input: Pdf) -> OutlineResult:
    """Extract a PDF's outline / bookmark tree (table of contents), flattened
    in depth-first order with a `level` field to reconstruct nesting. Each
    entry resolves to either a 1-based internal `page` number (GoTo dest/
    action) or a `uri` (external web link); a well-formed PDF with no
    outline at all returns zero entries, not an error. Malformed input
    returns a structured error instead of raising.
    """
    def run():
        entries, truncated = outline_entries(input)
        out = [
            OutlineEntry(level=e["level"], title=e["title"], page=e["page"], uri=e["uri"])
            for e in entries
        ]
        return OutlineResult(entries=out, truncated=truncated)

    result, err = safe(run)
    return result if not err else OutlineResult(error=err)
