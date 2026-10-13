from django import template
register = template.Library()

@register.filter
def hm(minutos):
    """Minutos -> '3 h 05 min'."""
    try:
        m = int(round(float(minutos)))
    except (TypeError, ValueError):
        return "—"
    return f"{m // 60} h {m % 60:02d} min"
