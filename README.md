# Portal de gestión multitenant — Edocere

Portal de autogestión para clientes de Edocere: registro, creación de instancias
Moodle, suscripciones y estadísticas de uso.

## Stack

| Componente | Elección | Por qué |
|---|---|---|
| Lenguaje | Python 3.12 | Todo el equipo lo maneja |
| Framework | Django 5.2 LTS | Soporte hasta abril de 2028 |
| Base de datos | MariaDB 11 | Exigido por el cliente |
| Linter y formateador | Ruff | Un solo binario, rápido |
| Análisis estático | mypy + django-stubs | Detecta errores de tipos sin ejecutar |
| Tests | pytest-django | Cobertura medida en cada PR |
| Servidor de aplicación | Gunicorn + systemd | Sin contenedores en el servidor |

## Levantar el proyecto

```bash
git clone <url-del-repo>
cd portal-edocere

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env

docker compose up -d             # levanta MariaDB local
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La aplicación queda en http://localhost:8000 y el panel de administración en
http://localhost:8000/admin/

## Comandos de calidad

```bash
ruff check .            # linter
ruff format .           # formateo
mypy .                  # análisis estático
pytest --cov=.          # tests con cobertura
```

Los cuatro corren en el pipeline en cada pull request. Si alguno falla, el
merge queda bloqueado.

## Metodología de trabajo

### Ramas

`main` está protegida: nadie commitea directo. Cada tarea se trabaja en su
propia rama con el formato `tipo/TICKET-descripcion-corta`.

| Prefijo | Cuándo |
|---|---|
| `feat/` | funcionalidad nueva |
| `fix/` | corrección de un error |
| `chore/` | tareas que no cambian el comportamiento |
| `docs/` | documentación |

Ejemplo: `feat/EDO-12-registro-cliente`

### Pull requests

Todo cambio entra por pull request usando la plantilla del repositorio.
Requisitos para mergear: pipeline en verde y al menos una aprobación de otro
integrante.

La revisión mira cuatro cosas: que el cambio haga lo que dice la tarjeta, que
no rompa tests existentes, que no incluya credenciales, y que las dependencias
nuevas estén anotadas en `requirements.txt`.

### Criterios de "done"

Una tarjeta se mueve a Done cuando el código está mergeado a `main`, el
pipeline pasó, tiene test si toca lógica de negocio, y otro integrante la
revisó. No cuando está programada localmente.

### Deuda técnica

Se registra como tarjetas etiquetadas `deuda-tecnica` en el mismo tablero, no
en un documento aparte. Cada sprint reserva capacidad para bajarla.

### Ceremonias

Sprints de dos semanas, alineados con la reunión quincenal con el cliente.
Planificación al inicio, retrospectiva corta al cierre, sincronización breve
dos veces por semana.

## Estructura

```
config/          configuración del proyecto
  settings/      base, local, test, production
apps/
  core/          endpoint de salud y utilidades comunes
  clientes/      empresas contratantes y usuarios del portal
  planes/        catálogo de planes y suscripciones
  instancias/    instancias Moodle y su aprovisionamiento
  pagos/         pagos y documentos tributarios
  estadisticas/  lectura de métricas desde cada instancia Moodle
docs/            documentación técnica
```

Las apps siguen el modelo de dominio del Design Doc. Cada una agrupa sus
modelos, vistas y tests.
