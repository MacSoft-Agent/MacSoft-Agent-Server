# WhatsApp channels

Dynamic mappings belong in `whatsapp_identifiers`; this file records deployment policy only.

Supported purposes:

- `payment_slip_intake`
- `bank_verification`
- `receiving_document_intake`
- `supplier_cn_follow_up`

Never infer purpose from a group display name. A missing or inactive mapping blocks Case creation for that channel.
