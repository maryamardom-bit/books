from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from products.factories import ProductFactory
from products.models import Product

from decimal import Decimal

from .isbn import canonical_isbn13, is_valid_isbn, normalize_isbn
from .money import InvalidAmountError, UnsupportedCurrencyError, woo_amount_to_toman
from .text import normalize_persian, search_variants


class PersianNormalizationTest(SimpleTestCase):
    def test_arabic_letters_and_digits(self):
        self.assertEqual(normalize_persian('كتاب علي ۱۴۰۲'), 'کتاب علی 1402')

    def test_zwnj_punctuation_and_spaces(self):
        self.assertEqual(normalize_persian('  میر\u200cعباسی،   معماری!  '), 'میر عباسی معماری')

    def test_variants_cover_arabic_spelling_and_persian_digits(self):
        variants = search_variants('کتاب 12')
        self.assertIn('كتاب 12', variants)
        self.assertIn('کتاب ۱۲', variants)


class ISBNTest(SimpleTestCase):
    def test_valid_isbn13_with_hyphens_and_persian_digits(self):
        self.assertEqual(normalize_isbn('978-0-306-40615-7'), '9780306406157')
        self.assertTrue(is_valid_isbn('978-0-306-40615-7'))
        self.assertTrue(is_valid_isbn('۹۷۸-۰-۳۰۶-۴۰۶۱۵-۷'))

    def test_invalid_checksum(self):
        self.assertFalse(is_valid_isbn('9780306406158'))

    def test_isbn10_maps_to_isbn13(self):
        self.assertEqual(canonical_isbn13('0-306-40615-2'), '9780306406157')


