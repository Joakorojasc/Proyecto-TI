"""Configuración común a todos los entornos.

Django lee de este archivo todo lo que necesita para arrancar. Lo partimos en
cuatro archivos (base, local, test, production) porque la configuración de
desarrollo y la del servidor no pueden ser la misma: en desarrollo queremos ver
los errores en pantalla, en el servidor eso sería un agujero de seguridad.

Regla del proyecto: todo lo que sea secreto o cambie entre entornos se lee de
variables de entorno con os.environ. Nunca se escribe una credencial acá,
porque este archivo se sube a GitHub.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# BASE_DIR apunta a la raíz del proyecto. Lo usamos para construir rutas sin
# depender de dónde esté instalado el proyecto en cada máquina.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Lee el archivo .env de la raíz y mete sus valores en las variables de entorno,
# para que los os.environ.get de más abajo los encuentren. Sin esta línea el
# .env que cada uno crea en su máquina no lo leería nadie.
#
# No pisa las variables que ya vengan del sistema: en el servidor y en el
# pipeline mandan las del entorno, no un archivo. Si no existe el .env, no pasa
# nada y se usan los valores por defecto.
load_dotenv(BASE_DIR / ".env")

# La SECRET_KEY firma las cookies de sesión y los tokens CSRF. El valor por
# defecto solo sirve para desarrollo; en el servidor se pasa por variable de
# entorno y debe ser distinta.
SECRET_KEY = os.environ.get("SECRET_KEY", "clave-insegura-solo-para-desarrollo")

# DEBUG en True muestra el detalle del error en el navegador, incluida la
# configuración. En el servidor va siempre en False.
DEBUG = os.environ.get("DEBUG", "False") == "True"

# Django rechaza peticiones cuyo dominio no esté en esta lista. Protege contra
# ataques de cabecera Host.
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    # Apps que trae Django. "admin" es el panel de administración que usamos
    # como base de la consola de superadministrador.
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps nuestras. Cada una agrupa una parte del dominio del portal y sigue
    # el modelo de datos del Design Doc.
    "apps.core",  # salud del sistema y utilidades compartidas
    "apps.clientes",  # empresas contratantes y usuarios del portal
    "apps.planes",  # catálogo de planes y suscripciones
    "apps.instancias",  # instancias Moodle y su aprovisionamiento
    "apps.pagos",  # pagos y documentos tributarios
    "apps.estadisticas",  # métricas leídas desde cada instancia Moodle
]

# El middleware es una cadena por la que pasa cada petición antes de llegar a
# la vista, y cada respuesta antes de salir. El orden importa: la sesión tiene
# que resolverse antes que la autenticación, porque la autenticación la usa.
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

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI es el estándar por el que Gunicorn habla con Django en el servidor.
WSGI_APPLICATION = "config.wsgi.application"

# Base de datos del portal. Es una base propia, distinta de las bases de cada
# instancia Moodle: el portal nunca escribe en un Moodle, solo lee estadísticas.
# Usamos MariaDB porque es lo que el cliente ya opera en su servidor.
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.mysql"),
        "NAME": os.environ.get("DB_NAME", "portal_edocere"),
        "USER": os.environ.get("DB_USER", "portal"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        # utf8mb4 es el juego de caracteres que soporta tildes, ñ y emojis.
        # Sin esto, un nombre de empresa con tilde puede romper la inserción.
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

# Reglas que debe cumplir una contraseña al registrarse.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-cl"

# Guardamos todo en hora de Chile porque el cobro se calcula por mes calendario:
# un usuario que entra el 31 a las 23:00 cuenta para ese mes, no para el
# siguiente. Con una zona horaria equivocada la facturación quedaría corrida.
TIME_ZONE = "America/Santiago"
USE_I18N = True

# USE_TZ guarda las fechas en UTC en la base y las convierte al mostrarlas.
# Evita errores en los cambios de horario de verano.
USE_TZ = True

STATIC_URL = "static/"

# collectstatic junta acá todos los archivos estáticos (CSS, JS, imágenes) para
# que nginx los sirva directamente, sin pasar por Django.
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Los logs salen por la salida estándar en formato JSON. En el servidor los
# recoge systemd y se consultan con journalctl. El formato JSON permite
# filtrarlos y, más adelante, mandarlos a una herramienta de monitoreo sin
# tener que reescribir nada.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"nivel":"%(levelname)s","hora":"%(asctime)s",'
            '"modulo":"%(name)s","mensaje":"%(message)s"}'
        }
    },
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["consola"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
