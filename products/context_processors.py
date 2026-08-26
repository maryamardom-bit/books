import json
from .models import FAQ


def faq_context(request):
    """Send FAQs to template for chat widget"""
    faqs = FAQ.objects.filter(is_active=True)
    faqs_list = [{'question': faq.question, 'answer': faq.answer} for faq in faqs]
    
    return {
        'faqs_json': json.dumps(faqs_list, ensure_ascii=False),
    }