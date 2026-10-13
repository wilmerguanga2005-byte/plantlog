"""Modelos del MES UPEC: EBR, balance de masa, telemetría, envasado y trazabilidad unitaria."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# ───────────────────────── 1. Infraestructura y receta base ─────────────────────────
class AreaPlanta(models.Model):
    nombre = models.CharField("Área de planta", max_length=120, unique=True)
    descripcion = models.TextField("Descripción", blank=True)

    class Meta:
        verbose_name, verbose_name_plural = "Área de planta", "Áreas de planta"

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    nombre = models.CharField(max_length=120)
    codigo = models.CharField("Código", max_length=30, unique=True)
    area = models.ForeignKey(AreaPlanta, on_delete=models.PROTECT, related_name="equipos")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class RecetaProceso(models.Model):
    UNIDADES = [("kg", "kg"), ("L", "L")]
    codigo = models.CharField("Código", max_length=40, unique=True, help_text="Ej. ALM-BEB-REC-01-04")
    nombre = models.CharField(max_length=160)
    producto_final = models.CharField(max_length=160)
    tamano_corrida_base = models.DecimalField("Tamaño de corrida base", max_digits=10, decimal_places=2)
    unidad_medida = models.CharField(max_length=3, choices=UNIDADES, default="kg")
    rendimiento_teorico_pct = models.DecimalField("Rendimiento teórico global (%)", max_digits=5, decimal_places=2, default=100)

    class Meta:
        verbose_name, verbose_name_plural = "Receta de proceso", "Recetas de proceso"

    def __str__(self):
        return f"{self.codigo} – {self.nombre}"

    def duracion_estimada_min(self):
        return sum(e.tiempo_total_min for e in self.etapas.all())

    def rendimiento_encadenado_pct(self):
        """Producto de los rendimientos esperados por etapa (%)."""
        r = Decimal(1)
        for e in self.etapas.all():
            r *= e.rendimiento_esperado_pct / 100
        return (r * 100).quantize(Decimal("0.01"))


class EtapaReceta(models.Model):
    OPERACION, INSPECCION, DEMORA = "OP", "INS", "DEM"
    TIPOS = [(OPERACION, "Operación"), (INSPECCION, "Inspección"), (DEMORA, "Espera / Demora")]  # ASME Y15.3
    receta = models.ForeignKey(RecetaProceso, on_delete=models.CASCADE, related_name="etapas")
    numero = models.PositiveSmallIntegerField("N° de etapa")
    nombre = models.CharField(max_length=160)
    tipo = models.CharField(max_length=3, choices=TIPOS, default=OPERACION)
    equipo = models.ForeignKey(Equipo, null=True, blank=True, on_delete=models.SET_NULL)
    tiempo_trabajo_min = models.PositiveIntegerField("Tiempo de trabajo (min)", default=0)
    tiempo_espera_min = models.PositiveIntegerField("Tiempo de espera (min)", default=0)
    personas_requeridas = models.PositiveSmallIntegerField(default=1)
    rendimiento_esperado_pct = models.DecimalField("Rendimiento esperado (%)", max_digits=5, decimal_places=2, default=100)
    es_pc = models.BooleanField("Punto de Control (PC)", default=False)
    es_pcc = models.BooleanField("Punto Crítico de Control (PCC)", default=False)
    codigo_control = models.CharField("Código PC/PCC", max_length=10, blank=True, help_text="Ej. PC-1, PCC-1")
    especificacion_critica = models.TextField("Especificación crítica / límites", blank=True)

    class Meta:
        ordering = ["receta", "numero"]
        unique_together = [("receta", "numero")]
        verbose_name, verbose_name_plural = "Etapa de receta", "Etapas de receta"

    def __str__(self):
        return f"E{self.numero} {self.nombre}"

    @property
    def tiempo_total_min(self):
        return self.tiempo_trabajo_min + self.tiempo_espera_min

    @property
    def nivel_control(self):
        return "PCC" if self.es_pcc else ("PC" if self.es_pc else "")


# ───────────────────────── 2. EBR y órdenes ─────────────────────────
class OrdenProduccion(models.Model):
    ESTADOS = [("PLANIFICADA", "Planificada"), ("EN_PROCESO", "En proceso"), ("FINALIZADA", "Finalizada")]
    numero = models.CharField("N° de orden", max_length=30, unique=True)
    fecha_programacion = models.DateField()
    estado = models.CharField(max_length=12, choices=ESTADOS, default="PLANIFICADA")

    class Meta:
        verbose_name, verbose_name_plural = "Orden de producción", "Órdenes de producción"

    def __str__(self):
        return self.numero


class Tanque(models.Model):
    TIPOS = [("FERMENTADOR", "Fermentador"), ("DESTILADOR", "Destilador"), ("SEDIMENTACION", "Sedimentación")]
    ESTADOS = [("LIBRE", "Libre"), ("OCUPADO", "Ocupado"), ("LIMPIEZA", "En limpieza"), ("MANTENIMIENTO", "Mantenimiento")]
    codigo = models.CharField(max_length=20, unique=True)
    tipo = models.CharField(max_length=14, choices=TIPOS)
    capacidad = models.DecimalField("Capacidad", max_digits=10, decimal_places=2)
    unidad_capacidad = models.CharField(max_length=2, choices=[("L", "L"), ("kg", "kg")], default="L")
    estado = models.CharField(max_length=14, choices=ESTADOS, default="LIBRE")

    def __str__(self):
        return f"{self.codigo} ({self.get_tipo_display()})"


class Lote(models.Model):
    ESTADOS = [("PLANIFICADO", "Planificado"), ("EN_PROCESO", "En proceso"), ("ENVASADO", "Envasado"),
               ("FINALIZADO", "Finalizado"), ("DETENIDO", "Detenido")]
    codigo = models.CharField("Código de lote", max_length=40, unique=True)
    orden = models.ForeignKey(OrdenProduccion, on_delete=models.PROTECT, related_name="lotes")
    receta = models.ForeignKey(RecetaProceso, on_delete=models.PROTECT, related_name="lotes")
    fecha_inicio = models.DateTimeField("Fecha y minuto de inicio", default=timezone.now)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="EN_PROCESO")

    class Meta:
        ordering = ["-fecha_inicio"]
        verbose_name, verbose_name_plural = "Lote (EBR)", "Lotes (EBR)"

    def __str__(self):
        return self.codigo

    @property
    def duracion_real_min(self):
        fin = self.fecha_fin or timezone.now()
        return max(int((fin - self.fecha_inicio).total_seconds() // 60), 0)

    @property
    def duracion_estimada_min(self):
        return self.receta.duracion_estimada_min()

    @property
    def avance_tiempo_pct(self):
        est = self.duracion_estimada_min
        return min(round(self.duracion_real_min / est * 100), 100) if est else 0

    def etapa_activa(self):
        qs = self.seguimientos.select_related("etapa")
        return qs.filter(estado="EN_CURSO").first() or qs.filter(estado="PENDIENTE").first()


class SeguimientoEtapaLote(models.Model):
    ESTADOS = [("PENDIENTE", "Pendiente"), ("EN_CURSO", "En curso"), ("COMPLETADA", "Completada"), ("DESVIADA", "Desviada")]
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name="seguimientos")
    etapa = models.ForeignKey(EtapaReceta, on_delete=models.PROTECT, related_name="seguimientos")
    fecha_hora_inicio = models.DateTimeField(null=True, blank=True)
    fecha_hora_fin = models.DateTimeField(null=True, blank=True)
    tiempo_trabajo_real_min = models.PositiveIntegerField(default=0)
    tiempo_espera_real_min = models.PositiveIntegerField(default=0)
    operarios = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="etapas_operadas")
    estado = models.CharField(max_length=10, choices=ESTADOS, default="PENDIENTE")

    class Meta:
        ordering = ["lote", "etapa__numero"]
        unique_together = [("lote", "etapa")]
        verbose_name, verbose_name_plural = "Seguimiento de etapa", "Seguimiento de etapas"

    def __str__(self):
        return f"{self.lote.codigo} · {self.etapa}"

    def iniciar(self):
        self.estado, self.fecha_hora_inicio = "EN_CURSO", timezone.now()
        self.save(update_fields=["estado", "fecha_hora_inicio"])

    def completar(self, espera_min=None):
        self.fecha_hora_fin = timezone.now()
        total = int(((self.fecha_hora_fin - (self.fecha_hora_inicio or self.fecha_hora_fin)).total_seconds()) // 60)
        espera = self.etapa.tiempo_espera_min if espera_min is None else espera_min
        self.tiempo_espera_real_min = min(espera, total)
        self.tiempo_trabajo_real_min = total - self.tiempo_espera_real_min
        self.estado = "COMPLETADA"
        self.save()

    @property
    def desviacion_tiempo_min(self):
        return (self.tiempo_trabajo_real_min + self.tiempo_espera_real_min) - self.etapa.tiempo_total_min


# ───────────────────────── 3. Balance de materia ─────────────────────────
class Insumo(models.Model):
    TIPOS = [("MP", "Materia prima"), ("ADI", "Aditivo / levadura"), ("ENV", "Envase / etiqueta")]
    nombre = models.CharField(max_length=140)
    unidad_medida = models.CharField(max_length=10, default="kg")
    tipo = models.CharField(max_length=3, choices=TIPOS)

    def __str__(self):
        return f"{self.nombre} ({self.unidad_medida})"


class BalanceMateriaEtapa(models.Model):
    """Balance dinámico: entra + se incorpora = continúa + merma.  Rendimiento = continúa / (entra + incorpora)."""
    seguimiento_etapa = models.OneToOneField(SeguimientoEtapaLote, on_delete=models.CASCADE, related_name="balance")
    masa_entra_kg = models.DecimalField("Materia que entra (kg)", max_digits=10, decimal_places=3, default=0)
    masa_incorporada_kg = models.DecimalField("Materia que se incorpora (kg)", max_digits=10, decimal_places=3, default=0)
    masa_continua_kg = models.DecimalField("Materia que continúa (kg)", max_digits=10, decimal_places=3, default=0)
    merma_declarada_kg = models.DecimalField("Merma / pérdida declarada (kg)", max_digits=10, decimal_places=3, default=0)
    motivo_merma = models.CharField(max_length=200, blank=True)
    rendimiento_real_pct = models.DecimalField("Rendimiento real (%)", max_digits=6, decimal_places=2, default=0, editable=False)

    class Meta:
        verbose_name, verbose_name_plural = "Balance de materia por etapa", "Balances de materia por etapa"

    @property
    def masa_disponible_kg(self):
        return self.masa_entra_kg + self.masa_incorporada_kg

    @property
    def merma_calculada_kg(self):
        return self.masa_disponible_kg - self.masa_continua_kg

    @property
    def merma_no_declarada_kg(self):
        return self.merma_calculada_kg - self.merma_declarada_kg

    def calcular_rendimiento(self):
        d = self.masa_disponible_kg
        return (self.masa_continua_kg / d * 100).quantize(Decimal("0.01")) if d else Decimal(0)

    def balance_cierra(self, tolerancia_kg=Decimal("0.5")):
        return abs(self.merma_no_declarada_kg) <= tolerancia_kg

    @property
    def desviacion_vs_receta_pct(self):
        return self.rendimiento_real_pct - self.seguimiento_etapa.etapa.rendimiento_esperado_pct

    def save(self, *args, **kwargs):
        self.rendimiento_real_pct = self.calcular_rendimiento()
        super().save(*args, **kwargs)


# ───────────────────────── 4. Telemetría y control estadístico ─────────────────────────
class Variable(models.Model):
    codigo = models.CharField(max_length=10, unique=True, help_text="TEMP, PH, BRIX, PRESION")
    nombre = models.CharField(max_length=80)
    unidad = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.codigo} ({self.unidad})"


class LimiteControl(models.Model):
    TIPOS = [("PC", "Punto de Control"), ("PCC", "Punto Crítico de Control")]
    etapa = models.ForeignKey(EtapaReceta, null=True, blank=True, on_delete=models.CASCADE, related_name="limites")
    tanque = models.ForeignKey(Tanque, null=True, blank=True, on_delete=models.CASCADE, related_name="limites")
    variable = models.ForeignKey(Variable, on_delete=models.CASCADE)
    valor_min_critico = models.DecimalField(max_digits=9, decimal_places=3)
    valor_max_critico = models.DecimalField(max_digits=9, decimal_places=3)
    valor_optimo = models.DecimalField(max_digits=9, decimal_places=3)
    tipo = models.CharField(max_length=3, choices=TIPOS, default="PC")

    class Meta:
        verbose_name, verbose_name_plural = "Límite de control", "Límites de control"

    def clean(self):
        if not (self.etapa or self.tanque):
            raise ValidationError("Defina una etapa o un tanque.")
        if self.valor_min_critico >= self.valor_max_critico:
            raise ValidationError("El mínimo crítico debe ser menor que el máximo crítico.")

    def evaluar(self, valor):
        """Retorna 'BAJO', 'ALTO' o None si está dentro de límites."""
        v = Decimal(str(valor))
        if v < self.valor_min_critico:
            return "BAJO"
        if v > self.valor_max_critico:
            return "ALTO"
        return None

    def __str__(self):
        return f"{self.tipo} {self.variable.codigo} [{self.valor_min_critico}–{self.valor_max_critico}]"


class LecturaProceso(models.Model):
    ORIGENES = [("ESP32", "Sensor ESP32"), ("MANUAL", "Manual")]
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name="lecturas")
    etapa = models.ForeignKey(EtapaReceta, null=True, blank=True, on_delete=models.SET_NULL)
    variable = models.ForeignKey(Variable, on_delete=models.PROTECT)
    tanque = models.ForeignKey(Tanque, null=True, blank=True, on_delete=models.SET_NULL)
    valor_medido = models.DecimalField(max_digits=10, decimal_places=3)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    origen = models.CharField(max_length=6, choices=ORIGENES, default="ESP32")

    class Meta:
        ordering = ["timestamp"]
        indexes = [models.Index(fields=["lote", "variable", "timestamp"])]


# ───────────────────────── 5. Envasado y trazabilidad unitaria ─────────────────────────
class Envasado(models.Model):
    lote = models.OneToOneField(Lote, on_delete=models.CASCADE, related_name="envasado")
    fecha = models.DateTimeField(default=timezone.now)
    volumen_total_obtenido_l = models.DecimalField(max_digits=10, decimal_places=2)
    unidades_terminadas = models.PositiveIntegerField()
    merma_envasado_l = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Envasado {self.lote.codigo}"


class Botella(models.Model):
    ESTADOS = [("ENVASADA", "Envasada"), ("DESPACHADA", "Despachada CEDI"), ("EN_VENTA", "En venta"), ("RETORNADA", "Retornada")]
    codigo_serial_uuid_gs1 = models.CharField("Serial único (UUID/GS1)", max_length=64, unique=True, default=uuid.uuid4)
    envasado = models.ForeignKey(Envasado, on_delete=models.CASCADE, related_name="botellas")
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name="botellas")
    numero_botella = models.PositiveIntegerField()
    qr_code_image = models.ImageField(upload_to="qr/%Y/%m/", blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="ENVASADA")
    hash_autenticidad = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["lote", "numero_botella"]
        unique_together = [("lote", "numero_botella")]

    def __str__(self):
        return f"{self.lote.codigo} #{self.numero_botella}"


class SolicitudAtencion(models.Model):
    TIPOS = [("CONSULTA", "Consulta"), ("RECLAMO", "Reclamo de calidad"), ("RETORNO", "Logística inversa (retorno de envase)")]
    botella = models.ForeignKey(Botella, on_delete=models.CASCADE, related_name="solicitudes")
    tipo = models.CharField(max_length=9, choices=TIPOS)
    nombre = models.CharField(max_length=120)
    contacto = models.CharField("Correo o teléfono", max_length=120)
    mensaje = models.TextField(blank=True)
    creada = models.DateTimeField(auto_now_add=True)


# ───────────────────────── 6. Integración externa y agente IA ─────────────────────────
class DespachoCEDI(models.Model):
    SYNC = [("PENDIENTE", "Pendiente"), ("ENVIADO", "Enviado a Odoo"), ("ERROR", "Error")]
    codigo = models.CharField(max_length=30, unique=True)
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name="despachos")
    cantidad_unidades = models.PositiveIntegerField()
    json_contrato_datos = models.JSONField(default=dict, blank=True)
    estado_sincronizacion_odoo = models.CharField(max_length=10, choices=SYNC, default="PENDIENTE")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name, verbose_name_plural = "Despacho CEDI", "Despachos CEDI"

    def __str__(self):
        return self.codigo


class AlertaAgenteIA(models.Model):
    ESTADOS = [("PENDIENTE", "Pendiente"), ("APROBADO", "Aprobado"), ("RECHAZADO", "Rechazado")]
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name="alertas")
    etapa = models.ForeignKey(EtapaReceta, null=True, on_delete=models.SET_NULL)
    variable = models.ForeignKey(Variable, on_delete=models.PROTECT)
    lectura = models.ForeignKey(LecturaProceso, on_delete=models.CASCADE, related_name="alertas")
    tipo_control = models.CharField(max_length=3, choices=LimiteControl.TIPOS, default="PC")
    sentido = models.CharField(max_length=5, blank=True)  # ALTO / BAJO
    explicacion_causa = models.TextField()
    accion_propuesta = models.TextField()
    estado = models.CharField(max_length=10, choices=ESTADOS, default="PENDIENTE", db_index=True)
    auditado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada"]
        verbose_name, verbose_name_plural = "Alerta del agente IA", "Alertas del agente IA"

    def resolver(self, usuario, aprobar):
        self.estado = "APROBADO" if aprobar else "RECHAZADO"
        self.auditado_por, self.fecha_aprobacion = usuario, timezone.now()
        self.save(update_fields=["estado", "auditado_por", "fecha_aprobacion"])
