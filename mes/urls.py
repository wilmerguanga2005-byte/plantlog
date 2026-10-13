from django.urls import path
from . import api_views as api, views

app_name = "mes"
urlpatterns = [
    # Interfaz
    path("", views.dashboard, name="dashboard"),
    path("lotes/", views.lotes_lista, name="lotes"),
    path("lotes/<str:codigo>/", views.lote_control, name="lote_control"),
    path("lotes/<str:codigo>/balance/", views.balance_materia, name="balance"),
    path("lotes/<str:codigo>/envasado/", views.envasado_marbetes, name="envasado"),
    path("lotes/<str:codigo>/marbetes.zip", views.marbetes_zip, name="marbetes_zip"),
    path("agente-ia/", views.alertas_lista, name="alertas"),
    path("cedi/", views.cedi_lista, name="cedi"),
    path("trazabilidad/<str:codigo_serial>/", views.trazabilidad_publica, name="trazabilidad"),  # público
    # API v1
    path("api/v1/telemetria/", api.TelemetriaView.as_view(), name="api_telemetria"),
    path("api/v1/lotes/<str:codigo>/lecturas/", api.LecturasLoteView.as_view(), name="api_lecturas"),
    path("api/v1/lotes/<str:codigo>/prediccion/", api.PrediccionView.as_view(), name="api_prediccion"),
    path("api/v1/lotes/<str:codigo>/cerrar-envasado/", api.CerrarEnvasadoView.as_view(), name="api_cerrar_envasado"),
    path("api/v1/cedi/despacho/crear/", api.CrearDespachoView.as_view(), name="api_despacho_crear"),
    path("api/v1/cedi/despacho/<int:pk>/", api.DespachoCEDIView.as_view(), name="api_despacho"),
    path("api/v1/alertas/pendientes/", api.AlertasPendientesView.as_view(), name="api_alertas_pendientes"),
    path("api/v1/alertas/<int:pk>/aprobar/", api.AprobarAlertaView.as_view(), name="api_alerta_aprobar"),
    path("api/v1/alertas/<int:pk>/descartar/", api.DescartarAlertaView.as_view(), name="api_alerta_descartar"),
]
