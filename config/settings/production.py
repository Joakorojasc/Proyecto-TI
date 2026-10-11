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

# HSTS le dice al navegador que este dominio se visita siempre por HTTPS,
# aunque el usuario escriba http:// a mano.
#
# Partimos con una hora. El navegador se guarda esta instrucción por el tiempo
# que le indiquemos y no hay forma de retirarla antes, así que si el
# certificado falla en el primer despliegue nadie podría entrar. Una vez que el
# HTTPS lleve unos días estable, subirlo a un año (31536000) es cambiar este
# número. Bajarlo después no tiene efecto en los navegadores que ya recibieron
# la cabecera, por eso conviene partir corto.
#
# El preload queda fuera: inscribe el dominio en una lista incorporada en los
# navegadores y salir de ahí toma meses.
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Impide que el portal se cargue dentro de un iframe de otro sitio, que es como
# se monta un ataque de clickjacking.
X_FRAME_OPTIONS = "DENY"

# Evita que el navegador adivine el tipo de un archivo servido, técnica usada
# para colar scripts disfrazados de imagen.
SECURE_CONTENT_TYPE_NOSNIFF = True
