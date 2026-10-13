from django.db import transaction
from django.utils import timezone

from ..models import Envasado
from . import qr


@transaction.atomic
def cerrar_envasado(lote, volumen_l, unidades, merma_l, usuario=None):
    """Cierra la etapa de envasado: registra el Envasado, genera las N botellas con QR y finaliza el lote."""
    env, _ = Envasado.objects.update_or_create(lote=lote, defaults=dict(
        volumen_total_obtenido_l=volumen_l, unidades_terminadas=unidades, merma_envasado_l=merma_l, fecha=timezone.now()))
    botellas = qr.generar_botellas(env)
    seg = lote.seguimientos.filter(etapa__nombre__icontains="envasado").first()
    if seg and seg.estado != "COMPLETADA":
        seg.fecha_hora_inicio = seg.fecha_hora_inicio or timezone.now()
        seg.completar()
    lote.estado, lote.fecha_fin = "ENVASADO", timezone.now()
    lote.save(update_fields=["estado", "fecha_fin"])
    return env, botellas
