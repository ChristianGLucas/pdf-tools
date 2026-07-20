from gen.messages_pb2 import Pdf, InfoResult
from gen.axiom_context import AxiomContext
from nodes._pdf import doc_info, safe


def get_info(ax: AxiomContext, input: Pdf) -> InfoResult:
    """Read document-level metadata and structural facts from a PDF: total page
    count (bounded at 2000), whether it declares encryption, and info-dictionary
    fields (title, author, subject, creator, producer, keywords, creation and
    modification dates). A cheap triage/routing step before full extraction.
    Malformed input returns a structured error instead of raising.
    """
    def run():
        encrypted, info, count, truncated = doc_info(input)

        def g(*keys):
            for k in keys:
                v = info.get(k)
                if v:
                    return v
            return ""

        return InfoResult(
            page_count=count, encrypted=encrypted, truncated=truncated,
            title=g("Title"), author=g("Author"), subject=g("Subject"),
            creator=g("Creator"), producer=g("Producer"), keywords=g("Keywords"),
            created=g("CreationDate"), modified=g("ModDate"),
        )

    result, err = safe(run)
    return result if not err else InfoResult(error=err)
