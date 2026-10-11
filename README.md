# Portal de gestión multitenant — Edocere

Portal donde los clientes de Edocere se registran, contratan un plan, crean sus
instancias Moodle y ven sus estadísticas de uso. Del otro lado, Rafael tiene una
consola para ver todos los clientes, sus instancias y el estado de los pagos.

Hoy toda esa gestión es manual. La idea del portal es que deje de serlo.

## Stack

Python 3.12 y Django 5.2 LTS, que tiene soporte hasta abril de 2028. La base de
datos es MariaDB porque es la que Edocere ya opera en su servidor.

Para calidad usamos Ruff como linter y formateador, mypy con django-stubs para
revisar tipos, y pytest para los tests.

Docker levanta el entorno completo en cualquier computador del equipo, y es
también la forma en que se entrega la aplicación. El despliegue en el servidor
lo ejecuta Edocere. Pueden correr la imagen tal cual, o instalar el proyecto
directo y usar la configuración de nginx y systemd que quedó en `deploy/`. Esa
carpeta está escrita pero nunca se ejecutó, porque el servidor de pruebas no
llegó a existir.

## Levantarlo en tu computador

La forma corta es con Docker, que levanta el portal y la base de una vez. Solo
necesitas Docker Desktop andando.

```bash
git clone https://github.com/Joakorojasc/Proyecto-TI.git
cd Proyecto-TI
docker compose up --build
```

La primera vez demora unos minutos porque tiene que compilar el driver de
MariaDB. Las siguientes es casi inmediato.

Queda en http://localhost:8000, con las migraciones aplicadas y los datos de
prueba ya cargados. Para entrar al panel de administración necesitas crear un
usuario:

```bash
docker compose exec portal python manage.py createsuperuser
```

Para apagarlo, `docker compose down`. Los datos se conservan. Si quieres partir
de cero, `docker compose down -v`.

### Sin Docker

Si prefieres correr Django directo en tu máquina necesitas Python 3.12 y una
MariaDB. Para la base puedes levantar solo ese contenedor con
`docker compose up -d mariadb`.

```bash
python -m venv .venv
.venv\Scripts\activate.bat

pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

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
ejemplo `feature/registro-cliente`. Los tipos que usamos son `feature/` para
funcionalidad nueva, `fix/` para corregir un error, `chore/` para tareas que no
cambian el comportamiento, `test/` para pruebas, `docs/` para documentación y
`ci/` para cosas del pipeline.

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
negocio, y otra persona lo revisó. No cuando funciona en tu computador. Un hito
del plan se cierra cuando Rafael además lo valida en el entorno de desarrollo,
que es el criterio que acordamos con él.

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
deploy/          configuración de nginx y systemd, opcional para el servidor
docs/            decisiones de arquitectura, despliegue y diagramas
```

Las apps siguen el modelo de dominio del Design Doc. Cada una agrupa sus
modelos, sus vistas y sus tests.

Las seis apps tienen sus modelos, sus vistas y sus tests. `core` además expone
`/health/`, un endpoint que responde si la aplicación está viva y si la base de
datos contesta. Lo consulta el pipeline de entrega continua para comprobar que
el sistema arrancó de verdad, y nginx lo usaría en el servidor.

La configuración está partida en cuatro archivos porque desarrollo y servidor
necesitan cosas opuestas: en tu computador quieres ver el error completo en
pantalla, en el servidor eso mismo sería una filtración. Lo común vive en
`base.py` y cada entorno declara solo sus diferencias.
