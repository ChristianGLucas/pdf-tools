from gen.messages_pb2 import Pdf, Annotation, AnnotationsResult
from gen.axiom_context import AxiomContext
from nodes._pdf import page_annotations, safe


def extract_annotations(ax: AxiomContext, input: Pdf) -> AnnotationsResult:
    """Extract every page annotation — comments, highlights, hyperlinks, and
    form-field widget markers — with its page, subtype, and bounding box.
    Hyperlinks (Link annotations with a /URI or internal GoTo action) carry
    their target in `uri` or `dest_page`; markup annotations carry `contents`
    and `author` when present. Honors the page cap and its own annotation
    cap. Malformed input returns a structured error instead of raising.
    """
    def run():
        annots, truncated = page_annotations(input)
        out = [
            Annotation(
                page=a["page"], subtype=a["subtype"],
                x0=a["x0"], y0=a["y0"], x1=a["x1"], y1=a["y1"],
                contents=a["contents"], author=a["author"],
                uri=a["uri"], dest_page=a["dest_page"],
            )
            for a in annots
        ]
        return AnnotationsResult(annotations=out, truncated=truncated)

    result, err = safe(run)
    return result if not err else AnnotationsResult(error=err)
