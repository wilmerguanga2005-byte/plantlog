"""Puente MQTT -> servicio de ingesta. Topic: upec/planta/telemetria (payload = mismo JSON de la API REST)."""
import json
from django.conf import settings
from django.core.management.base import BaseCommand
from mes.serializers import TelemetriaSerializer
from mes.services.alertas import procesar_lectura


class Command(BaseCommand):
    help = "Suscribe al broker MQTT y registra lecturas de los ESP32."

    def handle(self, *a, **o):
        import paho.mqtt.client as mqtt

        def on_message(client, userdata, msg):
            try:
                ser = TelemetriaSerializer(data=json.loads(msg.payload))
                ser.is_valid(raise_exception=True)
                lect = ser.save()
                for al in procesar_lectura(lect):
                    self.stdout.write(self.style.WARNING(f"ALERTA {al.tipo_control} {al.variable.codigo} lote {al.lote.codigo}"))
            except Exception as e:  # no tumbar el puente por un mensaje malformado
                self.stderr.write(f"Mensaje descartado: {e}")

        c = mqtt.Client()
        c.on_connect = lambda cl, *x: cl.subscribe(settings.MQTT_TOPIC)
        c.on_message = on_message
        c.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT)
        self.stdout.write(f"Escuchando {settings.MQTT_TOPIC} en {settings.MQTT_BROKER_HOST}…")
        c.loop_forever()
