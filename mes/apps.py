from django.apps import AppConfig

class MesConfig(AppConfig):
    name = "mes"
    verbose_name = "UPEC · Cadena de suministro de almidones y bebidas (MES)"

    def ready(self):
        from . import signals  # noqa
