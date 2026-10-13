from django.utils import timezone
from rest_framework import serializers

from .models import (AlertaAgenteIA, DespachoCEDI, LecturaProceso, Lote, Tanque, Variable)


class TelemetriaSerializer(serializers.Serializer):
    """Payload del ESP32: etapa_id = número de etapa (1..N) dentro de la receta del lote."""
    lote_codigo = serializers.CharField()
    etapa_id = serializers.IntegerField(min_value=1)
    tanque_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    variable = serializers.CharField()
    valor = serializers.DecimalField(max_digits=10, decimal_places=3)
    origen = serializers.ChoiceField(choices=["ESP32", "MANUAL"], default="ESP32")
    timestamp = serializers.DateTimeField(required=False)

    def validate(self, d):
        try:
            lote = Lote.objects.select_related("receta").get(codigo=d["lote_codigo"])
        except Lote.DoesNotExist:
            raise serializers.ValidationError({"lote_codigo": "Lote inexistente."})
        etapa = lote.receta.etapas.filter(numero=d["etapa_id"]).first()
        if not etapa:
            raise serializers.ValidationError({"etapa_id": "La receta del lote no tiene esa etapa."})
        try:
            variable = Variable.objects.get(codigo=d["variable"].upper())
        except Variable.DoesNotExist:
            raise serializers.ValidationError({"variable": "Variable no registrada."})
        tanque = None
        if d.get("tanque_id"):
            tanque = Tanque.objects.filter(codigo=d["tanque_id"]).first()
            if not tanque:
                raise serializers.ValidationError({"tanque_id": "Tanque inexistente."})
        d.update(lote=lote, etapa=etapa, variable_obj=variable, tanque=tanque)
        return d

    def create(self, d):
        return LecturaProceso.objects.create(
            lote=d["lote"], etapa=d["etapa"], variable=d["variable_obj"], tanque=d["tanque"],
            valor_medido=d["valor"], origen=d["origen"], timestamp=d.get("timestamp") or timezone.now())


class AlertaSerializer(serializers.ModelSerializer):
    variable = serializers.CharField(source="variable.codigo")
    lectura_valor = serializers.DecimalField(source="lectura.valor_medido", max_digits=10, decimal_places=3)
    lote = serializers.CharField(source="lote.codigo")
    etapa_nombre = serializers.CharField(source="etapa.nombre", default=None)

    class Meta:
        model = AlertaAgenteIA
        fields = ["id", "lote", "etapa_nombre", "variable", "lectura_valor", "tipo_control", "sentido",
                  "explicacion_causa", "accion_propuesta", "estado", "fecha_aprobacion", "creada"]


class DespachoSerializer(serializers.ModelSerializer):
    lote = serializers.CharField(source="lote.codigo")

    class Meta:
        model = DespachoCEDI
        fields = ["id", "codigo", "lote", "cantidad_unidades", "estado_sincronizacion_odoo", "json_contrato_datos"]
