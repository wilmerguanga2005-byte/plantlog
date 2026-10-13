from django.contrib import admin
from . import models as m

class EtapaInline(admin.TabularInline):
    model, extra = m.EtapaReceta, 0

@admin.register(m.RecetaProceso)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "producto_final", "tamano_corrida_base", "rendimiento_teorico_pct")
    inlines = [EtapaInline]

@admin.register(m.SeguimientoEtapaLote)
class SegAdmin(admin.ModelAdmin):
    list_display = ("lote", "etapa", "estado", "fecha_hora_inicio", "fecha_hora_fin")
    list_filter = ("estado", "lote")

@admin.register(m.LimiteControl)
class LimAdmin(admin.ModelAdmin):
    list_display = ("tipo", "variable", "etapa", "tanque", "valor_min_critico", "valor_optimo", "valor_max_critico")

@admin.register(m.AlertaAgenteIA)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ("lote", "variable", "tipo_control", "estado", "auditado_por", "creada")
    list_filter = ("estado", "tipo_control")

for mod in (m.AreaPlanta, m.Equipo, m.OrdenProduccion, m.Lote, m.Tanque, m.Insumo, m.BalanceMateriaEtapa,
            m.Variable, m.LecturaProceso, m.Envasado, m.Botella, m.DespachoCEDI, m.SolicitudAtencion):
    admin.site.register(mod)
