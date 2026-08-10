# WhatsApp Document Ingestion Design

## Objective

Allow the MacSoft WhatsApp workflow to read supplier, receiving, payment, and
bank PDF attachments before the LLM begins business reasoning, without
enabling the Hermes Terminal, arbitrary file access, or code-execution
toolsets.

The established Receiving and Payment Skills remain the business workflow
authority. Document extraction supplies untrusted evidence only; it does not
approve, validate, or execute an AutoCount action.

## Scope

This change covers inbound documents received by the bundled WhatsApp adapter:

- text-based PDF documents;
- scanned or image-only PDF documents;
- the existing directly supported text-document types;
- preservation of the current trusted attachment path and media metadata for
  later `workflow_archive_evidence` use.

It does not add a general document Tool, enable Terminal or code execution for
WhatsApp, change AutoCount write rules, change approval authority, or add a
public Client/Server API.

## Authority and security boundaries

1. The WhatsApp bridge-provided file path is accepted only after the existing
   `_is_allowed_bridge_path` cache-root validation succeeds.
2. Extraction reads only files attached to the current `MessageEvent`; the LLM
   cannot supply another path to this pre-processing path.
3. Extracted text and page images are untrusted user evidence. They must be
   framed as attachment data, never as system instructions.
4. The original trusted path remains available to the MacSoft workflow plugin
   through `MACSOFT_SESSION_MEDIA_JSON` so `workflow_archive_evidence` can
   archive the exact current-message bytes.
5. No extraction result grants identity, approval, account-book, or AutoCount
   authority.
6. Existing file-size, media-type, and trusted-current-message checks remain
   fail closed.

## Architecture

### Shared extraction behavior

Create a narrow, pure document-ingestion helper in the Hermes Gateway document
path. It will accept a validated local PDF path and return one of:

- extracted text with page boundaries;
- rendered page-image paths for visual processing;
- a typed, user-safe failure.

The helper will follow the MacSoft Server attachment contract where applicable:

- text extraction uses `pypdf`;
- extracted text is capped at 80,000 characters;
- empty text is classified as an image/scanned PDF, not as a successful empty
  extraction;
- corrupt or encrypted/unreadable PDFs return a specific failure;
- original attachment bytes are not modified.

The Server remains the owner of Client-facing upload and extraction behavior.
This Gateway helper is an internal WhatsApp ingestion path and must have
contract tests demonstrating parity for common PDF outcomes, avoiding a new
public API or runtime dependency owner.

### Text-based PDF flow

For a validated WhatsApp PDF:

1. Read the PDF with `pypdf` before constructing the LLM user turn.
2. Preserve page boundaries in the extracted text.
3. Add a bounded block to the message:

   ```text
   [BEGIN UNTRUSTED ATTACHMENT DATA: supplier-invoice.pdf]
   ...extracted text...
   [END UNTRUSTED ATTACHMENT DATA: supplier-invoice.pdf]
   ```

4. Keep the existing trusted attachment path note for approved workflow Tools.
5. Do not tell the model to use Terminal or ask the user to paste the document.

### Scanned PDF flow

When a PDF has no meaningful extractable text:

1. Render a bounded number of pages to PNG files in the profile-specific
   Hermes image cache.
2. Treat those PNGs as current-turn image attachments and pass them through the
   existing Gateway native/auxiliary vision routing.
3. Add a text note identifying the original filename and page number for each
   rendered image.
4. Keep the original PDF path as the workflow evidence source; rendered pages
   are temporary derived inputs and are not substitutes for the archived
   original.
5. If page rendering is unavailable, return a precise message asking for the
   relevant pages as JPG/PNG rather than claiming that the session lacks tools.

Initial limits:

- maximum original attachment size: retain the existing WhatsApp/document
  cache limit and the workflow evidence limit where stricter;
- maximum rendered pages per message: 20;
- maximum extracted text: 80,000 characters;
- rendered page resolution: sufficient for invoice text while remaining under
  existing vision payload limits.

Documents exceeding a limit must be reported clearly and left available for
workflow evidence archival where allowed; they must not be silently truncated
in a way that hides missing pages or accounting lines.

## Message and workflow behavior

After ingestion, the LLM receives the original user caption plus extracted
text or page images. The applicable protected Skill then controls behavior.

For Receiving:

- extract supplier, invoice, PO, item, quantity, price, tax, batch, expiry, and
  uncertainty;
- register/archive accepted evidence;
- create or continue one Receiving Case;
- follow PO, discrepancy, CN, batch/expiry, approval, and read-back rules.

For Payment:

- treat a Payment Slip as payer-side evidence only;
- record a pending Case only after the user agrees;
- wait for acceptable bank evidence before debtor and invoice work;
- follow preview, approval, execution, and read-back rules.

Extraction must never collapse these workflow stages.

## Error handling

- Missing cached file: state that the WhatsApp attachment is no longer
  available and ask the user to resend it.
- Unsupported document type: identify the supported alternatives.
- Corrupt/encrypted PDF: state that the PDF could not be read and ask for an
  unlocked or exported copy.
- Text extraction empty and rendering succeeds: continue through vision.
- Text extraction empty and rendering unavailable: ask for relevant pages as
  JPG/PNG.
- Page or size limit exceeded: state which limit was reached and request a
  smaller document or relevant page range.
- Partial extraction: identify omitted pages/characters explicitly; do not
  present the extraction as complete.

No extraction failure may fall back to enabling Terminal automatically.

## Testing

Add focused tests for:

1. WhatsApp text PDF content is injected before the LLM turn.
2. Extracted content is wrapped as untrusted attachment data.
3. Trusted source path and media type remain in session media context.
4. A PDF outside the allowed bridge cache is rejected before reading.
5. An image-only PDF routes rendered pages through existing image handling.
6. Page labels retain original filename and page number.
7. Corrupt/encrypted PDFs produce a specific safe failure.
8. File, page, and text limits fail visibly.
9. No `terminal`, `process`, `execute_code`, or general `file` toolset is added
   to the MacSoft WhatsApp configuration or initializer.
10. Existing text-document, image, audio, video, and WhatsApp reply behavior
    remains unchanged.
11. MacSoft workflow evidence archival continues to accept only trusted media
    from the current message.
12. Client/Admin PDF extraction contracts remain green.

Verification must include focused WhatsApp adapter and Gateway tests, MacSoft
Server file-contract tests, PharmaRise workflow tests, and an installed/source
runtime acceptance using a real WhatsApp text PDF and scanned PDF.

## Acceptance criteria

- Sending a text-based supplier invoice PDF through WhatsApp gives the LLM the
  document text without Terminal access.
- Sending a scanned supplier invoice PDF gives the LLM page pixels through the
  existing vision path.
- The LLM no longer replies that PDF extraction is impossible merely because
  Terminal is unavailable.
- The protected Receiving or Payment Skill remains the workflow authority.
- Original evidence can be archived from the trusted current-message path.
- No arbitrary local path can enter extraction through model-controlled input.
- WhatsApp retains only `macsoft_autocount` and `skills_readonly` configured
  toolsets unless independently approved later.
