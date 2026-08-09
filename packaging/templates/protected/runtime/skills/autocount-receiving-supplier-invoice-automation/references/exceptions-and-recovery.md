# Receiving Exceptions and Recovery

- Unreadable document: preserve it, identify critical unknowns, request clearer evidence/typed facts.
- Unknown supplier/Item/UOM: show live candidates or ask; never invent codes.
- Multiple POs: present distinguishing lines/dates/status; do not choose arbitrarily.
- No PO and user declines creation: keep Case pending/manual.
- PO update unsupported: report exact manual change; do not create a duplicate PO as workaround.
- Supplier never responds or CN is rejected: retain waiting evidence/decision and escalate as configured.
- Batch/expiry/UDF field unsupported: retain values and manual warning; do not claim line write.
- Archive failure: retain managed evidence if available and report incomplete archive.
- AutoCount unavailable: preserve Case and next required live read.
- Duplicate supplier invoice: compare stable evidence and live PI before any write.

## Stale approval

Any relevant Case/PO/Item/document/CN/PI payload change invalidates approval. Reload, regenerate preview/digest, and obtain new approval.

## Unknown write result

Persist stable action ID/execution-started event first. After timeout:

1. do not retry;
2. inspect Case events;
3. query live PO/Item/PI using supported references;
4. if success is proven, record/read back;
5. if failure is proven, retry only while the same approval/action remains valid;
6. otherwise escalate for manual verification.

Never create a second PO or PI just because the first response was lost.
