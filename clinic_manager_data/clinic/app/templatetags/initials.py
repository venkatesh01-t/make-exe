from django import template

register = template.Library()

@register.filter
def initials(value):
    return ''.join(word[0].upper() for word in value.split())