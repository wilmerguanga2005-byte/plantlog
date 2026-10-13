"""Contrato de datos para la torre de control del CEDI-UPEC."""
from django.utils import timezone
from ..models import DespachoCEDI


def construir_contrato(despacho):
    lote = despacho.lote
    alertas = lote.alertas.select_related("variable", "etapa")
    superados = [{
        "tipo": a.tipo_control, "etapa": a.etapa.nombre if a.etapa else None,
        "codigo_control": a.etapa.codigo_control if a.etapa else None,
        "variable": a.variable.codigo, "valor": float(a.lectura.valor_medido), "sentido": a.sentido,
        "estado_gestion": a.estado, "fecha": a.creada.isoformat()} for a in alertas]
    pcc_pend = alertas.filter(tipo_control="PCC", estado="PENDIENTE").exists()
    env = getattr(lote, "envasado", None)
    return {
        "esquema": "upec.cedi.despacho/v1",
        "despacho": {"codigo": despacho.codigo, "fecha": timezone.now().isoformat(), "unidades": despacho.cantidad_unidades},
        "origen": {"institucion": "Universidad Politécnica Estatal del Carchi (UPEC)",
                   "proyecto": "Gestión digital de la cadena de suministro de almidones y bebidas",
                   "orden_produccion": lote.orden.numero},
        "lote": {"codigo": lote.codigo, "receta": lote.receta.codigo, "producto": lote.receta.producto_final,
                 "inicio": lote.fecha_inicio.isoformat(), "fin": lote.fecha_fin.isoformat() if lote.fecha_fin else None,
                 "volumen_envasado_l": float(env.volumen_total_obtenido_l) if env else None},
        "controles_calidad": {
            "pc_pcc_definidos": [{"etapa": e.numero, "codigo": e.codigo_control, "tipo": e.nivel_control,
                                  "especificacion": e.especificacion_critica}
                                 for e in lote.receta.etapas.all() if e.nivel_control],
            "limites_superados": superados},
        "sellos_inocuidad": {
            "pcc_sin_desviaciones_abiertas": not pcc_pend,
            "todas_las_alertas_gestionadas": not alertas.filter(estado="PENDIENTE").exists(),
            "trazabilidad_unitaria": lote.botellas.count() == despacho.cantidad_unidades or lote.botellas.exists(),
            "liberado_para_despacho": not alertas.filter(estado="PENDIENTE").exists() and lote.botellas.exists()},
        "trazabilidad_url_base": "/trazabilidad/<codigo_serial>/",
    }


def crear_despacho(lote, cantidad=None):
    cantidad = cantidad or lote.botellas.count()
    n = DespachoCEDI.objects.count() + 1
    d = DespachoCEDI.objects.create(codigo=f"CEDI-{timezone.now():%Y%m%d}-{n:03d}", lote=lote, cantidad_unidades=cantidad)
    d.json_contrato_datos = construir_contrato(d)
    d.save(update_fields=["json_contrato_datos"])
    lote.botellas.filter(estado="ENVASADA").update(estado="DESPACHADA")
    return d
