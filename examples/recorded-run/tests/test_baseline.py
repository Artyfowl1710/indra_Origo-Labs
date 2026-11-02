"""Protected acceptance tests. Add new tests in another file; do not edit these."""
import unittest
from checkout import quote

class CheckoutAcceptance(unittest.TestCase):
    def test_normal_order(self):
        self.assertEqual(quote([{"unit_price": "150.00", "quantity": 1}]),
                         {"subtotal":"150.00","discount":"0.00","shipping":"39.00","tax":"7.50","total":"196.50"})

    def test_exact_free_shipping_threshold(self):
        result = quote([{"unit_price": "199.90", "quantity": 2}, {"unit_price": "100.20", "quantity": 1}])
        self.assertEqual(result["shipping"], "0.00")
        self.assertEqual(result["total"], "525.00")

    def test_half_up_line_rounding(self):
        result = quote([{"unit_price": "2.675", "quantity": 1}])
        self.assertEqual(result["subtotal"], "2.68")
        self.assertEqual(result["total"], "41.81")

    def test_discount_then_tax(self):
        result = quote([{"unit_price": "250.00", "quantity": 2}], discount_percent=10)
        self.assertEqual(result["discount"], "50.00")
        self.assertEqual(result["tax"], "22.50")
        self.assertEqual(result["total"], "472.50")

    def test_above_threshold(self):
        self.assertEqual(quote([{"unit_price":"600.00","quantity":1}])["shipping"], "0.00")

    def test_reject_negative_price(self):
        with self.assertRaises(ValueError): quote([{"unit_price":"-1.00","quantity":1}])

    def test_reject_zero_quantity(self):
        with self.assertRaises(ValueError): quote([{"unit_price":"10.00","quantity":0}])

    def test_reject_invalid_discount(self):
        with self.assertRaises(ValueError): quote([{"unit_price":"10.00","quantity":1}], discount_percent=101)

if __name__ == "__main__": unittest.main()
