import json
from .models import FAQ
from .search import get_searchable_field_choices


def faq_context(request):
    """Send FAQs to template for chat widget"""
    faqs = FAQ.objects.filter(is_active=True)
    faqs_list = [{'question': faq.question, 'answer': faq.answer} for faq in faqs]
    
    return {
        'faqs_json': json.dumps(faqs_list, ensure_ascii=False),
    }


def search_context(request):
    """Expose live Product searchable fields to header Advanced Search."""
    return {
        'book_search_fields': get_searchable_field_choices(),
    }