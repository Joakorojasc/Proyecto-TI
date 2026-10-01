#!/bin/sh
#
# Esto corre cada vez que arranca el contenedor del portal, antes del servidor.
# Deja la base lista sola: espera a MariaDB, aplica las migraciones
# y carga los datos demo.
#
# Así nadie tiene que acordarse de correr migrate a mano después de levantar.

# Corta al primer error. Si las migraciones fallan preferimos enterarnos ahí
# mismo y no que el servidor arranque contra una base a medio hacer.
set -e

echo "==> Esperando a que MariaDB acepte conexiones..."

# El compose ya hace que esperemos el healthcheck de la base, así que esto
# normalmente pasa a la primera. Lo dejamos por si acaso, porque hay un rato en
# que MariaDB ya responde pero todavía está creando el usuario y la base, y ahí
# Django no puede entrar.
intentos=0
until python manage.py shell -c "from django.db import connection; connection.ensure_connection()" 2>/dev/null; do
    intentos=$((intentos + 1))

    # Si en 30 segundos no respondió, algo está mal de verdad. Mejor fallar con
    # un mensaje claro que quedarse colgado sin que nadie sepa por qué.
    if [ "$intentos" -ge 30 ]; then
        echo "ERROR: MariaDB no respondió. Revisa con: docker compose ps"
        exit 1
    fi

    sleep 1
done

echo "==> Aplicando migraciones..."

# --noinput es para que Django no se pare a preguntar algo por teclado, porque
# adentro del contenedor no hay nadie para contestarle.
python manage.py migrate --noinput

# seed_demo es el comando de Sebastián que crea planes, clientes, instancias y
# mediciones de prueba. Siempre los mismos, así todos vemos lo mismo y la demo
# se puede repetir.
#
# Lo dejamos detrás de una variable para poder apagarlo, por si algún día esta
# imagen se usa contra una base con datos reales.
if [ "$CARGAR_DATOS_DEMO" = "1" ]; then
    echo "==> Cargando datos demo..."
    python manage.py seed_demo
fi

echo "==> Listo, levantando el portal."

# Ejecuta el comando que viene del CMD del Dockerfile, que es el runserver.
# Usamos "exec" para que el servidor reemplace a este script y no quede colgando
# arriba. Así el Ctrl+C y el "docker compose down" apagan Django ordenadamente.
exec "$@"
