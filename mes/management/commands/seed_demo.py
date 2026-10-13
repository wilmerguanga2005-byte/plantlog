"""Carga datos demo: planta, receta ALM-BEB-REC-01-04, límites PC/PCC, un lote en proceso y uno ya envasado."""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from mes.models import *
from mes.services import alertas as svc_alertas, cedi as svc_cedi, envasado as svc_env

D = Decimal
# (n, nombre, tipo, equipo, trabajo, espera, personas, rend%, pc, pcc, codigo, especificacion)
ETAPAS = [
    (1, "Recepción y pesaje de materia prima", "OP", "BAL-01", 30, 0, 2, 99.5, True, False, "PC-1", "Humedad del almidón ≤ 14 %; peso verificado en balanza calibrada."),
    (2, "Inspección de materia prima", "INS", "BAL-01", 20, 0, 1, 99.0, True, False, "PC-2", "Sin impurezas visibles; almidón blanco, sin olor rancio."),
    (3, "Maceración y molienda húmeda", "OP", "MAR-01", 90, 0, 2, 97.0, False, False, "", ""),
    (4, "Cocción y gelatinización", "OP", "MAR-01", 120, 0, 1, 98.0, False, False, "", ""),
    (5, "Enfriamiento (demora)", "DEM", "MAR-01", 0, 90, 0, 100.0, False, False, "", ""),
    (6, "Inoculación con levadura", "OP", "FER-01", 30, 0, 1, 100.0, True, False, "PC-3", "Temperatura de inoculación 24–32 °C; pH 4,0–5,2."),
    (7, "Fermentación controlada", "OP", "FER-01", 30, 600, 1, 92.0, True, False, "PC-4", "Temperatura 24–30 °C (óptimo 27 °C); pH 4,0–5,2; °Brix 2–16."),
    (8, "Sedimentación y clarificación (demora)", "DEM", "SED-01", 0, 120, 0, 97.0, False, False, "", ""),
    (9, "Pasteurización", "OP", "PAS-01", 150, 0, 1, 99.0, False, True, "PCC-1", "Temperatura 72–78 °C (óptimo 75 °C) con retención ≥ 15 s. Fuera de rango: retener lote."),
    (10, "Inspección fisicoquímica final", "INS", "LAB-01", 30, 0, 1, 99.5, True, False, "PC-5", "pH 3,8–4,6; °Brix 2–12; sin turbidez ni sedimento."),
    (11, "Envasado y sellado", "OP", "ENV-01", 120, 0, 2, 98.0, False, False, "", ""),
    (12, "Etiquetado y marbetado QR", "OP", "ENV-01", 40, 0, 1, 100.0, False, False, "", ""),
]
LIMITES = [  # etapa -> (var, min, max, opt, tipo)
    (6, "TEMP", 24, 32, 28, "PC"), (6, "PH", 4.0, 5.2, 4.6, "PC"),
    (7, "TEMP", 24, 30, 27, "PC"), (7, "PH", 4.0, 5.2, 4.6, "PC"), (7, "BRIX", 2, 16, 10, "PC"),
    (9, "TEMP", 72, 78, 75, "PCC"), (10, "PH", 3.8, 4.6, 4.2, "PC"), (10, "BRIX", 2, 12, 7, "PC"),
]


