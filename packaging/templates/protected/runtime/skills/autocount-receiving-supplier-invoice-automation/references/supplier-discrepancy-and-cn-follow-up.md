# Supplier Discrepancy and CN Follow-Up

## Decide the business correction

When PO and supplier evidence differ, show the exact difference and its quantity or financial effect. Ask staff whether the PO is wrong, the supplier file is wrong, or partial receiving is intentional. Do not assign blame from document type alone.

A CN may be appropriate when the supplier overcharged or owes the buyer a credit. Undercharge, omitted charge, replacement invoice, quantity correction, or non-financial error is not automatically CN. Let staff confirm whether a corrected document or CN is required.

## Ask in the correct order

If staff confirms that a corrected file/CN is required:

1. Ask whether the user will obtain it from the supplier.
2. If yes, offer to help follow up.
3. If follow-up is accepted, obtain supplier phone number and confirm the user name/phone represented.
4. Preview recipient and exact opening message.
5. Send only after confirmation.

Example:

> 我是 MacSoft AI 助理，受 [用户名称／电话号码] 委托跟进这份 CN。准备好后可以直接发在这里，谢谢。

## Limited messenger role

The Agent may only ask for status, receive the supplier's reply/document, and relay it to the user. It must not negotiate, promise a deadline, agree to money/quantity changes, accept a CN for the user, or handle an open-ended supplier conversation independently.

In test mode, follow up once per minute and stop after three minutes. In production, use configured timing. Stop early when:

- the supplier sends the requested document;
- the supplier says it is busy, needs time, or cannot provide it now;
- the user cancels follow-up.

Relay a delay plainly, for example:

> Supplier 说近期较忙，需要多几天。我已停止自动跟进；之后需要继续可以告诉我。

If there is no response by the limit, notify the user and stop. Do not continue silently.

## Corrected document/CN arrives

Archive it and match it to the original Pending Receiving Record using trusted sender, supplier, document/PO references, amount, line facts, and evidence identity. Ask when more than one record is plausible.

Show material corrections and ask staff whether this exact version is accepted. Receipt is not acceptance. Once accepted, repeat the PO/document comparison and resume Batch/Expiry/PI processing. Do not create the PI while a material discrepancy remains unresolved.
