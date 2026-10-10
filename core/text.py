"""Persian/Arabic text normalization shared by search, ISBN validation and imports."""

import re

ZWNJ = '\u200c'
PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩'

_CHAR_MAP = {
    ord('ي'): 'ی',
    ord('ى'): 'ی',
    ord('ئ'): 'ی',
    ord('ك'): 'ک',
    ord('ة'): 'ه',
    ord('ۀ'): 'ه',
    ord('أ'): 'ا',
    ord('إ'): 'ا',
    ord('ٱ'): 'ا',
}
_DIGIT_MAP = {}
for _index, (_fa, _ar) in enumerate(zip(PERSIAN_DIGITS, ARABIC_DIGITS)):
    _DIGIT_MAP[ord(_fa)] = str(_index)
    _DIGIT_MAP[ord(_ar)] = str(_index)
_CHAR_MAP.update(_DIGIT_MAP)
_TO_PERSIAN_DIGITS = {ord(str(i)): PERSIAN_DIGITS[i] for i in range(10)}

_DIACRITICS = re.compile('[\u064B-\u065F\u0670\u0640]')
_PUNCTUATION = re.compile(r'[^\w\s]', flags=re.UNICODE)
_SPACES = re.compile(r'\s+')


def normalize_digits(text):
    """Persian/Arabic digits to ASCII."""
    if not text:
        return ''
    return str(text).translate(_DIGIT_MAP)


def normalize_persian(text):
    """
    Canonical form for matching: Persian ی/ک, ASCII digits, no diacritics/tatweel,
    ZWNJ and punctuation become spaces, whitespace collapsed.
    """
    if not text:
        return ''
    text = str(text).translate(_CHAR_MAP)
    text = _DIACRITICS.sub('', text)
    text = text.replace(ZWNJ, ' ')
    text = _PUNCTUATION.sub(' ', text)
    return _SPACES.sub(' ', text).strip()


def search_variants(token):
    """
    Spellings a stored value may use for an already-normalized token.
    The catalog was imported from WordPress, so Arabic ي/ك and Persian digits exist in data.
    """
    variants = {token}
    if 'ی' in token or 'ک' in token:
        variants.add(token.replace('ی', 'ي').replace('ک', 'ك'))
    if any(ch.isdigit() for ch in token):
        for value in list(variants):
            variants.add(value.translate(_TO_PERSIAN_DIGITS))
    return variants
