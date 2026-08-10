# MacSoft Client OCR / Attachment Integration Handoff

## Purpose

The Client uploads the original file to MacSoft Server and then sends the returned `file_id` in the normal chat request. The Client must not add a second OCR engine or a second AI runtime.

## Division of responsibility

- Client: file picker/drop/paste UI, upload progress, retry/cancel, and `file_id` lifecycle.
- MacSoft Server: authentication, device ownership, file-type/size validation, private storage, download/delete, deterministic document extraction, and the bridge to the existing AI Service.
- Existing AI Service and selected model: visual understanding/OCR for JPG, PNG, and WebP. Accuracy depends on the selected model supporting image input.
- AutoCount tools: official reads, schema validation, and later execution. OCR output is never treated as proof that an AutoCount write is correct.

No Tesseract, PaddleOCR, new Electron process, or separate Python OCR service is part of this contract.

## Authentication headers

Use the same paired-device headers as the other Client API calls:

```http
Authorization: Bearer <device_token>
X-Device-Id: <accepted_device_id>
```

Never place the device token in the URL.

## Upload

```http
POST /api/files
Content-Type: multipart/form-data
```

Multipart field name: `file`.

Supported inputs:

- JPG / JPEG
- PNG
- WebP
- PDF with extractable text
- CSV
- XLSX
- TXT

Maximum file size: 20 MB. Maximum files referenced by one chat message: 5. The combined files in one chat message must not exceed 25 MB.

Successful response contains both naming styles:

```json
{
  "ok": true,
  "file_id": "file_...",
  "fileId": "file_...",
  "filename": "bank-slip.jpg",
  "content_type": "image/jpeg",
  "contentType": "image/jpeg",
  "size_bytes": 12345,
  "sizeBytes": 12345,
  "sha256": "...",
  "created_at": "...",
  "createdAt": "..."
}
```

Do not invent a Client-side file ID. Keep the exact ID returned by the Server.

## Send attachment to chat

After every upload succeeds, send the existing chat request:

```json
{
  "session_id": "session_...",
  "message": "Extract this bank slip and prepare a reconciliation draft.",
  "uploaded_file_ids": ["file_..."]
}
```

The Client should send a clear business instruction with the attachment. It must not convert the image to guessed text and replace the original file.

If one of several uploads fails, do not submit a partial chat silently. Show which file failed and let the user retry or remove it.

## Download and delete

```http
GET /api/files/{file_id}
DELETE /api/files/{file_id}
```

Both calls require the paired-device headers. A device cannot read or delete another device's file.

Delete an unused upload when the user removes it before sending. Do not automatically delete a file merely because the user changes sessions while an upload or reply is active.

## OCR behavior the Client must communicate

- Image OCR/visual extraction is performed by the selected vision-capable AI model through the existing AI Service.
- CSV, XLSX, TXT, and text PDFs are parsed deterministically by MacSoft Server before the text is supplied to the model.
- A scanned/image-only PDF is not silently guessed. The Server asks for the relevant pages as JPG or PNG.
- OCR and document extraction can be wrong. The UI should describe results as a draft and preserve the original attachment for comparison.
- Bank Slip/bank-statement MVP produces extraction or reconciliation drafts only.
- Photo Key In MVP produces a proposed entry/draft only. An AutoCount write must not occur until the user has reviewed and explicitly confirmed the extracted business values.

## Required Client error handling

Read the top-level `error.code` and show `error.message`. Important codes include:

- `device_credentials_rejected`
- `empty_file`
- `file_too_large`
- `unsupported_file_type`
- `file_not_found`
- `invalid_file_ids`
- `too_many_files`
- `attachments_too_large`
- `scanned_pdf_requires_images`

Do not display internal IPC channel names, stack traces, local Server paths, or internal “Hermes” identifiers to the end user. The product-facing name is MacSoft.

## Minimum Client acceptance

1. Upload one JPG Bank Slip, submit its returned `file_id`, and receive a visible extraction draft.
2. Upload one CSV or XLSX bank statement and receive a structured summary/draft.
3. Upload one photographed stock document and receive a draft; verify that no AutoCount write runs before confirmation.
4. Remove an unsent attachment and confirm `DELETE` succeeds.
5. Pair a second device and confirm it receives `404 file_not_found` for the first device's file ID.
6. Confirm session switching does not cancel or cross-wire another session's file upload/reply.
