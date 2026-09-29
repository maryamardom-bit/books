from .models import ContactInfo

_DIGIT_MAP = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def site_contact(request):
    """WhatsApp link for the footer, using the number stored in contact info."""
    contact = ContactInfo.objects.first()
    digits = ''
    if contact and contact.whatsapp:
        digits = ''.join(
            char for char in str(contact.whatsapp).translate(_DIGIT_MAP) if char.isdigit()
        )
    return {
        'footer_whatsapp_url': f'https://wa.me/{digits}' if digits else '',
    }
