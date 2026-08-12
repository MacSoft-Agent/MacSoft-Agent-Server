# Receiving Exceptions and Recovery

- Unreadable document: preserve it, identify critical unknowns, request clearer evidence/typed facts.
- Unknown supplier/Item/UOM: show live candidates or ask; never invent codes.
- Multiple POs: present distinguishing lines/dates/status; do not choose arbitrarily.
- No PO: offer PO creation or direct PI. If the user chooses neither, keep Pending.
- PO update unsupported: report exact manual change; do not create a duplicate PO as workaround.
- Supplier never responds or CN is rejected: retain waiting evidence/decision and escalate as configured.
- Required Batch/UDF configuration unavailable: retain values and report the exact missing configuration; do not silently omit dates or claim the line write.
- Archive failure: retain managed evidence if available and report incomplete archive.
- AutoCount unavailable: preserve Case and next required live read.
- Duplicate supplier invoice: compare stable evidence and live PI before any write.
- Lookup schema mismatch: preserve the displayed identifier, resolve an internal key only through an executed authoritative read, and report unresolved rather than absent when no mapping capability exists.
- Workflow approval/context rejection without a command ID: the write was not submitted; complete or refresh the approval handshake instead of blaming or retrying the connector.

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

## Failure classification

- No command ID and no queued/submitted response: pre-submission failure; do not claim AutoCount executed it.
- Command ID plus final failed status: connector/AutoCount execution failure; report the returned error.
- Command ID plus timeout or missing final response: uncertain; read back before any retry.
- Approval or action-digest mismatch: regenerate the preview/approval only when the underlying facts changed; otherwise complete the missing active-contract handshake without duplicating business reads.
