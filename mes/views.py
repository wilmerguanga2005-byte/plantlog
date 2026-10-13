import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (AlertaAgenteIA, BalanceMateriaEtapa, Botella, DespachoCEDI, EtapaReceta, Lote,
                     SeguimientoEtapaLote, SolicitudAtencion, Variable)
from .services import qr as svc_qr


@login_required
def dashboard(request):
    lotes = Lote.objects.select_related("receta").exclude(estado="FINALIZADO")[:8]
    return render(request, "mes/dashboard.html", {
        "lotes": lotes,
        "n_lotes_activos": Lote.objects.filter(estado="EN_PROCESO").count(),
        "n_botellas": Botella.objects.count(),
        "n_alertas_pcc": AlertaAgenteIA.objects.filter(estado="PENDIENTE", tipo_control="PCC").count(),
        "alertas": AlertaAgenteIA.objects.select_related("lote", "variable").filter(estado="PENDIENTE")[:5],
    })


@login_required
def lotes_lista(request):
    destino = request.GET.get("destino", "control")
    titulos = {"control": "Lotes (EBR)", "balance": "Cronograma y balance de materia", "iot": "IoT en vivo", "envasado": "Envasado y botellas"}
    return render(request, "mes/lotes_lista.html", {
        "lotes": Lote.objects.select_related("receta", "orden"), "destino": destino, "titulo": titulos.get(destino, "Lotes")})


@login_required
def lote_control(request, codigo):
    lote = get_object_or_404(Lote.objects.select_related("receta", "orden"), codigo=codigo)
    segs = lote.seguimientos.select_related("etapa", "etapa__equipo").prefetch_related("operarios")
    activa = lote.etapa_activa()
    pcs = [s.etapa for s in segs if s.etapa.es_pc]
    pccs = [s.etapa for s in segs if s.etapa.es_pcc]
    variables = Variable.objects.filter(lecturaproceso__lote=lote).distinct() or Variable.objects.all()
    return render(request, "mes/lote_ebr_control.html", {
        "lote": lote, "segs": segs, "activa": activa, "pcs": pcs, "pccs": pccs, "variables": variables,
        "alertas_pendientes_lote": lote.alertas.filter(estado="PENDIENTE").select_related("variable", "etapa", "lectura"),
        "estimada_h": round(lote.duracion_estimada_min / 60, 1),
        "etapa_activa_num": activa.etapa.numero if activa else "",
    })


@login_required
def balance_materia(request, codigo):
    lote = get_object_or_404(Lote.objects.select_related("receta"), codigo=codigo)
    if request.method == "POST":
        seg = get_object_or_404(SeguimientoEtapaLote, pk=request.POST.get("seguimiento"), lote=lote)
        try:
            vals = {k: Decimal(request.POST.get(k) or 0) for k in ("masa_entra_kg", "masa_incorporada_kg", "masa_continua_kg", "merma_declarada_kg")}
            if any(v < 0 for v in vals.values()):
                raise InvalidOperation
        except InvalidOperation:
            messages.error(request, "Valores de masa inválidos.")
        else:
            b, _ = BalanceMateriaEtapa.objects.update_or_create(
                seguimiento_etapa=seg, defaults={**vals, "motivo_merma": request.POST.get("motivo_merma", "")[:200]})
            (messages.success if b.balance_cierra() else messages.warning)(
                request, f"Balance de E{seg.etapa.numero} guardado. Rendimiento real: {b.rendimiento_real_pct}%."
                + ("" if b.balance_cierra() else f" Merma no declarada: {b.merma_no_declarada_kg} kg."))
        return redirect("mes:balance", codigo=codigo)

    filas, totales = [], {"entra": Decimal(0), "inc": Decimal(0), "merma": Decimal(0)}
    segs = lote.seguimientos.select_related("etapa", "balance")
    for s in segs:
        b = getattr(s, "balance", None)
        filas.append({"seg": s, "bal": b})
        if b:
            totales["entra"] += b.masa_entra_kg if not totales["entra"] else 0
            totales["inc"] += b.masa_incorporada_kg
            totales["merma"] += b.merma_declarada_kg
    con = [f["bal"] for f in filas if f["bal"]]
    salida = con[-1].masa_continua_kg if con else Decimal(0)
    entrada = con[0].masa_entra_kg if con else Decimal(0)
    global_pct = round(salida / (entrada + totales["inc"]) * 100, 2) if con and (entrada + totales["inc"]) else 0
    chart = {
        "labels": [f"E{f['seg'].etapa.numero}" for f in filas],
        "nombres": [f["seg"].etapa.nombre for f in filas],
        "continua": [float(f["bal"].masa_continua_kg) if f["bal"] else 0 for f in filas],
        "merma": [float(f["bal"].merma_declarada_kg) if f["bal"] else 0 for f in filas],
        "real": [float(f["bal"].rendimiento_real_pct) if f["bal"] else None for f in filas],
        "esperado": [float(f["seg"].etapa.rendimiento_esperado_pct) for f in filas],
    }
    return render(request, "mes/balance_materia_etapa.html", {
        "lote": lote, "filas": filas, "totales": totales, "salida": salida, "entrada": entrada, "global_pct": global_pct,
        "teorico_pct": lote.receta.rendimiento_encadenado_pct(), "chart": chart})


