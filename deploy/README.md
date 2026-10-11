# Configuración de despliegue

Acá está lo que necesita el servidor para correr el portal. Son archivos de
referencia: el equipo los escribió pero nunca los ejecutó, porque el ambiente
de pruebas que Edocere iba a facilitar no llegó y el despliegue productivo
queda a cargo de ellos.

| Archivo | Para qué sirve |
| --- | --- |
| `nginx.conf` | nginx recibe el tráfico de internet, resuelve el HTTPS, entrega los archivos estáticos y le pasa el resto a la aplicación. |
| `portal.service` | Registra el portal como servicio de systemd, para que arranque solo al encender el servidor y se levante de nuevo si se cae. |

## Los dos caminos

El proyecto se puede desplegar de dos formas y las dos funcionan. nginx va
adelante en ambas y su configuración no cambia. Lo que cambia es dónde corre
Gunicorn, que es el proceso que ejecuta el código Python.

**Con Docker.** Es el que proponemos. La imagen ya está construida y el
pipeline de entrega continua la levanta y la verifica en cada merge a `main`,
así que es lo único que podemos respaldar con evidencia. En este caso
`portal.service` hay que adaptarlo para que administre el contenedor en vez de
Gunicorn directo.

**Instalación directa.** Clonar el repositorio en `/opt/portal-edocere`, crear
el entorno virtual e instalar las dependencias. Acá `portal.service` sirve tal
cual está escrito.

## Antes de encender

El archivo `/opt/portal-edocere/.env` tiene que incluir esta línea:

```
DJANGO_SETTINGS_MODULE=config.settings.production
```

Si falta, el portal arranca igual y no avisa nada, pero usa la configuración de
desarrollo: DEBUG activado, sin HTTPS obligatorio y sin cookies seguras. El
resto de las variables está en `.env.example`, en la raíz del repositorio.
