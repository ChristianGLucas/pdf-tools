# pdf-tools

Composable [Axiom](https://axiomide.com) nodes for **PDF text, layout & structure
extraction**, wrapping the MIT-licensed
[pdfminer.six](https://github.com/pdfminer/pdfminer.six) engine. Built for the
Axiom marketplace.

Every node is stateless and offline: it takes one `Pdf` envelope (raw bytes plus
optional password and page cap) and returns a purpose-shaped result. No external
service, no secrets, no persisted state.

## Use it from your agent or app

Every node in this package is a **live, auto-scaling API endpoint** on the
[Axiom](https://axiomide.com) marketplace — call it from an AI agent or your own
code, with nothing to self-host.

**📦 See it on the marketplace:**
https://dev.axiomide.com/marketplace/christiangeorgelucas/pdf-tools@0.2.0

**Hook it up to an AI agent (MCP).** Add Axiom's hosted MCP server to any MCP
client and every node becomes a typed tool your agent can call — search the
catalog, inspect a schema, and invoke it directly.

```bash
# Claude Code
claude mcp add --transport http axiom https://api.axiomide.com/mcp \
  --header "Authorization: Bearer $AXIOM_API_KEY"
```

Claude Desktop, Cursor, or any config-based client:

```json
{
  "mcpServers": {
    "axiom": {
      "type": "http",
      "url": "https://api.axiomide.com/mcp",
      "headers": { "Authorization": "Bearer YOUR_AXIOM_API_KEY" }
    }
  }
}
```

**Call it from the CLI.**

```bash
axiom invoke christiangeorgelucas/pdf-tools/ExtractText --input '{ ... }'
```

**Call it over HTTP.**

```bash
curl -X POST https://api.axiomide.com/invocations/v1/nodes/christiangeorgelucas/pdf-tools/0.2.0/ExtractText \
  -H "Authorization: Bearer $AXIOM_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{ ... }'
```

> Input/output schema for each node is on the marketplace page above, or via
> `axiom inspect node christiangeorgelucas/pdf-tools/ExtractText`.

### Get started free

Install the CLI:

```bash
# macOS / Linux — Homebrew
brew install axiomide/tap/axiom

# macOS / Linux — install script
curl -fsSL https://raw.githubusercontent.com/AxiomIDE/axiom-releases/main/install.sh | sh
```

**Windows:** download the `windows/amd64` `.zip` from the
[releases page](https://github.com/AxiomIDE/axiom-releases/releases), unzip it,
and put `axiom.exe` on your `PATH`.

Then `axiom version` to verify, `axiom login` (GitHub or Google) to authenticate,
and create an API key under **Console → API Keys**. Docs and sign-up at
**[axiomide.com](https://axiomide.com)**.

## Nodes

| Node | Input → Output | What it does |
|------|----------------|--------------|
| `ExtractText` | `Pdf` → `TextResult` | Full normalized document text in layout-analyzed reading order, pages joined by a blank line. |
| `ExtractPages` | `Pdf` → `PagesResult` | Per-page text segmentation: an ordered list of pages, each with its 1-based number and text. |
| `ExtractLayout` | `Pdf` → `LayoutResult` | Per-page layout: page dimensions plus text blocks and lines, each with an `(x0,y0,x1,y1)` bounding box — the raw material for table/column/heading detection. |
| `GetInfo` | `Pdf` → `InfoResult` | Document metadata & structure: page count, encryption flag, and info-dictionary fields (title, author, subject, creator, producer, keywords, dates). |
| `ExtractOutline` | `Pdf` → `OutlineResult` | Bookmark / table-of-contents tree, flattened with a `level` for nesting; each entry resolves to an internal `page` or an external `uri`. |
| `ExtractAnnotations` | `Pdf` → `AnnotationsResult` | Every page annotation — comments, highlights, hyperlinks, form-widget markers — with page, subtype, bounding box, and (for links) the target `uri`/`dest_page`. |
| `ExtractFormFields` | `Pdf` → `FormFieldsResult` | AcroForm interactive field values: fully-qualified name, type (Tx/Btn/Ch/Sig), current value, and the page its widget appears on. |
| `ExtractImages` | `Pdf` → `ImagesResult` | Every embedded raster image: placement bounding box, pixel dimensions, colorspace, and the image bytes (JPEG/JPEG2000 pass through natively; other filters decode to raw samples). |
| `ExtractFonts` | `Pdf` → `FontsResult` | Per-page `(font, size)` usage inventory with character counts — the raw material for heading/style detection via font-size clustering and font audits. |

## The `Pdf` envelope

```
Pdf {
  bytes  data       // raw PDF bytes (base64 over JSON); %PDF- header required in first 1KB
  string password   // optional, for encrypted PDFs
  int32  max_pages  // optional page cap (1-2000); 0 => default 500
}
```

## Coordinates

Every bounding box in this package — `ExtractLayout`'s blocks/lines,
`ExtractAnnotations`' annotations, `ExtractImages`' placement boxes — is in
**PDF points** (1/72 inch) with the origin at the **bottom-left** of the page,
pdfminer.six's native coordinate system. `y0` is the bottom edge, `y1` the top.

## Bounds on untrusted input

PDFs are a classic resource-exhaustion surface, so every node bounds cost on the
**raw** input before parsing:

- Input over **30 MB** is rejected before any parsing.
- Non-PDF input (no `%PDF-` header in the first 1KB) is rejected.
- At most **2000 pages** are ever processed; the default cap is **500**. Larger
  documents are truncated (`truncated = true`), never rejected. Every node
  honors this same page cap, including the five below.
- Any parse failure on hostile or malformed input becomes a structured `error`
  string — nodes do not crash.

The five structural-extraction nodes add their own bound on top, each checked
incrementally (never after materializing an unbounded collection) and each
reported via `truncated`/`truncated_data` rather than a hard failure:

- `ExtractOutline` — at most **2000** bookmark entries.
- `ExtractAnnotations` — at most **5000** annotations.
- `ExtractFormFields` — at most **5000** AcroForm fields.
- `ExtractImages` — at most **200** images, and at most **15 MB** of decoded
  data per image (an oversized image reports its metadata with
  `truncated_data = true` and empty `data`).
- `ExtractFonts` — no extra cap beyond the shared page cap; per-page character
  walks are bounded internally against pathological XObject/figure nesting.

## License

MIT © 2026 Christian George Lucas. pdfminer.six is MIT; its transitive
dependencies (charset-normalizer MIT, cryptography Apache-2.0/BSD, cffi MIT,
pycparser BSD) are all permissive.
