import socket
from django.conf import settings
from django.core.cache import cache

def _broker_activo():
    ok = cache.get("mqtt_ok")
    if ok is None:
        try:
            with socket.create_connection((settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT), timeout=0.25):
                ok = True
        except OSError:
            ok = False
        cache.set("mqtt_ok", ok, 15)
    return ok

def estado_global(request):
    if not request.user.is_authenticated:
        return {}
    from .models import AlertaAgenteIA
    return {
        "alertas_pendientes": AlertaAgenteIA.objects.filter(estado="PENDIENTE").count(),
        "mqtt_activo": _broker_activo(),
        "mqtt_host": f"{settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}",
    }
