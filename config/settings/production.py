"""Entorno de staging y producción en el servidor de Edocere.

Todas estas opciones son de seguridad y solo tienen sentido cuando hay HTTPS.
Por eso no están en base.py: en desarrollo romperían el acceso por localhost.
"""

from .base import *  # noqa: F403

DEBUG = False

# Redirige cualquier petición HTTP a HTTPS.
SECURE_SSL_REDIRECT = True

# Las cookies de sesión y de CSRF solo viajan por conexiones cifradas, para que
# nadie las capture en una red intermedia.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS le dice al navegador que este dominio se visita siempre por HTTPS
# durante un año, aunque el usuario escriba http:// a mano.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Impide que el portal se cargue dentro de un iframe de otro sitio, que es como
# se monta un ataque de clickjacking.
X_FRAME_OPTIONS = "DENY"

# Evita que el navegador adivine el tipo de un archivo servido, técnica usada
# para colar scripts disfrazados de imagen.
SECURE_CONTENT_TYPE_NOSNIFF = True
