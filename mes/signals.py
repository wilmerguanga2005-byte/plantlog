from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from .models import Lote, SeguimientoEtapaLote

# Evento disparado cuando una lectura sobrepasa un límite PC/PCC.
desviacion_detectada = Signal()  # kwargs: alerta, lectura, limite


@receiver(post_save, sender=Lote)
def crear_seguimientos(sender, instance, created, **kw):
    """Al abrir un lote (EBR) se instancian todas las etapas de su receta."""
    if created:
        SeguimientoEtapaLote.objects.bulk_create(
            [SeguimientoEtapaLote(lote=instance, etapa=e) for e in instance.receta.etapas.all()])
