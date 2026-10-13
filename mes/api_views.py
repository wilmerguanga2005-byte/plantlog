from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AlertaAgenteIA, DespachoCEDI, LecturaProceso, Lote, Variable
from .serializers import AlertaSerializer, DespachoSerializer, TelemetriaSerializer
from .services import alertas as svc_alertas, cedi as svc_cedi, envasado as svc_env, prediccion as svc_pred


class IoTKeyOrAuthenticated(permissions.BasePermission):
    """Dispositivos ESP32: cabecera X-API-Key. Personas: sesión autenticada."""
    def has_permission(self, request, view):
        return request.headers.get("X-API-Key") == settings.IOT_API_KEY or bool(request.user and request.user.is_authenticated)


class TelemetriaView(APIView):
    permission_classes = [IoTKeyOrAuthenticated]

    def post(self, request):
        ser = TelemetriaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lectura = ser.save()
        alertas = svc_alertas.procesar_lectura(lectura)
        return Response({"lectura_id": lectura.id, "fuera_de_limites": bool(alertas),
                         "alertas": AlertaSerializer(alertas, many=True).data},
                        status=status.HTTP_201_CREATED)


class LecturasLoteView(APIView):
    """Serie temporal + límites para Chart.js."""
    def get(self, request, codigo):
        lote = get_object_or_404(Lote, codigo=codigo)
        var = get_object_or_404(Variable, codigo=request.GET.get("variable", "TEMP").upper())
        qs = LecturaProceso.objects.filter(lote=lote, variable=var).select_related("etapa", "tanque")
        if request.GET.get("etapa"):
            qs = qs.filter(etapa__numero=request.GET["etapa"])
        lecturas = list(qs.order_by("-timestamp")[:int(request.GET.get("limite", 300))])[::-1]
        ultima = lecturas[-1] if lecturas else None
        activa = lote.etapa_activa()
        etapa_ref = ultima.etapa if ultima else (activa.etapa if activa else None)
        lim = svc_alertas.limite_para(var, etapa_ref, ultima.tanque if ultima else None)
        f = lambda x: float(x)
        return Response({
            "variable": var.codigo, "unidad": var.unidad,
            "puntos": [{"t": timezone.localtime(l.timestamp).strftime("%d/%m %H:%M"), "v": f(l.valor_medido)} for l in lecturas],
            "limites": None if not lim else {"min": f(lim.valor_min_critico), "max": f(lim.valor_max_critico),
                                             "optimo": f(lim.valor_optimo), "tipo": lim.tipo},
        })


class PrediccionView(APIView):
    def get(self, request, codigo):
        lote = get_object_or_404(Lote, codigo=codigo)
        return Response(svc_pred.predecir_rendimiento(lote, request.GET.get("horas", 6)))


class CerrarEnvasadoView(APIView):
    def post(self, request, codigo):
        lote = get_object_or_404(Lote, codigo=codigo)
        try:
            vol, uds, merma = float(request.data["volumen_total_l"]), int(request.data["unidades"]), float(request.data.get("merma_l", 0))
        except (KeyError, ValueError):
            return Response({"detail": "Datos inválidos: volumen_total_l, unidades, merma_l."}, status=400)
        if uds <= 0 or uds > 20000:
            return Response({"detail": "Unidades fuera de rango (1–20000)."}, status=400)
        env, botellas = svc_env.cerrar_envasado(lote, vol, uds, merma, request.user)
        return Response({"lote": lote.codigo, "unidades": env.unidades_terminadas, "botellas_creadas": len(botellas)}, status=201)


class DespachoCEDIView(APIView):
    def get(self, request, pk):
        d = get_object_or_404(DespachoCEDI, pk=pk)
        d.json_contrato_datos = svc_cedi.construir_contrato(d)   # contrato siempre actualizado
        d.save(update_fields=["json_contrato_datos"])
        return Response(DespachoSerializer(d).data)


class CrearDespachoView(APIView):
    def post(self, request):
        lote = get_object_or_404(Lote, codigo=request.data.get("lote_codigo"))
        if not lote.botellas.exists():
            return Response({"detail": "El lote aún no tiene botellas generadas."}, status=400)
        d = svc_cedi.crear_despacho(lote)
        return Response(DespachoSerializer(d).data, status=201)


class _ResolverAlerta(APIView):
    aprobar = True

    def post(self, request, pk):
        a = get_object_or_404(AlertaAgenteIA, pk=pk)
        if a.estado != "PENDIENTE":
            return Response({"detail": f"La alerta ya fue {a.get_estado_display().lower()}."}, status=409)
        a.resolver(request.user, self.aprobar)
        return Response(AlertaSerializer(a).data)


class AprobarAlertaView(_ResolverAlerta):
    aprobar = True


class DescartarAlertaView(_ResolverAlerta):
    aprobar = False


class AlertasPendientesView(APIView):
    def get(self, request):
        return Response({"pendientes": AlertaAgenteIA.objects.filter(estado="PENDIENTE").count()})
