"""Fictional demo starter. Intentionally contains two checkout defects."""

def quote(lines, discount_percent=0):
    if not lines:
        raise ValueError("An order needs at least one line")
    if not 0 <= float(discount_percent) <= 100:
        raise ValueError("Discount must be between 0 and 100")
    for line in lines:
        if float(line["unit_price"]) < 0:
            raise ValueError("Prices must be non-negative")
        if type(line["quantity"]) is not int or line["quantity"] <= 0:
            raise ValueError("Quantity must be a positive integer")

    subtotal = round(sum(float(line["unit_price"]) * line["quantity"] for line in lines), 2)
    discount = round(subtotal * float(discount_percent) / 100, 2)
    taxable = subtotal - discount
    shipping = 0.0 if subtotal > 500 else 39.0
    tax = round(taxable * 0.05, 2)
    total = round(taxable + shipping + tax, 2)
    return {"subtotal": f"{subtotal:.2f}", "discount": f"{discount:.2f}",
            "shipping": f"{shipping:.2f}", "tax": f"{tax:.2f}", "total": f"{total:.2f}"}
