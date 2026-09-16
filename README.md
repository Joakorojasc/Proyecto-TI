# Portal de gestión multitenant — Edocere

Portal donde los clientes de Edocere se registran, contratan un plan, crean sus
instancias Moodle y ven sus estadísticas de uso. Del otro lado, Rafael tiene una
consola para ver todos los clientes, sus instancias y el estado de los pagos.

Hoy toda esa gestión es manual. La idea del portal es que deje de serlo.

## Stack

Python 3.12 y Django 5.2 LTS, que tiene soporte hasta abril de 2028. La base de
datos es MariaDB porque es la que Edocere ya opera en su servidor.

Para calidad usamos Ruff como linter y formateador, mypy con django-stubs para
revisar tipos, y pytest para los tests. En el servidor corre Gunicorn levantado
por systemd, detrás de nginx. Sin contenedores: el cliente no los quiere en su
máquina.

## Levantarlo en tu computador

Necesitas Python 3.12 y, si quieres ver el portal andando, Docker Desktop.

```bash
git clone https://github.com/Joakorojasc/Proyecto-TI.git
cd Proyecto-TI

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate.bat

pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

Después levantas la base y arrancas:

```bash
docker compose up -d             # MariaDB 11 en un contenedor
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Queda en http://localhost:8000, y el panel de administración en
http://localhost:8000/admin/

Para apagar la base, `docker compose down`. Los datos se conservan.

## Comandos de calidad

```bash
ruff check .            # busca errores
ruff format .           # ordena el formato
mypy .                  # revisa los tipos
pytest --cov=.          # tests y cobertura
```

Los cuatro son los mismos que corre el pipeline. Si te pasan acá, te van a
pasar allá.

Los tests necesitan una base de datos. Si no quieres levantar Docker cada vez,
hay un atajo que los corre contra SQLite en memoria:

```bash
export USE_SQLITE=1              # Windows CMD: set "USE_SQLITE=1"
pytest --cov=.
```

En Windows las comillas no son opcionales. Sin ellas la consola guarda el valor
con un espacio al final, el atajo no se activa y pytest intenta conectarse a
MariaDB igual.

En el pipeline esa variable no se define, así que allá los tests corren contra
MariaDB de verdad. Eso es a propósito: SQLite es para iterar rápido, MariaDB es
la que decide.

## Cómo trabajamos

### Ramas

Hay dos ramas permanentes. `dev` es donde se integra lo que va saliendo, y
`main` es lo que se considera estable. Nada se escribe directo en ninguna de las
dos: cada tarea va en su propia rama.

```
tu rama  →  dev  →  main
```

El nombre de la rama lleva el tipo, el ticket y una descripción corta, por
ejemplo `feat/EDO-12-registro-cliente`. Los tipos que usamos son `feat/` para
funcionalidad nueva, `fix/` para corregir un error, `chore/` para tareas que no
cambian el comportamiento, `docs/` para documentación y `ci/` para cosas del
pipeline.

`main` está protegida con un ruleset: exige pull request, el pipeline en verde y
la aprobación de otro integrante. No hay excepciones, tampoco para quien
administra el repositorio.

### Pull requests

Todo cambio entra por pull request. La descripción se rellena sola con la
plantilla del repositorio.

El pipeline corre en cada push y en cada pull request, hacia cualquier rama, así
que te enteras de que algo se rompió al momento y no cuando ya es tarde.

Quien revisa mira cuatro cosas: que el cambio haga lo que dice la tarjeta, que
no rompa tests que ya estaban, que no se haya colado ninguna credencial, y que
si hay dependencias nuevas estén anotadas.

### Cuándo una tarjeta está lista

Cuando el código está en `main`, el pipeline pasó, tiene test si tocó lógica de
negocio, y otra persona lo revisó. No cuando funciona en tu computador.

### Deuda técnica

Va como tarjetas etiquetadas `deuda-tecnica` en el mismo tablero, no en un
documento aparte que nadie abre. Cada sprint deja algo de capacidad para bajarla.

### Ceremonias

Sprints de dos semanas, alineados con la reunión quincenal con el cliente.
Planificación al principio, retrospectiva corta al final, y dos sincronizaciones
breves por semana.

## Cómo está organizado

```
config/
  settings/      base, local, test, production
  urls.py        el mapa de direcciones
apps/
  core/          endpoint de salud y utilidades comunes
  clientes/      empresas contratantes y usuarios del portal
  planes/        catálogo de planes y suscripciones
  instancias/    instancias Moodle y su aprovisionamiento
  pagos/         pagos y documentos tributarios
  estadisticas/  lectura de métricas desde cada instancia Moodle
deploy/          configuración de nginx y systemd del servidor
docs/            decisiones de arquitectura, despliegue y diagramas
```

Las apps siguen el modelo de dominio del Design Doc. Cada una agrupa sus
modelos, sus vistas y sus tests.

Por ahora solo `core` tiene código: un endpoint en `/health/` que responde si la
aplicación está viva y si la base de datos contesta. Lo consultan nginx, el
script de despliegue y el monitoreo. Los modelos de las otras cinco apps se
escriben cuando esté listo el diagrama entidad-relación.

La configuración está partida en cuatro archivos porque desarrollo y servidor
necesitan cosas opuestas: en tu computador quieres ver el error completo en
pantalla, en el servidor eso mismo sería una filtración. Lo común vive en
`base.py` y cada entorno declara solo sus diferencias.
