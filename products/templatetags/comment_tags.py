from django import template

register = template.Library()

@register.filter
def only_active_comments(comments):
    return comments.filter(active = True).order_by("-datetime_created")



@register.filter
def average_rating(comments):
    if not comments:
        return 0
    total = sum(comment.stars for comment in comments)
    return round(total / len(comments), 1)