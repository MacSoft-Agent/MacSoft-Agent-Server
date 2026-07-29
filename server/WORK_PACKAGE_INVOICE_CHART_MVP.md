# Invoice Count Chart MVP Work Package

## Status

Implemented locally; real AutoCount acceptance blocked by Connector performance/update.

## Scope

- Detect explicit invoice chart requests in the Server chat boundary.
- Execute the official read-only `list-sales-invoices` command.
- Aggregate only document counts by month from `DocDate`.
- Render styled PNG and PDF with local Edge/Chromium.
- Stream an authenticated Artifact event and display/download it in the Thin Client.

## Data semantics

- The dataset is the latest 20 invoice headers returned by AutoCount.
- The metric is document count, not revenue, tax, balance, profit, or accounting-period total.
- The title and summary retain the bounded/latest qualifier.
- No customer name, document number, or amount is rendered.

## Local configuration

- Server chart and AutoCount flags are enabled only in ignored local configuration.
- Credentials remain in the ignored protected Plugin config and are not committed.
- Production defaults remain disabled and use the Foundation renderer.

## Verification

- Server focused lifecycle/intent/aggregation tests.
- Server full regression suite.
- Client TypeScript typecheck and focused UI adapter tests.
- Local Chromium smoke test produced valid PNG and PDF signatures.
- Real Connector status and official schemas were verified.

## External blocker

The configured Connector reports build `local-mvp-2026.07.21.01` and requires
`local-mvp-2026.07.28.09`. A 20-row read succeeded once during schema probing,
but subsequent bounded reads timed out at 120 and 300 seconds after larger
commands occupied the Connector. End-to-end real-data acceptance therefore
remains failed until the Connector is upgraded/recovered and the read command
completes reliably.
