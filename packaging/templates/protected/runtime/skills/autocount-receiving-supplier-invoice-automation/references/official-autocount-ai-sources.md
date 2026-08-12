# Official AutoCount AI Sources

Use these exact official sources when command discovery or field meaning is unclear. Do not start from the website home page and wander through unrelated pages.

1. `https://api.autocount.cloud/developers/recipes.json` — proven business recipes and example sequences.
2. `https://api.autocount.cloud/ai/manifest.json` — canonical command catalog, payload fields, examples, aliases, and AI instructions.
3. `https://api.autocount.cloud/ai/autocount-ontology.json` — accounting entities, relationships, modules, workflows, and safety rules.
4. `https://api.autocount.cloud/openapi.json` — transport endpoints and complete API contract.

## Authority order for a real operation

Use the official files to find the likely command and understand the business/API vocabulary. Then retrieve the current deployed command schema through the existing AutoCount Tool, validate the exact payload, and read the saved result back.

Static official documentation proves the platform's intended capability; it does not prove that a customer's installed connector/catalog version currently accepts the same field. When official documentation and the live schema differ:

- do not guess or force the documented field;
- report the exact capability/version mismatch;
- use only a live-validated safe alternative;
- preserve the unresolved business fact in the Case;
- require live read-back before claiming success.

Never call a local connector API directly. Use the configured AutoCount Cloud Tool boundary, unique command identity, validation, polling, approval for consequential actions, and read-back.

## Verified Batch and UDF findings

The current official files document:

- `create-item` and `update-item` with `hasBatchNo`;
- Item opening balances with `batchNo`;
- Purchase Invoice, Goods Received Note, and Stock Receive line examples with `batchNo`;
- header and line `userDefinedFields` objects;
- UDF keys without the database `UDF_` prefix.

They do not document a native `expiryDate` or `expireDate` PI line field. In the currently tested deployment, PI detail UDFs named `ExpiryDate` and `CreatedDate` are configured and have been successfully written and read back through line `userDefinedFields`.

Direct execution testing also proved that a PI can reference and read back an existing `batchNo`, and that its batch stock balance changes. A new Batch No must be established before the PI references it; the tested PI operation does not create a missing ItemBatch automatically.
