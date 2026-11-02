# Atlas Checkout — current fictional business rules

Document: Atlas checkout requirements
Version: 2.0
Owner: Demo product team
Effective date: 2026-11-01
Review due: 2027-02-01

This is a fictional software test project, not a real payment or tax system.

1. `quote(lines, discount_percent=0)` must preserve its public function signature.
2. Prices arrive as decimal strings. Use exact decimal arithmetic. Quantize each line's extended amount (unit price multiplied by quantity) to two decimal places with ROUND_HALF_UP, then sum the line amounts into the subtotal. Do not round the unit price before multiplying by quantity.
3. Discounts are percentages of the subtotal and are rounded to two places with ROUND_HALF_UP.
4. Shipping is 0.00 when the pre-discount subtotal is at least 500.00. Otherwise shipping is 39.00. A discount does not change shipping eligibility.
5. Apply the fictional 5% tax to subtotal minus discount. Shipping is not taxable. Round tax to two places with ROUND_HALF_UP.
6. Total equals subtotal minus discount plus shipping plus tax. Every returned value is a two-decimal string under the existing keys subtotal, discount, shipping, tax and total.
7. Preserve rejection of empty orders, negative prices, non-positive or non-integer quantities, and discounts outside 0–100.
8. Add regression tests without modifying the protected baseline test file. Use the Python standard library; no installations or network access are needed.

Expected acceptance examples are in sample_orders.json and the protected baseline tests.
