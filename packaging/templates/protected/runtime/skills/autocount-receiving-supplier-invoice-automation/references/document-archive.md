# Document Archive

Original supplier/receiving evidence must survive WhatsApp cache cleanup, Client restart, session deletion, and workflow continuation.

Use only a trusted source attachment and the controlled evidence/archive capability. Validate MIME/size, resolve path safely, prevent traversal, calculate SHA-256, assign an internal evidence ID, and retain original filename only as metadata. Link every archived object to company/account book/Case and provenance.

Read the archive destination from Company Configuration. Distinguish Server/shared storage from a Client-local path; the Server must not claim it wrote to an inaccessible Client path.

If configured archival fails, preserve managed evidence when possible, keep the Case pending/warned, and report the exact failure. Never claim archival based only on a planned path. Do not store credentials in document metadata.