@login_required
def envasado_marbetes(request, codigo):
    lote = get_object_or_404(Lote.objects.select_related("receta"), codigo=codigo)
    return render(request, "mes/envasado_marbetes.html", {
        "lote": lote, "envasado": getattr(lote, "envasado", None),
        "botellas": lote.botellas.all()[:240], "total": lote.botellas.count(),
        "pendientes": lote.alertas.filter(estado="PENDIENTE").count()})


@login_required
def marbetes_zip(request, codigo):
    lote = get_object_or_404(Lote, codigo=codigo)
    resp = HttpResponse(svc_qr.zip_marbetes(lote), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="marbetes_{lote.codigo}.zip"'
    return resp


@login_required
def alertas_lista(request):
    estado = request.GET.get("estado", "PENDIENTE")
    qs = AlertaAgenteIA.objects.select_related("lote", "etapa", "variable", "lectura", "auditado_por")
    return render(request, "mes/alertas_lista.html", {
        "alertas": qs.filter(estado=estado) if estado != "TODAS" else qs, "estado": estado,
        "puntos": EtapaReceta.objects.filter(Q(es_pc=True) | Q(es_pcc=True)).select_related("receta")})


@login_required
def cedi_lista(request):
    return render(request, "mes/cedi_lista.html", {
        "despachos": DespachoCEDI.objects.select_related("lote"),
        "lotes_listos": Lote.objects.filter(estado__in=["ENVASADO", "FINALIZADO"], botellas__isnull=False).distinct()})


def trazabilidad_publica(request, codigo_serial):
    """Portal público (sin autenticación) al que apunta el QR de cada botella."""
    botella = get_object_or_404(Botella.objects.select_related("lote", "lote__receta", "envasado"), codigo_serial_uuid_gs1=codigo_serial)
    if request.method == "POST":
        tipo = request.POST.get("tipo", "CONSULTA")
        if tipo in dict(SolicitudAtencion.TIPOS) and request.POST.get("nombre") and request.POST.get("contacto"):
            SolicitudAtencion.objects.create(botella=botella, tipo=tipo, nombre=request.POST["nombre"][:120],
                                             contacto=request.POST["contacto"][:120], mensaje=request.POST.get("mensaje", "")[:1000])
            messages.success(request, "Recibimos tu solicitud. El equipo de la UPEC te contactará.")
        else:
            messages.error(request, "Completa nombre y contacto.")
        return redirect("mes:trazabilidad", codigo_serial=codigo_serial)
    lote = botella.lote
    controles = []
    for e in lote.receta.etapas.all():
        if not e.nivel_control:
            continue
        desv = lote.alertas.filter(etapa=e)
        controles.append({"etapa": e, "desviaciones": desv.count(),
                          "abiertas": desv.filter(estado="PENDIENTE").count()})
    total_ok = all(c["abiertas"] == 0 for c in controles)
    return render(request, "mes/trazabilidad_publica.html", {
        "b": botella, "lote": lote, "controles": controles, "total": lote.botellas.count(),
        "autentica": svc_qr.autentica(botella), "conforme": total_ok})
