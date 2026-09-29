"""Authors and translators derived from catalog fields. No extra model."""

import re
from collections import defaultdict

from django.db.models import Q

from .models import Product

PERSIAN_LETTERS = 'ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی'
_LETTER_ORDER = {char: index for index, char in enumerate(PERSIAN_LETTERS)}
_LETTER_FOLD = {
    'آ': 'ا',
    'أ': 'ا',
    'إ': 'ا',
    'ٱ': 'ا',
    'ك': 'ک',
    'ي': 'ی',
    'ى': 'ی',
    'ئ': 'ی',
    'ة': 'ه',
    'ؤ': 'و',
}


def split_people(value):
    """Names stored together are separated with a Persian comma."""
    if not value:
        return []
    return [part.strip() for part in str(value).split('،') if part.strip()]


def catalog_contributors():
    """Every author or translator who has at least one active book."""
    counts = defaultdict(int)
    rows = Product.objects.filter(active=True).values_list('author', 'edition')
    for author, edition in rows:
        seen = set()
        for raw in (author, edition):
            for name in split_people(raw):
                if name not in seen:
                    seen.add(name)
                    counts[name] += 1
    contributors = [
        {'author': name, 'book_count': count}
        for name, count in counts.items()
    ]
    contributors.sort(key=lambda item: persian_sort_key(item['author']))
    return contributors


def persian_letter(name):
    """Persian alphabet bucket for a name. Alef with madda stays under الف."""
    if not name:
        return ''
    char = name[0]
    return _LETTER_FOLD.get(char, char)


def persian_sort_key(name):
    parts = []
    for char in name:
        if char == '\u200c' or char.isspace():
            parts.append((40, 0))
            continue
        if char == 'آ':
            parts.append((_LETTER_ORDER['ا'], 0))
            continue
        folded = _LETTER_FOLD.get(char, char)
        if folded in _LETTER_ORDER:
            parts.append((_LETTER_ORDER[folded], 1))
        else:
            parts.append((200, ord(char)))
    return parts


def catalog_contributor_groups():
    """Full Persian alphabet, each person filed under their first letter."""
    buckets = {letter: [] for letter in PERSIAN_LETTERS}
    for person in catalog_contributors():
        letter = persian_letter(person['author'])
        if letter in buckets:
            buckets[letter].append(person)
    groups = []
    for index, letter in enumerate(PERSIAN_LETTERS):
        groups.append({
            'letter': letter,
            'slug': f'{index:02d}',
            'people': buckets[letter],
        })
    return groups


def contributor_book_filter(name):
    """Match a person as a whole field or as one comma-separated name."""
    token = re.escape(name.strip())
    pattern = rf'(^|،\s*){token}(\s*،|$)'
    return Q(author__regex=pattern) | Q(edition__regex=pattern)
