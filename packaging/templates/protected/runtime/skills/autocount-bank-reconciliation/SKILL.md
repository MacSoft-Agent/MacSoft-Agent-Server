---
name: autocount-bank-reconciliation
description: Prepare, validate, create, and read back AutoCount GL Bank Reconciliation from a bank statement or user request. Use when the user asks for bank recon, bank reconciliation, clearing or ticking bank transactions, or matching an AutoCount bank/cash account to a statement balance. Provides the exact Connector command sequence and JSON payload shape.
---

# AutoCount Bank Reconciliation

## Goal

Help the user reconcile one AutoCount bank/cash GL account without guessing JSON. Use the existing generic AutoCount Tools; do not create a new connector or command-specific Tool.

## Required sequence

1. Read the current live schema for every command before calling it.
2. Use `list-gl-bank-cash-accounts` with payload `{}` to identify the correct `accNo`. If one account is obvious, show it; if several are plausible, ask the user to choose.
3. Use `list-gl-bank-reconciliation-uncleared` with:

```json
{
  "accNo": "110-0010",
  "startDate": "2026-01-01"
}
```

`startDate` is optional and must use `YYYY-MM-DD` when supplied.

4. Match the statement rows against the returned uncleared AutoCount rows. Take every selected value from the live result; never invent a `BankTransKey`.
5. Build and validate a draft with exact command type `validate-gl-bank-reconciliation`. Validation does not save anything.
6. Show the account, reconciliation date, statement balance, statement reference, and selected AutoCount rows. Ask for explicit confirmation before saving.
7. After confirmation, send the same approved payload to exact command type `create-gl-bank-reconciliation`.
8. Read back with `get-gl-bank-reconciliation` using the same `accNo` and `reconDate`. Report success only when the saved result contains the intended selection and balance.

## Exact JSON shape

The Tool call contains `command_type` and one nested JSON **object** named `payload`:

```json
{
  "command_type": "validate-gl-bank-reconciliation",
  "payload": {
    "accNo": "110-0010",
    "reconDate": "2026-06-30",
    "actualBalance": 2900,
    "selectedBankTransKeys": [1, 2],
    "bankStatementNo": "BS-2026-06",
    "description": "June bank reconciliation"
  }
}
```

After approval, change only `command_type` to `create-gl-bank-reconciliation` and preserve the approved `payload` exactly.

The AutoCount payload itself is:

```json
{
  "accNo": "110-0010",
  "reconDate": "2026-06-30",
  "actualBalance": 2900,
  "selectedBankTransKeys": [1, 2],
  "bankStatementNo": "BS-2026-06",
  "description": "June bank reconciliation"
}
```

## Field rules

- `accNo`: bank/cash **GL account number**, not debtor, creditor, bank account ID, company ID, or account-book ID.
- `reconDate`: bank statement/reconciliation date in `YYYY-MM-DD`.
- `actualBalance`: JSON number representing the actual statement balance. Do not send currency symbols, commas, or a formatted numeric string.
- `selectedBankTransKeys`: JSON array of live `BankTransKey` values returned by `list-gl-bank-reconciliation-uncleared`.
- `bankStatementNo`: optional statement/reference number.
- `description`: optional narration.
- `clearedRows`: optional detailed alternative/companion selection containing `bankTransKey`, `sourceType`, `sourceKey`, `dtlKey`, `docNo`, and `lineNo`. Prefer `selectedBankTransKeys` for the simple path. If detailed rows are used, copy every identifier from the live uncleared result.
- `unselectedBankTransKeys`: optional replacement-selection rows, mainly relevant to update behavior.

## Common format mistakes

Never:

- send `payload` as a quoted JSON string;
- send `payloadSchema`, `examplePayload`, `Master`, or `Details` as the payload wrapper;
- place `connectorId` or `companyId` inside the command payload;
- use `accountNo`, debtor code, or a bank name in place of a verified `accNo` merely because an alias exists;
- send `actualBalance` as `"RM 2,900.00"` or `"2,900.00"`;
- send document numbers in `selectedBankTransKeys`;
- create the reconciliation before the validate result and user confirmation;
- claim success before read-back.

## Update requests

For an existing reconciliation, first read it with `get-gl-bank-reconciliation`, re-list live uncleared rows, and retrieve the live `update-gl-bank-reconciliation` schema. The selected row list replaces the saved tick selection. Show the complete replacement preview and obtain fresh confirmation before updating.

## User-facing response

Speak in accounting terms, not Tool or schema narration. Show what account and statement were read, which rows matched or remained unmatched, the resulting difference, and the one decision needed. Keep Tool calls and internal JSON hidden unless the user explicitly asks for technical details.
