# pdf-tools

Composable [Axiom](https://axiom.dev) nodes for **PDF text & layout extraction**,
wrapping the MIT-licensed [pdfminer.six](https://github.com/pdfminer/pdfminer.six)
layout-analysis engine. Built for the Axiom marketplace.

Every node is stateless and offline: it takes one `Pdf` envelope (raw bytes plus
optional password and page cap) and returns a purpose-shaped result. No external
service, no secrets, no persisted state.

## Nodes

| Node | Input → Output | What it does |
|------|----------------|--------------|
| `ExtractText` | `Pdf` → `TextResult` | Full normalized document text in layout-analyzed reading order, pages joined by a blank line. |
| `ExtractPages` | `Pdf` → `PagesResult` | Per-page text segmentation: an ordered list of pages, each with its 1-based number and text. |
| `ExtractLayout` | `Pdf` → `LayoutResult` | Per-page layout: page dimensions plus text blocks and lines, each with an `(x0,y0,x1,y1)` bounding box — the raw material for table/column/heading detection. |
| `GetInfo` | `Pdf` → `InfoResult` | Document metadata & structure: page count, encryption flag, and info-dictionary fields (title, author, subject, creator, producer, keywords, dates). |

## The `Pdf` envelope

```
Pdf {
  bytes  data       // raw PDF bytes (base64 over JSON); %PDF- header required in first 1KB
  string password   // optional, for encrypted PDFs
  int32  max_pages  // optional page cap (1-2000); 0 => default 500
}
```

## Coordinates

Layout bounding boxes are in **PDF points** (1/72 inch) with the origin at the
**bottom-left** of the page — pdfminer.six's native coordinate system. `y0` is the
bottom edge, `y1` the top.

## Bounds on untrusted input

PDFs are a classic resource-exhaustion surface, so every node bounds cost on the
**raw** input before parsing:

- Input over **30 MB** is rejected before any parsing.
- Non-PDF input (no `%PDF-` header in the first 1KB) is rejected.
- At most **2000 pages** are ever processed; the default cap is **500**. Larger
  documents are truncated (`truncated = true`), never rejected.
- Any parse failure on hostile or malformed input becomes a structured `error`
  string — nodes do not crash.

## License

MIT © 2026 Christian George Lucas. pdfminer.six is MIT; its transitive
dependencies (charset-normalizer MIT, cryptography Apache-2.0/BSD, cffi MIT,
pycparser BSD) are all permissive.
