from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from products.factories import ProductFactory
from products.models import Product

from .isbn import canonical_isbn13, is_valid_isbn, normalize_isbn
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
