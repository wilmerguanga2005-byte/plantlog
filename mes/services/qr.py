"""Servicio de marbetes: serial único, hash de autenticidad HMAC y PNG de QR por botella."""
import hashlib, hmac, io, uuid, zipfile

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse

from ..models import Botella


def firmar(serial):
    return hmac.new(settings.SECRET_KEY.encode(), serial.encode(), hashlib.sha256).hexdigest()


def autentica(botella):
    return hmac.compare_digest(botella.hash_autenticidad, firmar(botella.codigo_serial_uuid_gs1))


def url_trazabilidad(serial):
    return settings.PUBLIC_BASE_URL.rstrip("/") + reverse("mes:trazabilidad", args=[serial])


def render_qr_png(url):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return buf.getvalue()


@transaction.atomic
def generar_botellas(envasado):
    """Crea N botellas (idempotente: solo completa las faltantes)."""
    existentes = set(envasado.botellas.values_list("numero_botella", flat=True))
    creadas = []
    for n in range(1, envasado.unidades_terminadas + 1):
        if n in existentes:
            continue
        serial = str(uuid.uuid4())
        b = Botella(codigo_serial_uuid_gs1=serial, envasado=envasado, lote=envasado.lote,
                    numero_botella=n, hash_autenticidad=firmar(serial))
        b.qr_code_image.save(f"{envasado.lote.codigo}_{n:05d}.png", ContentFile(render_qr_png(url_trazabilidad(serial))), save=False)
        b.save()
        creadas.append(b)
    return creadas


def zip_marbetes(lote):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for b in lote.botellas.all():
            if b.qr_code_image:
                z.write(b.qr_code_image.path, f"{lote.codigo}_{b.numero_botella:05d}.png")
    return buf.getvalue()
