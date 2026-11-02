"""Atlas Checkout - fixed per docs/CURRENT_REQUIREMENTS.md v2.0"""
from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")

def _q(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def quote(lines, discount_percent=0):
    if not lines:
        raise ValueError("An order needs at least one line")
    if not 0 <= float(discount_percent) <= 100:
        raise ValueError("Discount must be between 0 and 100")
    for line in lines:
        if Decimal(str(line["unit_price"])) < 0:
            raise ValueError("Prices must be non-negative")
        if type(line["quantity"]) is not int or line["quantity"] <= 0:
            raise ValueError("Quantity must be a positive integer")

    line_amounts = []
    for line in lines:
        amt = Decimal(str(line["unit_price"])) * Decimal(line["quantity"])
        line_amounts.append(_q(amt))
    subtotal = sum(line_amounts, Decimal("0.00"))
    subtotal = _q(subtotal)

    discount = _q(subtotal * Decimal(str(discount_percent)) / Decimal("100"))
    taxable = subtotal - discount
    shipping = Decimal("0.00") if subtotal >= Decimal("500.00") else Decimal("39.00")
    tax = _q(taxable * Decimal("0.05"))
    total = _q(taxable + shipping + tax)

    return {
        "subtotal": format(subtotal, ".2f"),
        "discount": format(discount, ".2f"),
        "shipping": format(shipping, ".2f"),
        "tax": format(tax, ".2f"),
        "total": format(total, ".2f"),
    }
