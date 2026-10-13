import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
env = lambda k, d=None: os.environ.get(k, d)

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-cambiar-en-produccion")
DEBUG = env("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework",
    "mes.apps.MesConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug", "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages",
        "mes.context_processors.estado_global",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

if env("DB_ENGINE", "mysql") == "sqlite":          # solo para pruebas rápidas
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "es-ec"
TIME_ZONE = "America/Guayaquil"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "mes:dashboard"
LOGOUT_REDIRECT_URL = "login"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}

# --- Parámetros MES ---
IOT_API_KEY = env("IOT_API_KEY", "esp32-upec-clave-demo")      # cabecera X-API-Key
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "http://127.0.0.1:8000")  # base de las URL de los QR
MQTT_BROKER_HOST = env("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_BROKER_PORT = int(env("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = env("MQTT_TOPIC", "upec/planta/telemetria")
ODOO_URL = env("ODOO_URL", "")                                  # sincronización futura
