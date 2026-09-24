from django.db import models
from django.db.models import Q

from .models import Product

# Operational / commerce fields are not bibliographic search targets.
EXCLUDED_FIELD_NAMES = {
    'id',
    'pk',
    'wordpress_id',
    'active',
    'image',
    'price',
    'discount_percent',
    'discount_start_date',
    'discount_end_date',
    'special_price',
    'stock',
    'reserved_stock',
    'datetime_created',
    'datetime_modified',
}

TEXT_FIELD_TYPES = (models.CharField, models.TextField)
NUMERIC_FIELD_TYPES = (
    models.IntegerField,
    models.PositiveIntegerField,
    models.PositiveSmallIntegerField,
    models.SmallIntegerField,
    models.BigIntegerField,
    models.DecimalField,
    models.FloatField,
)


def get_searchable_product_fields():
    """Return concrete Product fields that can be searched, from the live model."""
    fields = []
    for field in Product._meta.get_fields():
        if not getattr(field, 'concrete', False) or getattr(field, 'auto_created', False):
            continue
        if field.name in EXCLUDED_FIELD_NAMES:
            continue
        if isinstance(field, (models.ForeignKey, models.ManyToManyField, models.OneToOneField)):
            continue
        if isinstance(field, (models.ImageField, models.FileField, models.BooleanField)):
            continue
        if isinstance(field, (models.DateTimeField, models.DateField, models.TimeField)):
            continue
        if isinstance(field, TEXT_FIELD_TYPES + NUMERIC_FIELD_TYPES):
            fields.append(field)
    return fields


def get_searchable_field_choices():
    """Labels for Advanced Search checkboxes (driven by Product._meta)."""
    return [
        {'name': field.name, 'label': str(field.verbose_name).rstrip(':').strip()}
        for field in get_searchable_product_fields()
    ]


def _allowed_field_map():
    return {field.name: field for field in get_searchable_product_fields()}


def _query_for_field(field, query):
    name = field.name
    clauses = Q()

    if isinstance(field, TEXT_FIELD_TYPES):
        clauses |= Q(**{f'{name}__icontains': query})
        if field.choices:
            matching = [
                value
                for value, label in field.flatchoices
                if query.lower() in str(label).lower() or query.lower() in str(value).lower()
            ]
            if matching:
                clauses |= Q(**{f'{name}__in': matching})
        return clauses

    if isinstance(field, NUMERIC_FIELD_TYPES):
        normalized = query.replace(',', '').replace('،', '').strip()
        try:
            number = int(float(normalized))
        except (TypeError, ValueError):
            return Q()
        return Q(**{name: number})

    return Q()


def build_search_q(query, field_names=None):
    """
    Build an OR query across selected Product fields.
    field_names=None → all searchable fields (simple search).
    field_names=[] → no fields selected (advanced with none checked).
    """
    query = (query or '').strip()
    if not query:
        return None

    allowed = _allowed_field_map()
    if field_names is None:
        selected = list(allowed.values())
    else:
        selected = [allowed[name] for name in field_names if name in allowed]
        if not selected:
            return None

    combined = Q()
    for field in selected:
        combined |= _query_for_field(field, query)
    return combined if combined else None