class WooAmountToTomanTest(SimpleTestCase):
    def test_currency_mappings(self):
        self.assertEqual(woo_amount_to_toman('1000', 'IRR'), 100)
        self.assertEqual(woo_amount_to_toman('1000', 'IRT'), 1000)
        self.assertEqual(woo_amount_to_toman('1000', 'IRHR'), 100000)
        self.assertEqual(woo_amount_to_toman('1000', 'IRHT'), 1000000)

    def test_audit_examples(self):
        self.assertEqual(woo_amount_to_toman('1965000', 'IRR'), 196500)
        self.assertEqual(woo_amount_to_toman('1425', 'IRHT'), 1425000)
        self.assertEqual(woo_amount_to_toman('29028.2', 'IRHT'), 29028200)
        self.assertEqual(woo_amount_to_toman('1965005', 'IRR'), 196501)

    def test_zero_stays_zero(self):
        for currency in ('IRR', 'IRT', 'IRHR', 'IRHT'):
            with self.subTest(currency=currency):
                self.assertEqual(woo_amount_to_toman('0', currency), 0)
                self.assertEqual(woo_amount_to_toman(0, currency), 0)
                self.assertEqual(woo_amount_to_toman('0.00', currency), 0)

    def test_rial_divisibility(self):
        self.assertEqual(woo_amount_to_toman('1965010', 'IRR'), 196501)
        self.assertEqual(woo_amount_to_toman('1965004', 'IRR'), 196500)
        self.assertEqual(woo_amount_to_toman('1965006', 'IRR'), 196501)

    def test_round_half_up_boundaries(self):
        self.assertEqual(woo_amount_to_toman('5', 'IRR'), 1)
        self.assertEqual(woo_amount_to_toman('4.99', 'IRR'), 0)
        self.assertEqual(woo_amount_to_toman('0.5', 'IRT'), 1)
        self.assertEqual(woo_amount_to_toman('2.5', 'IRT'), 3)
        self.assertEqual(woo_amount_to_toman('0.0005', 'IRHT'), 1)
        self.assertEqual(woo_amount_to_toman('0.0004999', 'IRHT'), 0)
        self.assertEqual(woo_amount_to_toman('0.005', 'IRHR'), 1)

    def test_fractional_decimal_strings(self):
        self.assertEqual(woo_amount_to_toman('41009.4167', 'IRHT'), 41009417)
        self.assertEqual(woo_amount_to_toman(' 1425.5 ', 'IRHT'), 1425500)
        self.assertEqual(woo_amount_to_toman('+100', 'IRT'), 100)

    def test_accepts_int_and_decimal(self):
        self.assertEqual(woo_amount_to_toman(1965000, 'IRR'), 196500)
        self.assertEqual(woo_amount_to_toman(Decimal('29028.2'), 'IRHT'), 29028200)
        self.assertIsInstance(woo_amount_to_toman(Decimal('1'), 'IRT'), int)

    def test_float_goes_through_its_decimal_string(self):
        # 0.1 + 0.2 is 0.30000000000000004 in binary; repr keeps that exact decimal value.
        self.assertEqual(woo_amount_to_toman(1965005.0, 'IRR'), 196501)
        self.assertEqual(woo_amount_to_toman(0.1 + 0.2, 'IRHT'), 300)
        self.assertEqual(woo_amount_to_toman(1e20, 'IRR'), 10 ** 19)

    def test_negative_amounts_rejected(self):
        for raw in ('-1', -1, Decimal('-0.01'), -0.5):
            with self.subTest(raw=raw), self.assertRaises(InvalidAmountError):
                woo_amount_to_toman(raw, 'IRR')

    def test_negative_zero_is_zero(self):
        self.assertEqual(woo_amount_to_toman('-0', 'IRR'), 0)

    def test_malformed_amounts_rejected(self):
        for raw in ('', '   ', 'abc', '1,965,000', '1.2.3', '.5', '5.', '1e3', '۱۲۳', '12 34', None, [], True):
            with self.subTest(raw=raw), self.assertRaises(InvalidAmountError):
                woo_amount_to_toman(raw, 'IRR')

    def test_non_finite_rejected(self):
        for raw in ('NaN', 'Infinity', '-Infinity', 'sNaN', float('nan'), float('inf'), float('-inf'),
                    Decimal('NaN'), Decimal('Infinity'), Decimal('-Infinity')):
            with self.subTest(raw=raw), self.assertRaises(InvalidAmountError):
                woo_amount_to_toman(raw, 'IRR')

    def test_unknown_currency_rejected(self):
        for currency in ('', 'USD', 'TOMAN', 'IRRR', 'IR R', None, 10):
            with self.subTest(currency=currency), self.assertRaises(UnsupportedCurrencyError):
                woo_amount_to_toman('100', currency)

    def test_currency_code_is_normalized(self):
        self.assertEqual(woo_amount_to_toman('100', ' irht '), 100000)
        self.assertEqual(woo_amount_to_toman('100', 'Irr'), 10)

    def test_errors_are_value_errors(self):
        with self.assertRaises(ValueError):
            woo_amount_to_toman('x', 'IRR')
        with self.assertRaises(ValueError):
            woo_amount_to_toman('1', 'XYZ')

    def test_large_amounts_keep_precision(self):
        self.assertEqual(woo_amount_to_toman('123456789012345678901234567895', 'IRR'),
                         12345678901234567890123456790)
        self.assertEqual(woo_amount_to_toman('98765432109876543210987654321.5', 'IRHT'),
                         98765432109876543210987654321500)
        self.assertEqual(woo_amount_to_toman('2227500000', 'IRR'), 222750000)


class ProductISBNRulesTest(TestCase):
    def test_duplicate_isbn_is_rejected_across_formats(self):
        ProductFactory(title='Book X', isbn='978-0-306-40615-7')
        candidate = Product(title='New', description='d', isbn='0306406152')
        with self.assertRaises(ValidationError) as ctx:
            candidate.clean()
        self.assertIn('Book X', str(ctx.exception))

    def test_invalid_isbn_is_rejected(self):
        with self.assertRaises(ValidationError):
            Product(title='New', description='d', isbn='12345').clean()


class PersianSearchTest(TestCase):
    def test_arabic_spelling_in_data_is_found(self):
        book = ProductFactory(title='معماري كلاسيك', active=True)
        response = self.client.get('/products/search/', {'q': 'معماری کلاسیک'})
        self.assertIn(book, list(response.context['results']))

    def test_split_name_matches_joined_name(self):
        book = ProductFactory(author='میرعباسی', active=True)
        response = self.client.get('/products/search/', {'q': 'میر عباسی'})
        self.assertIn(book, list(response.context['results']))


class HealthCheckTest(TestCase):
    def test_health_passes(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'PASS')
        self.assertEqual(data['checks']['database']['status'], 'PASS')
