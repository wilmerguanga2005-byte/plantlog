"""Validación de lecturas contra límites PC/PCC y generación de propuestas del agente IA (basado en reglas)."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from ..models import AlertaAgenteIA, LimiteControl
from ..signals import desviacion_detectada

# (variable, sentido) -> (causa probable, acción correctiva)
BASE_CONOCIMIENTO = {
    ("TEMP", "ALTO"): ("Exceso de aporte térmico (válvula de vapor/resistencia abierta) o falla del lazo de enfriamiento; "
                       "riesgo de estrés o muerte de levadura y pérdida de rendimiento.",
                       "Reducir el aporte de calor, activar enfriamiento por chaqueta, verificar la calibración de la sonda y re-medir en 10 min."),
    ("TEMP", "BAJO"): ("Pérdida de calor por aislamiento o chaqueta insuficiente; en pasteurización implica tratamiento térmico insuficiente.",
                       "Aumentar el aporte térmico y verificar el tiempo de retención; si es PCC, retener el lote hasta repetir el tratamiento."),
    ("PH", "ALTO"): ("Acidificación insuficiente o dosificación deficiente de ácido; riesgo de contaminación microbiana.",
                     "Dosificar ácido de grado alimentario en pequeñas fracciones, homogeneizar y volver a medir el pH."),
    ("PH", "BAJO"): ("Sobre-acidificación o fermentación láctica/acética paralela.",
                     "Detener adiciones ácidas, evaluar neutralización controlada y tomar muestra para análisis microbiológico."),
    ("BRIX", "ALTO"): ("Conversión de almidón incompleta o fermentación lenta (baja actividad de levadura).",
                       "Verificar la dosis de enzima/levadura y la temperatura; extender el tiempo de fermentación y re-medir en 2 h."),
    ("BRIX", "BAJO"): ("Dilución excesiva en maceración o sobre-consumo de azúcares.",
                       "Revisar la relación agua/sólido de la receta; ajustar con jarabe o concentrado si la política lo permite."),
    ("PRESION", "ALTO"): ("Obstrucción en línea/filtro o formación excesiva de CO₂ sin venteo.",
                          "Abrir venteo, revisar filtros y válvulas de la línea."),
    ("PRESION", "BAJO"): ("Fuga en sellos/tapas o bomba con cavitación.",
                          "Inspeccionar sellos y succión de la bomba; realizar prueba de estanqueidad."),
}
GENERICA = ("Desviación respecto al límite declarado de la receta.", "Verificar el sensor, confirmar con medición manual y consultar al supervisor.")


def _limites_aplicables(lectura):
    q = Q()
    if lectura.etapa_id:
        q |= Q(etapa=lectura.etapa)
    if lectura.tanque_id:
        q |= Q(tanque=lectura.tanque)
    if not q:
        return LimiteControl.objects.none()
    return LimiteControl.objects.filter(q, variable=lectura.variable).select_related("variable")


def procesar_lectura(lectura):
    """Evalúa la lectura. Retorna la lista de AlertaAgenteIA creadas (PCC se evalúa primero)."""
    alertas = []
    for lim in sorted(_limites_aplicables(lectura), key=lambda l: l.tipo != "PCC"):
        sentido = lim.evaluar(lectura.valor_medido)
        if not sentido:
            continue
        # anti-ruido: no duplicar una alerta pendiente igual de los últimos 10 min
        if AlertaAgenteIA.objects.filter(lote=lectura.lote, etapa=lectura.etapa, variable=lectura.variable, sentido=sentido,
                                         estado="PENDIENTE", creada__gte=timezone.now() - timedelta(minutes=10)).exists():
            continue
        causa, accion = BASE_CONOCIMIENTO.get((lectura.variable.codigo, sentido), GENERICA)
        ref = lim.valor_max_critico if sentido == "ALTO" else lim.valor_min_critico
        desv = abs(Decimal(lectura.valor_medido) - ref)
        causa = (f"{lectura.variable.codigo} = {lectura.valor_medido} {lectura.variable.unidad} "
                 f"({'sobre el máximo' if sentido == 'ALTO' else 'bajo el mínimo'} crítico {ref}; desvío {desv:.2f}). {causa}")
        if lim.tipo == "PCC":
            accion = "⚠ PCC: retener el producto en proceso hasta liberación por calidad. " + accion
        alerta = AlertaAgenteIA.objects.create(
            lote=lectura.lote, etapa=lectura.etapa, variable=lectura.variable, lectura=lectura,
            tipo_control=lim.tipo, sentido=sentido, explicacion_causa=causa, accion_propuesta=accion)
        seg = lectura.lote.seguimientos.filter(etapa=lectura.etapa, estado="EN_CURSO").first() if lectura.etapa_id else None
        if seg:
            seg.estado = "DESVIADA"
            seg.save(update_fields=["estado"])
        desviacion_detectada.send(sender=AlertaAgenteIA, alerta=alerta, lectura=lectura, limite=lim)
        alertas.append(alerta)
    return alertas


def limite_para(variable, etapa=None, tanque=None):
    """Límite de referencia para graficar (prioriza etapa, luego tanque)."""
    qs = LimiteControl.objects.filter(variable=variable)
    return (qs.filter(etapa=etapa).first() if etapa else None) or (qs.filter(tanque=tanque).first() if tanque else None)
