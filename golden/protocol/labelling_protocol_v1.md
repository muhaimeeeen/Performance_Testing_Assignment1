# Labelling Protocol — v1

Group 9 · ICT3113 Assignment 1 · Golden test set (rows 9000–9999)

## Purpose

Assign each ticket the **one** category whose team must act to resolve the complaint. The question to ask is *"Which desk would have to fix this?"*, not *"Which words appear in the text?"*

## Process rules

1. Label **independently**. Do not discuss tickets, compare answers, or look at another labeller's file until both files are submitted.
2. Do not look at the dataset's `source_label` column or any model output. The labelling tool hides the source label.
3. Read the whole narrative before deciding. The first sentence often sets the scene and is not the complaint.
4. Use **Unsure** plus a short note when two categories are close. Still pick your best answer. The note is used during adjudication.
5. Use **None** only when no category fits at all (see rule E7).

## Category definitions

| # | Category | Includes | Typical signals |
|---|----------|----------|-----------------|
| 1 | **Credit reporting** | Errors on a credit report, disputes with credit bureaus (Equifax, Experian, TransUnion), identity-theft entries, hard inquiries, credit scores, credit monitoring | "my credit report shows", "I disputed with Experian", "remove this inquiry", FCRA |
| 2 | **Debt collection** | Collectors or collection agencies: calls, letters, validation requests, debts not owed, harassment, threats, debts sold to a third party | "collection agency", "debt validation", "they keep calling", FDCPA, "this debt is not mine" |
| 3 | **Mortgage** | Home loans: origination, servicing, escrow, payments, modification, forbearance, foreclosure, HELOC, reverse mortgage | "servicer", "escrow", "loan modification", "foreclosure", "my house" |
| 4 | **Credit card** | Credit card accounts and prepaid cards: charges, fees, APR, rewards, billing disputes, card closures, credit limits | "my credit card", "statement balance", "APR", "rewards points", "prepaid card" |
| 5 | **Bank account or service** | Checking and savings accounts: deposits, withdrawals, overdraft and NSF fees, account opening and closing, holds, debit card transactions on the account, cheques | "checking account", "overdraft fee", "they closed my account", "debit card" |
| 6 | **Consumer loan** | Non-mortgage loans: auto loans and leases, personal and installment loans, payday and title loans, student loans | "car loan", "lease", "personal loan", "payday", "student loan", "Navient" |
| 7 | **Money transfer or service** | Moving money between people or institutions: wire transfers, international remittances, P2P apps (Zelle, Venmo, PayPal, Cash App), money orders, cheque cashing, virtual currency | "wire", "Western Union", "Zelle", "PayPal", "sent money to" |

## Edge-case rules

- **E1 — Credit report vs the underlying product.** If the consumer's main ask is to fix what appears on their **credit report**, or they are disputing with a **bureau**, label **Credit reporting**, even if the item is a card or loan. If the main complaint is how the **lender handled the account** and the credit report is only a consequence, label the product.
- **E2 — Collection vs credit report.** If a collection account appears on the report and the consumer is fighting the **collector** (validation, "not my debt", harassment), label **Debt collection**. If they are fighting the **bureau** to remove it, label **Credit reporting**.
- **E3 — Original creditor collecting its own debt.** If the bank or card issuer itself is chasing payment, label the **product** (e.g. Credit card). Only third-party collectors or debt buyers are **Debt collection**.
- **E4 — Debit card vs P2P vs wire.** A disputed debit card transaction or a fee on the account goes to **Bank account or service**. Money sent through Zelle, PayPal, Venmo, Cash App, a wire, or a remittance service goes to **Money transfer or service**, even when the bank is the respondent.
- **E5 — Student loans and vehicle loans.** Both go to **Consumer loan**, because this scheme has no separate student loan or vehicle category.
- **E6 — Two products, one complaint.** Pick the product whose team must take the corrective action. If that is still tied, pick the product the narrative is primarily about (usually the one introduced first as the subject of the dispute).
- **E7 — None.** Use **None** only for tickets with no financial-product complaint (e.g. empty, entirely redacted, or about an unrelated service). None tickets are excluded from the golden set and listed in the resolution log.
- **E8 — Scams and fraud.** Classify by the channel the money moved through: a wire or P2P transfer goes to Money transfer, a debit card goes to Bank account, and a credit card goes to Credit card.

## Adjudication (after both labellers submit)

1. The script `scripts/agreement.py` computes Cohen's κ and lists every disagreement.
2. The adjudicator resolves each disagreement with reference to the rules above and records the final label, the rule applied, and a one-line rationale in `golden/resolution_log.csv`.
3. If a disagreement exposes a gap in this protocol, the adjudicator adds or edits a rule, saves the result as `labelling_protocol_v2.md`, and records the change in the revision log below.

## Revision log

| Version | Date | Change | Triggered by |
|---------|------|--------|--------------|
| v1 | 2026-10-06 | Initial protocol | — |
