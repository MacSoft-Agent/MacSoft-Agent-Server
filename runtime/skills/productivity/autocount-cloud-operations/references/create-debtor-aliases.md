# Create Debtor Payload Alias Note

Observed session pattern:
- Command: `create-debtor`
- Live schema exposed canonical field names like `AccNo` and `CompanyName`, plus aliases such as `accNo`, `debtorCode`, and `companyName`.
- A first write using canonical keys failed with official error: `Missing command value: accNo`.
- Retrying with alias-style lower-camel keys succeeded.

Practical takeaway:
- For write commands, do not assume the displayed canonical field casing is the safest payload key.
- When the schema provides aliases, prefer the alias form that matches the connector's command-value wording if present.
- If the first write fails with a missing command value naming an alias, rebuild the payload with that exact alias and retry once.

Verified successful debtor-create payload shape in this session:
- `accNo`
- `companyName`
- `address1`
- `phone1`
- `emailAddress`
- `currencyCode`

Verified outcome fields worth reporting after success:
- `saved`
- `updated`
- `accNo`
- `companyName`
- `controlAccount`
- `isActive`
- `commandId`
