from gen.messages_pb2 import Pdf, FormField, FormFieldsResult
from gen.axiom_context import AxiomContext
from nodes._pdf import form_fields, safe


def extract_form_fields(ax: AxiomContext, input: Pdf) -> FormFieldsResult:
    """Read an AcroForm's interactive field values: fully-qualified field
    name, type (Tx/Btn/Ch/Sig), current value, and the page its widget
    appears on. `has_form` is false when the document declares no /AcroForm
    at all (distinct from a form with zero fields). Malformed input returns
    a structured error instead of raising.
    """
    def run():
        fields, truncated, has_form = form_fields(input)
        out = [
            FormField(
                name=f["name"], field_type=f["field_type"],
                value=f["value"], page=f["page"],
            )
            for f in fields
        ]
        return FormFieldsResult(fields=out, truncated=truncated, has_form=has_form)

    result, err = safe(run)
    return result if not err else FormFieldsResult(error=err)
