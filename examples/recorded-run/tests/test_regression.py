"""Regression tests for Atlas Checkout fixes - does not modify baseline."""
import unittest
from checkout import quote
from decimal import Decimal

class TestRegression(unittest.TestCase):
    def test_exact_500_free_shipping(self):
        result = quote([{"unit_price": "199.90", "quantity": 2}, {"unit_price": "100.20", "quantity": 1}])
        self.assertEqual(result["shipping"], "0.00")
        self.assertEqual(result["subtotal"], "500.00")

    def test_fractional_cent_half_up(self):
        result = quote([{"unit_price": "2.675", "quantity": 1}])
        self.assertEqual(result["subtotal"], "2.68")
        self.assertEqual(result["tax"], "0.13")

    def test_shipping_boundary_just_below(self):
        result = quote([{"unit_price": "499.99", "quantity": 1}])
        self.assertEqual(result["shipping"], "39.00")

    def test_discount_does_not_affect_shipping(self):
        # 500 subtotal with discount still free shipping
        result = quote([{"unit_price": "250.00", "quantity": 2}], discount_percent=10)
        self.assertEqual(result["shipping"], "0.00")
        self.assertEqual(result["subtotal"], "500.00")

if __name__ == "__main__":
    unittest.main()
