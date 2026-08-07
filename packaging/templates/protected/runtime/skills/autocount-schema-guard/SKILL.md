---
name: autocount-schema-guard
description: Safely interpret live AutoCount command schemas and build payloads without guessing or coercing identifiers. Use for every AutoCount catalog search, schema lookup, payload validation, command execution, or result interpretation, especially when fields contain words such as account number, document number, code, key, reference, date, amount, quantity, or ID, or when local validation conflicts with the live schema or example payload.
---

# AutoCount Schema Guard

Treat the live AutoCount catalog and command schema as the authority. Prevent local heuristics or model assumptions from changing the business meaning of a payload.

## Required workflow

1. Call `autocount_search_commands` when the exact command is not already established by a fresh live result.
2. Call `autocount_get_command_schema` for the selected command before building its payload.
3. Build the payload only from fields returned by that live schema.
4. Call `autocount_validate_command` before execution.
5. Call `autocount_execute_command` only when the payload is supported by explicit schema evidence and validation does not contradict that evidence.
6. Report only the final connector result. Never turn a validation failure, timeout, missing result, or ambiguous identifier into zero rows or success.

## Type authority

Use this precedence when deciding a field type:

1. Explicit JSON Schema `type`, format, enum, and required declarations.
2. Explicit native field metadata from the live command schema.
3. The exact JSON type shown by `examplePayload`.
4. If none of these establishes a type, preserve the user's original JSON type and ask when ambiguity affects the operation.

Never infer a JSON type from an English field name or description alone. In particular, the words `number`, `numeric`, or `decimal` inside a business label do not prove that the JSON value is numeric.

## Identifier rules

- Treat account numbers, document numbers, invoice numbers, debtor or creditor codes, item codes, references, IDs, keys, UOMs, locations, and tax codes as identifiers unless the live schema explicitly defines a numeric JSON type.
- Preserve leading zeros, hyphens, spaces, prefixes, suffixes, and letter case.
- Never convert an identifier string to an integer or decimal merely to satisfy a local validation message.
- Never invent a missing identifier. Resolve it with an official read/list command or ask the user.
- Never guess dates, balances, amounts, quantities, rates, or confirmation flags.

## Schema conflict handling

When local validation contradicts stronger live evidence:

1. Do not coerce the payload to satisfy the contradictory local expectation.
2. Do not execute the altered payload.
3. State that the local validator conflicts with the live AutoCount schema.
4. Show the conflicting field in business language, the live evidence, and the local expectation without exposing secrets.
5. Ask for user direction only if the live schema itself is ambiguous. Otherwise stop safely and report the blocker.

Top-level tool transport success does not mean payload validity. Inspect `data.valid`, all structured validation arrays, `submitted`, final command `status`, and the connector result.

## Known active hazard

For `list-gl-bank-reconciliation-uncleared` and `get-gl-bank-reconciliation`, the live schema describes `accNo` as a bank/cash account number and shows a string example such as `110-0010`. Keep `accNo` as a string. If validation says `expected: number` only because the description contains "account number," treat that as a local validator defect. Do not remove punctuation or leading zeros and do not claim that a result from a coerced numeric account represents the requested account.

## Result verification

Before answering the user:

- Confirm the command reached a final successful connector status.
- Confirm the echoed command type matches the selected live command.
- Confirm echoed identifiers preserve the intended account/document identity.
- Distinguish an actual empty result from a rejected, timed-out, or mismatched query.
- For writes, return the official saved document number or record key. For reads, return the actual row count and records supplied by the connector.
