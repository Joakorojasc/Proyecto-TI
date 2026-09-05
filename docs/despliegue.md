# Despliegue en el servidor de Edocere

El servidor es una máquina Linux en Huawei Cloud, la misma que aloja las
instancias Moodle. El cliente prohíbe el uso de contenedores en el servidor,
así que la aplicación corre directamente sobre el sistema operativo.

## Componentes en el servidor

| Componente | Rol |
|---|---|
| nginx | Recibe el tráfico HTTPS, entrega archivos estáticos y reenvía el resto a Gunicorn |
| Gunicorn | Ejecuta la aplicación Django |
| Tareas programadas | Proceso aparte del portal web. Lee las métricas de cada Moodle y prepara el cobro mensual |
| systemd | Mantiene Gunicorn levantado, lo reinicia si cae, y dispara las tareas programadas |
| MariaDB | Base de datos del portal, separada de las bases de cada instancia Moodle |

Las tareas programadas no corren dentro de Gunicorn. Son un proceso separado que
systemd dispara con un timer, por dos razones: un cálculo mensual que recorre
varias instancias Moodle puede tardar minutos, y bloquear un worker de Gunicorn
todo ese rato dejaría al portal sin capacidad para atender usuarios. Además, si
la tarea falla, no arrastra consigo al sitio web.

La unidad de systemd para esas tareas se escribirá cuando exista acceso al
servidor de staging y se sepa qué comando de gestión ejecutan.

## Instalación inicial

```bash
sudo apt install python3.12-venv nginx mariadb-server default-libmysqlclient-dev
git clone <url-del-repo> /opt/portal-edocere
cd /opt/portal-edocere
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # se completa con los valores reales del entorno
.venv/bin/python manage.py migrate --settings=config.settings.production
.venv/bin/python manage.py collectstatic --settings=config.settings.production
```

Falta instalar la configuración de nginx y de systemd, que se explica en la
sección siguiente, y recién entonces levantar el servicio.

## Archivos de configuración del servidor

La configuración real del servidor vive en el repositorio, en `deploy/`. Se
versiona y se revisa como cualquier otro cambio: no se edita a mano en el
servidor, se edita acá, se aprueba en un pull request y se copia.

| Archivo del repositorio | Dónde se instala en el servidor |
|---|---|
| `deploy/portal.service` | `/etc/systemd/system/portal.service` |
| `deploy/nginx.conf` | `/etc/nginx/sites-available/portal`, enlazado desde `sites-enabled/` |

```bash
sudo cp deploy/portal.service /etc/systemd/system/portal.service
sudo systemctl daemon-reload
sudo systemctl enable --now portal

sudo cp deploy/nginx.conf /etc/nginx/sites-available/portal
sudo ln -s /etc/nginx/sites-available/portal /etc/nginx/sites-enabled/portal
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t` valida la configuración antes de recargar. Si tiene un error, nginx
no se recarga y el sitio sigue respondiendo con la configuración anterior.

Cada archivo lleva sus propios comentarios explicando por qué está configurado
así: por qué Gunicorn escucha solo en `127.0.0.1`, por qué el servicio corre con
un usuario sin privilegios, y por qué nginx entrega los estáticos directamente.

## Actualización

```bash
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate --settings=config.settings.production
.venv/bin/python manage.py collectstatic --noinput --settings=config.settings.production
sudo systemctl restart portal
curl -f http://127.0.0.1:8000/health/
```

El último comando verifica que la aplicación quedó respondiendo. Si falla, el
despliegue se considera fallido.

## Rollback

Para volver a la versión anterior se hace `git checkout` al commit previo y se
reinicia el servicio. El punto delicado son las migraciones: una migración ya
aplicada no se revierte sola.

Regla del proyecto: las migraciones deben ser compatibles hacia atrás dentro de
un mismo sprint. No se borran ni renombran columnas en la misma versión en que
se deja de usarlas; se marcan como obsoletas y se eliminan en la versión
siguiente. Así un rollback de código nunca queda incompatible con el esquema.

## Observabilidad

Los logs de la aplicación salen por la salida estándar en formato JSON y los
recoge systemd, así que se consultan con `journalctl -u portal`.

El endpoint `/health/` verifica que la aplicación responde y que la base de
datos está accesible. Lo consulta el pipeline después de cada despliegue.

Señales mínimas a vigilar: respuestas 5xx, latencia de las vistas del portal,
fallas al gatillar la creación de una instancia, y trabajos de cobro que
terminan en error.
