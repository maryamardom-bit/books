"""ISBN-10 / ISBN-13 normalization and checksum validation."""

import re

from .text import normalize_digits

_ALLOWED = re.compile(r'[^0-9X]')


def normalize_isbn(value):
    """Strip hyphens/spaces, Persian digits to ASCII, uppercase X."""
    if not value:
        return ''
    return _ALLOWED.sub('', normalize_digits(str(value)).upper())


def _isbn10_valid(isbn):
    if not re.fullmatch(r'\d{9}[\dX]', isbn):
        return False
    total = sum((10 - i) * (10 if ch == 'X' else int(ch)) for i, ch in enumerate(isbn))
    return total % 11 == 0


def _isbn13_valid(isbn):
    if not re.fullmatch(r'\d{13}', isbn):
        return False
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(isbn))
    return total % 10 == 0


def is_valid_isbn(value):
    isbn = normalize_isbn(value)
    if len(isbn) == 10:
        return _isbn10_valid(isbn)
    if len(isbn) == 13:
        return _isbn13_valid(isbn)
    return False


def isbn10_to_13(isbn10):
    core = '978' + normalize_isbn(isbn10)[:9]
    check = (10 - sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(core)) % 10) % 10
    return core + str(check)


def canonical_isbn13(value):
    """ISBN-13 form used for duplicate detection, or '' when invalid."""
    isbn = normalize_isbn(value)
    if len(isbn) == 13 and _isbn13_valid(isbn):
        return isbn
    if len(isbn) == 10 and _isbn10_valid(isbn):
        return isbn10_to_13(isbn)
    return ''