class Command(BaseCommand):
    help = "Datos demostrativos UPEC MES"

    def handle(self, *a, **o):
        random.seed(11)
        U = get_user_model()
        sup, creado = U.objects.get_or_create(username="supervisor", defaults={"is_staff": True, "first_name": "Supervisor", "last_name": "Planta"})
        if creado:
            sup.set_password("upec2026"); sup.save()
            self.stdout.write(self.style.WARNING("Usuario demo: supervisor / upec2026  (cámbielo en producción)"))

        areas = {n: AreaPlanta.objects.get_or_create(nombre=n)[0] for n in
                 ["Área de recepción y pesaje", "Línea de fermentación y maceración", "Sala de destilación y horneado", "Sala de envasado"]}
        ar = list(areas.values())
        eq = {c: Equipo.objects.get_or_create(codigo=c, defaults={"nombre": n, "area": a})[0] for c, n, a in [
            ("BAL-01", "Balanza de plataforma 500 kg", ar[0]), ("MAR-01", "Marmita de cocción 400 L", ar[1]),
            ("FER-01", "Fermentador acero inox. 500 L", ar[1]), ("SED-01", "Tanque de sedimentación", ar[1]),
            ("PAS-01", "Pasteurizador de placas", ar[2]), ("LAB-01", "Estación de laboratorio", ar[2]), ("ENV-01", "Envasadora y selladora", ar[3])]}
        tq = {c: Tanque.objects.get_or_create(codigo=c, defaults=dict(tipo=t, capacidad=cap))[0] for c, t, cap in
              [("T-01", "FERMENTADOR", 500), ("T-02", "FERMENTADOR", 500), ("T-03", "SEDIMENTACION", 400), ("T-D1", "DESTILADOR", 300)]}
        var = {c: Variable.objects.get_or_create(codigo=c, defaults={"nombre": n, "unidad": u})[0] for c, n, u in
               [("TEMP", "Temperatura", "°C"), ("PH", "pH", "pH"), ("BRIX", "Sólidos solubles", "°Brix"), ("PRESION", "Presión", "kPa")]}
        for n, u, t in [("Almidón de papa (Carchi)", "kg", "MP"), ("Agua tratada", "kg", "MP"), ("Levadura Saccharomyces", "kg", "ADI"),
                        ("Botella de vidrio 750 mL", "u", "ENV"), ("Etiqueta/marbete", "u", "ENV")]:
            Insumo.objects.get_or_create(nombre=n, defaults={"unidad_medida": u, "tipo": t})

        receta, nueva = RecetaProceso.objects.get_or_create(codigo="ALM-BEB-REC-01-04", defaults=dict(
            nombre="Bebida fermentada de almidón de papa", producto_final="Bebida de almidón fermentada 750 mL",
            tamano_corrida_base=300, unidad_medida="L", rendimiento_teorico_pct=80))
        if nueva:
            for n, nom, tipo, e, tw, te, p, r, pc, pcc, cod, esp in ETAPAS:
                EtapaReceta.objects.create(receta=receta, numero=n, nombre=nom, tipo=tipo, equipo=eq[e], tiempo_trabajo_min=tw,
                    tiempo_espera_min=te, personas_requeridas=p, rendimiento_esperado_pct=r, es_pc=pc, es_pcc=pcc,
                    codigo_control=cod, especificacion_critica=esp)
            receta.rendimiento_teorico_pct = receta.rendimiento_encadenado_pct(); receta.save()
            for n, v, mn, mx, op, tipo in LIMITES:
                LimiteControl.objects.create(etapa=receta.etapas.get(numero=n), variable=var[v], valor_min_critico=mn,
                                             valor_max_critico=mx, valor_optimo=op, tipo=tipo)
        ahora = timezone.now()
        etapas = {e.numero: e for e in receta.etapas.all()}

        def balances(lote, hasta):
            masa = D(120)
            for s in lote.seguimientos.select_related("etapa").filter(etapa__numero__lte=hasta):
                inc = {3: D(180), 6: D("0.6")}.get(s.etapa.numero, D(0))
                rend = s.etapa.rendimiento_esperado_pct + D(str(round(random.uniform(-0.8, 0.3), 2)))
                rend = min(rend, D(100))
                cont = ((masa + inc) * rend / 100).quantize(D("0.001"))
                BalanceMateriaEtapa.objects.update_or_create(seguimiento_etapa=s, defaults=dict(
                    masa_entra_kg=masa, masa_incorporada_kg=inc, masa_continua_kg=cont,
                    merma_declarada_kg=(masa + inc - cont).quantize(D("0.001")),
                    motivo_merma="Residuos en equipo, evaporación y muestreo" if masa + inc > cont else ""))
                masa = cont

        def lote_base(codigo, orden, horas_atras):
            o, _ = OrdenProduccion.objects.get_or_create(numero=orden, defaults=dict(fecha_programacion=ahora.date(), estado="EN_PROCESO"))
            l, nuevo = Lote.objects.get_or_create(codigo=codigo, defaults=dict(orden=o, receta=receta, fecha_inicio=ahora - timedelta(hours=horas_atras)))
            return l, nuevo

        # ── Lote A: en proceso (fermentación) con desvío de temperatura ──
        A, nuevo = lote_base("L-2026-0008", "OP-2026-008", 9)
        if nuevo:
            t = A.fecha_inicio
            for s in A.seguimientos.select_related("etapa"):
                n = s.etapa.numero
                if n <= 6:
                    s.fecha_hora_inicio = t; t += timedelta(minutes=s.etapa.tiempo_total_min)
                    s.fecha_hora_fin = t; s.tiempo_trabajo_real_min = s.etapa.tiempo_trabajo_min + random.randint(-5, 12)
                    s.tiempo_espera_real_min = s.etapa.tiempo_espera_min; s.estado = "COMPLETADA"; s.save()
                    s.operarios.add(sup)
                elif n == 7:
                    s.fecha_hora_inicio, s.estado = t, "EN_CURSO"; s.save(); s.operarios.add(sup)
            balances(A, 6)
            lecturas, minutos = [], 0
            while A.fecha_inicio + timedelta(minutes=minutos) <= ahora - timedelta(minutes=5):
                ts = A.fecha_inicio + timedelta(minutes=minutos); h = minutos / 60
                num = 6 if ts < etapas[6].seguimientos.get(lote=A).fecha_hora_fin else 7
                for c, val in (("TEMP", 27 + random.gauss(0, .5)), ("PH", 4.8 - 0.03 * h + random.gauss(0, .04)), ("BRIX", max(12 - 0.8 * h, 3) + random.gauss(0, .15))):
                    lecturas.append(LecturaProceso(lote=A, etapa=etapas[num], variable=var[c], tanque=tq["T-01"], valor_medido=round(val, 2), timestamp=ts, origen="ESP32"))
                minutos += 20
            LecturaProceso.objects.bulk_create(lecturas)
            lec = LecturaProceso.objects.create(lote=A, etapa=etapas[7], variable=var["TEMP"], tanque=tq["T-01"], valor_medido=31.8, origen="ESP32")
            svc_alertas.procesar_lectura(lec)

        # ── Lote B: finalizado, envasado y despachado ──
        B, nuevo = lote_base("L-2026-0007", "OP-2026-007", 60)
        if nuevo:
            t = B.fecha_inicio
            for s in B.seguimientos.select_related("etapa"):
                s.fecha_hora_inicio = t; t += timedelta(minutes=s.etapa.tiempo_total_min); s.fecha_hora_fin = t
                s.tiempo_trabajo_real_min, s.tiempo_espera_real_min, s.estado = s.etapa.tiempo_trabajo_min, s.etapa.tiempo_espera_min, "COMPLETADA"
                s.save()
            balances(B, 12)
            lec = LecturaProceso.objects.create(lote=B, etapa=etapas[9], variable=var["TEMP"], tanque=tq["T-D1"], valor_medido=70.9,
                                                 timestamp=B.fecha_inicio + timedelta(hours=20), origen="ESP32")
            for al in svc_alertas.procesar_lectura(lec):
                al.resolver(sup, True)
            svc_env.cerrar_envasado(B, 238.5, 24, 1.5, sup)
            B.estado = "FINALIZADO"; B.save(update_fields=["estado"])
            svc_cedi.crear_despacho(B)
            B.orden.estado = "FINALIZADA"; B.orden.save()
        self.stdout.write(self.style.SUCCESS("Datos demo cargados. Lotes: L-2026-0008 (en proceso), L-2026-0007 (envasado)."))
