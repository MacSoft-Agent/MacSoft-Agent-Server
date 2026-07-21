# Sales invoice payload quirks observed in live AutoCount session

Context: sales invoice creation for debtor `111-1111` with stock `00009` qty 2 and `00007` qty 3.

## Commands involved

- `get-debtor-detail`
- `get-stock-item-detail`
- `validate-sales-invoice`
- `create-sales-invoice`
- `get-sales-invoice`
- `void-sales-invoice`

## Observed payload behavior

### 1. `details` at top level is unsafe here
Payload:
- `debtorCode`
- `details: [{ itemCode, qty }, ...]`

Observed result:
- create succeeded but saved a malformed one-line invoice
- saved doc `I-000024`
- single blank line posted to `AccNo 500-0000`
- qty 1, unit price 1, total 1

### 2. `Details` section-style also unsafe here
Payload:
- `debtorCode`
- `Details: [...]`

Observed in validation:
- collapsed to one blank G/L line with total 1
- not suitable for create in this environment

### 3. `lines` works for validation and create
Payload:
- `debtorCode: 111-1111`
- `lines: [{ itemCode: 00009, qty: 2 }, { itemCode: 00007, qty: 3 }]`

Observed validation result:
- 2 detail lines
- item `00009`, desc `TRASH CLEAN UP SERVICE`, qty 2, UOM `PER`
- item `00007`, desc `ELECTRIC SERVICE`, qty 3, UOM `PER`
- both unit prices derived as `0`

Observed create result:
- saved doc `I-000026`
- 2 detail lines exactly as intended
- both unit prices `0.00`
- final total `0.00`

### 4. `items` also validated correctly
Payload:
- `debtorCode`
- `items: [...]`

Observed validation result:
- same 2 correct lines
- unit prices still `0`

## Pricing observation

For item `00009` and `00007`, item detail showed UOM `PER` but no populated default sale price in the returned UOM table. AutoCount therefore derived invoice `UnitPrice = 0.00`.

## Cleanup performed

Exploratory malformed documents were voided successfully:
- `I-000024`
- `I-000025`

Use this reference when a future create response claims success but the saved invoice shape looks suspicious; validate first, then read back the saved doc and compare line-level fields.