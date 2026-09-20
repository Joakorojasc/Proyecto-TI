# Guía del repositorio

Esta guía es para el equipo. Explica qué hay en el repositorio, por qué está
así, y cómo trabajar sin romper nada.

Si es tu primer día en el proyecto, lee las dos primeras secciones y salta
directo a "Levantarlo en tu computador". El resto lo puedes leer después.

---

## Qué estamos construyendo

Edocere es una consultora chilena que opera Moodle como servicio. Tienen varias
instancias de Moodle corriendo en un mismo servidor Linux en Huawei Cloud, cada
cliente con su propio sitio y su propia base de datos.

El problema que nos trajeron es operacional: hoy toda la gestión comercial es
manual, con formularios, WhatsApp y planillas. Eso les topa el crecimiento en
unas veinte instancias. Tienen dos clientes y quieren llegar a doscientos o
trescientos sin crecer el equipo.

Nosotros construimos el portal que reemplaza esa gestión manual. Tiene dos
roles:

- **Cliente**: se registra, elige un plan, crea sus instancias Moodle, ve sus
  estadísticas de uso y paga.
- **Superadministrador**: ve todos los clientes e instancias, métricas globales,
  estado de pagos e historial de facturación. Puede dar de alta y baja, crear
  instancias a mano e impersonar a un cliente.

Un cliente puede tener muchas instancias. Una instancia pertenece a un solo
cliente.

**Lo que no hacemos.** Hay otros dos grupos trabajando en paralelo: uno hace el
script que crea instancias Moodle automáticamente y otro el de actualización
masiva. Nuestro portal solo le manda una petición al primero para que se
dispare. No tocamos esos scripts.

**El objetivo de esta etapa es un MVP en staging validado, no producción.** El
cliente fue explícito en eso.

---

## El hilo conductor: el viaje de un cambio

El repositorio está organizado en seis grupos, y cada grupo es una etapa del
camino que recorre un cambio desde que alguien lo escribe hasta que atiende a un
cliente de Edocere.

```
1. Configuración  →  cómo arranca Django
2. Dominio        →  dónde vive el negocio
3. Calidad        →  cómo se verifica lo que escribiste
4. Automatización →  quién lo verifica sin que se lo pidan
5. Despliegue     →  cómo llega al servidor
6. Documentación  →  por qué está así
```

El resto de esta guía sigue ese orden.

---

## Levantarlo en tu computador

La forma corta es con Docker, que levanta el portal y la base de una vez. Solo
necesitas **Docker Desktop** andando.

```bash
git clone https://github.com/Joakorojasc/Proyecto-TI.git
cd Proyecto-TI
docker compose up --build
```

La primera vez demora unos minutos porque compila el driver de MariaDB. Las
siguientes es casi inmediato.

Queda en http://localhost:8000, el panel de administración en `/admin/` y el
endpoint de salud en `/health/`. Las migraciones vienen aplicadas y los datos de
prueba cargados, porque de eso se encarga el `entrypoint.sh`.

Para entrar al panel necesitas crear un usuario:

```bash
docker compose exec portal python manage.py createsuperuser
```

Para apagarlo, `docker compose down`. Los datos se conservan. Si quieres partir
de cero, `docker compose down -v`.

### Sin Docker

Si prefieres correr Django directo en tu máquina necesitas **Python 3.12**. La
base la puedes levantar sola con `docker compose up -d mariadb`.

```bash
python -m venv .venv
.venv\Scripts\activate.bat

pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Esos dos comandos del entorno virtual son distintos y hacen cosas distintas: el
primero **crea** la carpeta `.venv` con un Python aislado, el segundo la
**llena** con las librerías. `requirements.txt` es solo una lista de texto, no
crea nada.

### Correr los tests sin base de datos

Los tests corren igual, contra una base SQLite en memoria:

```bash
export USE_SQLITE=1              # Windows CMD: set "USE_SQLITE=1"
pytest --cov=.
```

**En Windows las comillas no son opcionales.** Sin ellas la consola guarda el
valor con un espacio al final, el atajo no se activa, y pytest intenta
conectarse a MariaDB. El síntoma es un error de conexión al `127.0.0.1`.

Ese atajo aplica solo a los tests. Para `runserver` y `migrate` sí necesitas la
base de datos.

---

## Etapa 1 — Configuración

Todo lo que decide cómo arranca Django.

### `manage.py`

Es el comando con el que se le habla a Django. **No se modifica nunca.**

Solo hace tres cosas: elige el archivo de configuración, importa el despachador
de Django y le pasa lo que escribiste. Los comandos en sí (`runserver`,
`migrate`, `check`) no están acá, están dentro de Django.

Los que vas a usar:

```bash
python manage.py runserver         # levanta el portal
python manage.py makemigrations    # genera migraciones tras cambiar un modelo
python manage.py migrate           # aplica esos cambios a la base
python manage.py createsuperuser   # crea un usuario administrador
python manage.py check             # valida la configuración
```

### `config/settings/` — cuatro archivos, no uno

Django trae un solo `settings.py` por defecto. Lo partimos en cuatro porque el
mismo código corre en lugares con necesidades opuestas.

| Archivo | Dónde se usa |
|---|---|
| `base.py` | lo común a todos, se hereda siempre |
| `local.py` | el computador de cada integrante |
| `test.py` | el pipeline y los tests |
| `production.py` | el servidor de Edocere |

Los tres últimos empiezan con `from .base import *` y encima cambian solo lo que
debe ser distinto.

**El ejemplo que lo explica todo es `DEBUG`.** En local va en `True`, porque
cuando algo falla queremos ver el error completo en pantalla. En el servidor va
en `False`, porque eso mismo sería filtrarle la configuración interna a
cualquiera que provoque un error. Con un solo archivo habría que elegir uno de
los dos.

`production.py` agrega además seis opciones de seguridad que **solo tienen
sentido con HTTPS**: redirección forzada a HTTPS, cookies de sesión y CSRF
cifradas, HSTS por un año, bloqueo de iframes contra clickjacking y prohibición
de que el navegador adivine tipos de archivo. Si estuvieran en `base.py` no
podríamos ni desarrollar: nos mandarían de `http://localhost` a un HTTPS que en
nuestras máquinas no existe.

`test.py` tiene dos particularidades. El interruptor de SQLite que ya viste, y
un cifrado de contraseñas deliberadamente débil (MD5). Django normalmente cifra
las contraseñas con un algoritmo lento a propósito, para que a un atacante le
cueste años probar combinaciones. En los tests eso no aporta nada y hace que
cada usuario de prueba tarde una eternidad en crearse.

**Nunca escribas una credencial en estos archivos.** Todo lo secreto se lee de
variables de entorno, que vienen del archivo `.env` de cada uno. Ese `.env` está
en el `.gitignore` y no se sube jamás. `.env.example` es la plantilla que sí se
sube, para que sepas qué variables necesitas.

### `config/urls.py`

Es el router: recibe una dirección y decide qué código la atiende.

```python
urlpatterns = [
    path("admin/", admin.site.urls),          # el panel de Django
    path("", include("apps.core.urls")),      # lo que expone core
]
```

### `config/wsgi.py`

Es el traductor entre el servidor y Django. Gunicorn sabe recibir peticiones de
internet pero no sabe nada de tu portal; Django sabe qué responder pero no sabe
recibir peticiones. WSGI es el estándar que los conecta.

```
petición → Gunicorn → wsgi.py → Django → respuesta
```

`asgi.py` es la versión asíncrona del mismo archivo. Viene con Django y no lo
usamos.

---

## Etapa 2 — El dominio

"Dominio" significa el negocio: el mundo real que el sistema representa. Clientes,
planes, instancias, pagos y estadísticas son conceptos que existirían aunque el
software no existiera.

Por eso agrupamos por dominio y no por tipo técnico. Todo lo de pagos vive
junto, en vez de tener una carpeta de "vistas" y otra de "modelos" con pedazos
de todo mezclados.

| App | Qué le corresponde |
|---|---|
| `core` | salud del sistema y utilidades compartidas |
| `clientes` | empresas contratantes y usuarios del portal |
| `planes` | catálogo de planes y suscripciones |
| `instancias` | instancias Moodle y su aprovisionamiento |
| `pagos` | pagos y documentos tributarios |
| `estadisticas` | métricas leídas desde cada instancia Moodle |

`core` es la excepción: esa no es de negocio, es técnica.

### Estado actual

Las seis apps ya tienen sus modelos, con las migraciones generadas. Las nueve
entidades del diagrama entidad-relación quedaron repartidas así:

| App | Entidades |
|---|---|
| `clientes` | Cliente, UsuarioPortal |
| `planes` | Plan, Suscripcion |
| `instancias` | InstanciaMoodle |
| `pagos` | Pago, DocumentoTributario |
| `estadisticas` | MedicionUsoMensual |
| `core` | Bitacora |

Si en algún momento el diagrama cambia y aparece una entidad sin app, o una app
sin entidad, hay que ajustar una de las dos cosas. Esa es la costura entre el
modelo de datos y la estructura del código.

Lo que todavía no existe son las vistas y las pantallas. Los modelos guardan
datos, pero nadie los muestra ni los edita fuera del panel de administración.

### Dónde se declaran las apps

En `config/settings/base.py`, en la lista `INSTALLED_APPS`. **Ese es el que
manda**: si una carpeta no está en esa lista, Django la ignora aunque exista en
el disco.

Ahí también están las seis apps que trae Django. Vale la pena saber que existen,
porque explican por qué el proyecto ya tiene login, usuarios y un panel de
administración sin haber escrito una línea para eso:

- `django.contrib.admin` — el panel de administración, que es la base de la
  consola del superadministrador
- `django.contrib.auth` — usuarios, contraseñas y permisos
- `django.contrib.sessions` — mantiene la sesión iniciada entre páginas
- `django.contrib.contenttypes`, `messages`, `staticfiles` — infraestructura
  interna

### El endpoint de salud

Es la única vista que existe por ahora. Está en `apps/core/views.py`:

```python
def health(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        base_datos = "ok"
        estado = 200
    except Exception:
        base_datos = "sin conexion"
        estado = 503

    return JsonResponse(
        {"estado": "ok" if estado == 200 else "degradado", "base_datos": base_datos},
        status=estado,
    )
```

Entras a `/health/` y responde:

```json
{"estado": "ok", "base_datos": "ok"}
```

Dice dos cosas distintas: que la aplicación está viva, y que **además** se
conectó a la base de datos y ejecutó una consulta. Ese `SELECT 1` es la consulta
más simple que existe; no lee datos de nadie, solo comprueba que la base
responde.

**Por qué importa:** un programa puede estar vivo pero inútil. El proceso corre,
el puerto responde, pero la base se cayó y cualquiera que entre ve un error. Una
revisión del tipo "¿está abierto el puerto?" diría que todo bien.

Y tiene tres consumidores reales, no es decoración:

1. **El script de despliegue** termina con `curl -f http://127.0.0.1:8000/health/`.
   Ese `-f` hace que el comando falle si la respuesta no es exitosa, así que el
   despliegue se declara bueno o malo según lo que responda este endpoint.
2. **nginx** lo tiene configurado para no registrarlo en el log de accesos,
   porque el monitoreo lo consulta cada pocos segundos.
3. **El monitoreo**: si MariaDB se cae de madrugada, esto empieza a devolver 503.

---

## Etapa 3 — Calidad

Cuatro herramientas, cada una responde una pregunta distinta. Ninguna reemplaza
a las otras.

| Herramienta | Pregunta que responde |
|---|---|
| **Ruff** | ¿está bien escrito? |
| **mypy** | ¿los tipos calzan? |
| **pytest** | ¿hace lo que dice? |
| **coverage** | ¿cuánto de esto probé? |

**Ruff** lee el código sin ejecutarlo. Atrapa imports sin usar, variables que no
existen, comparaciones que siempre dan falso. Y además formatea: comillas,
espacios, orden de los imports. Sin un formateador, cada uno escribe con su
estilo y los pull requests se llenan de cambios que no son cambios reales.

**mypy** verifica los tipos antes de ejecutar nada:

```python
def sumar(a: int, b: int) -> int:
    return a + b

sumar("hola", 5)     # mypy avisa acá; sin él, explota en producción
```

Nuestra configuración tiene `disallow_untyped_defs = true`, o sea que **toda
función debe declarar sus tipos**. Por eso el endpoint de salud está escrito
`def health(request: HttpRequest) -> JsonResponse:`.

`django-stubs` es lo que le enseña a mypy cómo funciona Django, para que
entienda qué devuelve un `objects.filter()`.

**pytest** ejecuta pedazos del código y verifica el resultado. **coverage** no es
una herramienta aparte: acompaña a pytest y anota qué líneas se ejecutaron.

### Los comandos

```bash
ruff check .            # errores
ruff format .           # formato
mypy .                  # tipos
pytest --cov=.          # tests y cobertura
```

`ruff format .` te arregla el formato. En el pipeline se usa
`ruff format --check .`, que no modifica nada y solo falla si algo está
desalineado.

### `conftest.py`

Guarda cosas que muchos tests van a necesitar. pytest lo carga solo, sin que
nadie lo importe, y por eso el archivo tiene que llamarse así exactamente.

Adentro hay dos **fixtures**: funciones que preparan algo para un test.

```python
@pytest.fixture
def usuario_cliente(db: None) -> User:
    return User.objects.create_user(
        username="cliente-demo",
        email="contacto@cliente-demo.cl",
        password="clave-de-prueba",
    )
```

Se usan por nombre. Un test futuro se escribiría así:

```python
def test_cliente_no_ve_instancias_de_otro(usuario_cliente):
    ...
```

pytest ve el parámetro `usuario_cliente`, busca la fixture con ese nombre, la
ejecuta y le pasa el usuario ya creado. Tú nunca la llamas.

Las dos que hay —`superadmin` y `usuario_cliente`— están preparadas para probar
lo más importante de un sistema multitenant: **que un cliente nunca vea los
datos de otro**. Hoy no las usa nadie, porque los dos tests que existen son del
endpoint de salud.

### Sobre la cobertura

Está en 84%, y ese número hoy dice poco: la mayoría de lo que mide son archivos
de configuración y el esqueleto vacío de las apps, que cuentan como cubiertas
solo porque Django las importa al arrancar.

El dato relevante es que el único archivo con lógica real, `apps/core/views.py`,
está al 75%. Las tres líneas que faltan son el camino de falla del endpoint de
salud, o sea qué pasa cuando la base de datos se cae.

No manipulamos la configuración de coverage para que el número se vea mejor. El
84% es el que reporta el pipeline y se defiende por lo que es.

### `pyproject.toml`

Configura las cuatro herramientas en un solo archivo, cada una en su sección:
`[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, `[tool.coverage.run]`.
Cada herramienta lee solo lo suyo.

Antes cada una traía su propio archivo y terminabas con cinco sueltos en la
raíz. Desde 2016 el estándar de Python es juntarlos acá.

---

## Etapa 4 — Automatización

### `.github/workflows/ci.yml`

Es el pipeline: un robot que corre las verificaciones por ti, en un computador de
GitHub, cada vez que subes código.

Se dispara en **cada push a cualquier rama** y en **cada pull request**. Así te
enteras al momento de que rompiste algo, sin esperar a abrir nada.

Qué hace, en orden:

1. Enciende una máquina Ubuntu limpia y levanta un contenedor MariaDB 11 al lado
2. Instala Python 3.12 y las dependencias de ambos requirements
3. Corre **Ruff** (`check` y `format --check`)
4. Corre **mypy**
5. Verifica que **no falten migraciones** — falla si alguien cambió un modelo y
   olvidó generarlas
6. Corre **`manage.py check`**
7. Corre los **tests con cobertura** contra MariaDB de verdad
8. Publica el **reporte de cobertura** como archivo descargable

Todo en aproximadamente un minuto.

**Por qué importa que la máquina sea limpia:** elimina el "en mi computador
funcionaba". Si acá pasa y en un Ubuntu recién encendido falla, es que tu código
dependía de algo que solo tú tienes instalado.

Y una ironía sana: el cliente prohibió contenedores **en el servidor**, pero en
el pipeline son ideales, porque cada ejecución arranca con una base de datos
virgen y desechable.

### `.github/pull_request_template.md`

Es el texto que aparece por defecto en la descripción de cada pull request.
Siempre el mismo, y no obliga a nada: puedes borrarlo y escribir lo que quieras.

---

## Etapa 5 — Despliegue

Acá está la parte que todavía no se ha ejecutado, porque **no tenemos acceso al
servidor**. Depende de una coordinación del cliente sin fecha comprometida. Los
archivos están listos para cuando llegue.

### El problema que resuelven

El servidor es una máquina Linux siempre encendida, sin pantalla ni escritorio.
Se entra por SSH, que es una consola de texto a través de internet.

Si te conectas y escribes `gunicorn ...` a mano, pasan tres cosas malas: el
portal se muere al cerrar la sesión, nadie lo levanta si se cae, y no vuelve
solo si el servidor se reinicia.

### `deploy/portal.service`

Es un archivo de instrucciones para **systemd**, que es el gestor de servicios
de Linux. No es una consola: es un programa que viene dentro de Linux y está
corriendo siempre, encargándose de que otros programas estén vivos. El
equivalente son los "Servicios" de Windows.

En el servidor de Edocere systemd ya está trabajando: es el que mantiene vivos a
MariaDB y a Apache para los Moodle. Solo hay que decirle que además se haga cargo
del portal.

Las líneas que importan:

```
After=network.target mariadb.service    no arranques antes que la red y la base
User=portal                             corre con un usuario sin privilegios
ExecStart=.../gunicorn config.wsgi...   este es el comando a ejecutar
Restart=always                          si se cae, levántalo de nuevo
NoNewPrivileges=true                    no puede escalar permisos
```

`User=portal` es una decisión de seguridad importante: si alguien lograra
ejecutar código a través del portal, **no tendría permisos de administrador en
esa máquina** — donde también viven las instancias Moodle de los otros clientes.

### `deploy/nginx.conf`

nginx va delante de Gunicorn y hace tres cosas que Django no debería hacer:

- **Descifra el HTTPS.** El candado del navegador es cosa suya.
- **Entrega las imágenes, el CSS y el JavaScript** directo desde disco, sin
  molestar a Python. Es mucho más rápido y libera procesos de Gunicorn.
- **Le pasa el resto a Gunicorn**, que escucha solo en `127.0.0.1` y por lo tanto
  nunca queda expuesto directamente a internet.

Tiene además una regla para no registrar `/health/` en el log de accesos.

### Gunicorn

Es lo que ejecuta la aplicación **en el servidor**. Levanta tres procesos en
paralelo para atender a varias personas a la vez.

```
Tu computador  →  python manage.py runserver
Servidor       →  gunicorn config.wsgi:application
```

**No son lo mismo y nunca se encuentran.** `runserver` es una herramienta de
desarrollo: cómoda para programar, pero lenta y no endurecida para internet. La
documentación de Django dice explícitamente que no se use en producción. En tu
computador Gunicorn nunca se ejecuta, aunque esté instalado.

### La cadena completa

```
Internet
   ↓  puerto 443, HTTPS
nginx          descifra y entrega los estáticos
   ↓  reenvía a 127.0.0.1:8000
Gunicorn       ejecuta la aplicación, 3 procesos
   ↓
Django         nuestro código
   ↓
MariaDB        los datos

systemd, por debajo, mantiene todo vivo
```

En una frase: **nginx recibe y protege, Gunicorn ejecuta, systemd vigila,
MariaDB guarda.**

### `docker-compose.yml`, `Dockerfile` y `entrypoint.sh`

Los tres arman el entorno de desarrollo y pruebas. El `Dockerfile` construye la
imagen del portal, el `entrypoint.sh` espera a la base y aplica migraciones y
datos demo al arrancar, y el `docker-compose.yml` conecta el portal con
MariaDB 11 y los levanta juntos.

**Docker solo acá, nunca en el servidor**, que es una restricción explícita del
cliente. En el servidor MariaDB está instalada directamente sobre el sistema y
Gunicorn lo levanta systemd.

---

## Etapa 6 — Documentación

### `docs/decisiones/`

Son **ADR**, *Architecture Decision Records*: un archivo por decisión
importante, con contexto, alternativas evaluadas, qué se eligió y qué
consecuencias trae. Sirven para que dentro de un año alguien entienda *por qué*
está así, en vez de solo *cómo*.

**ADR 001 — por qué Django y no Laravel.** La razón no es técnica sino de
capacidad de revisión: los cinco leemos Python con soltura y ninguno conoce
Laravel. Con IA generando parte del código, el trabajo se desplaza de escribir a
revisar, y un equipo que no domina el framework aprueba pull requests sin
entender qué aprobó.

También descarta microservicios (el dominio no lo justifica: pocas entidades y
un solo servidor) y un frontend separado (obliga a mantener dos aplicaciones y
un contrato entre ellas, cuando el MVP son pocas pantallas).

**ADR 002 — por qué integración continua ahora y entrega continua después.**
Separarlas permite tener la mitad valiosa funcionando hoy sin depender de un
acceso al servidor que no controlamos. Automatizar el despliegue antes de tener
el servidor habría significado escribir un pipeline que no podemos probar, que
es peor que no tenerlo.

### `docs/despliegue.md`

Instalación, actualización, rollback y observabilidad. Incluye la tabla de qué
archivo del repositorio va a qué ruta del servidor.

La regla de rollback que hay que respetar: **las migraciones deben ser
compatibles hacia atrás dentro de un mismo sprint.** No se borran ni renombran
columnas en la misma versión en que se dejan de usar; se marcan como obsoletas y
se eliminan en la siguiente. Así un rollback de código nunca queda incompatible
con el esquema de la base.

### Los dos diagramas

Están en formato Mermaid, o sea **texto plano, no imágenes**. Eso es a propósito:
se revisan en un pull request igual que el código y no se desactualizan sin que
nadie lo note.

- **`diagrama-1-arquitectura.mmd`** — qué componentes tiene el sistema y con
  quién habla cada uno. Incluye una zona explícita de "Fuera de nuestro alcance"
  con las instancias Moodle, la capa de aprovisionamiento del otro grupo, la
  pasarela de pagos y el proveedor de DTE.
- **`diagrama-2-infraestructura.mmd`** — dónde corre cada cosa y cómo llega el
  código desde un computador hasta el servidor.

Los nombres de los componentes tienen que ser **idénticos en ambos diagramas y
en el texto**. Si cambias uno, cámbialo en los dos.

---

## Cómo trabajamos

### Ramas

Hay dos ramas permanentes:

```
tu rama  →  dev  →  main
```

`dev` es donde se integra lo que va saliendo. `main` es lo que se considera
estable. **Nada se escribe directo en ninguna de las dos.**

El nombre de la rama lleva el tipo, el ticket y una descripción corta:

```
feat/EDO-12-registro-cliente
```

| Prefijo | Cuándo |
|---|---|
| `feat/` | funcionalidad nueva |
| `fix/` | corregir un error |
| `chore/` | tareas que no cambian el comportamiento |
| `docs/` | documentación |
| `ci/` | cosas del pipeline |

### Pull requests

`main` está protegida con un ruleset que exige tres cosas: pull request, el
pipeline en verde, y **la aprobación de otro integrante**. Sin excepciones,
tampoco para quien administra el repositorio.

Nadie puede aprobar su propio pull request. Eso es de GitHub y es
intencional.

Quien revisa mira cuatro cosas: que el cambio haga lo que dice, que no rompa
tests existentes, que no se haya colado ninguna credencial, y que las
dependencias nuevas estén anotadas.

### Cuándo una tarjeta está lista

Cuando el código está en `main`, el pipeline pasó, tiene test si tocó lógica de
negocio, y otra persona lo revisó. **No cuando funciona en tu computador.**

### Deuda técnica

Va como tarjetas etiquetadas `deuda-tecnica` en el mismo tablero, no en un
documento aparte que nadie abre. Cada sprint deja algo de capacidad para bajarla.

---

## Archivos que quizás te preguntes qué hacen

| Archivo | Para qué |
|---|---|
| `.gitignore` | decide qué **no** se sube: `.venv`, cachés, el `.env` |
| `.gitattributes` | fija los finales de línea, para que Windows y Linux no llenen los pull requests de cambios falsos |
| `.env.example` | plantilla de variables de entorno. El `.env` real no se sube nunca |
| `Makefile` | atajos de comandos. **Solo funciona en Linux y Mac**; las equivalencias de Windows están escritas adentro |
| `requirements.txt` | lo que la aplicación necesita para correr |
| `requirements-dev.txt` | lo que necesitas tú para desarrollar |

Los dos requirements están separados porque el servidor no tiene ninguna razón
para instalar pytest ni Ruff. Menos paquetes en producción significa menos peso
y menos cosas que se puedan romper. Por eso hay que instalar **los dos** en tu
máquina: `requirements-dev.txt` no incluye al otro.

### Carpetas que aparecen y no importan

`.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `__pycache__`. Ninguna se
sube al repositorio.

`.venv` son los programas instalados. Las de caché son lo que esos programas
recuerdan entre ejecuciones para no repetir trabajo. Si borras una caché no pasa
nada, se regenera. Si borras `.venv` tienes que reinstalar todo.

---

## Estado actual y qué falta

**Lo que está funcionando:**

- Estructura Django completa con la configuración partida por entornos
- Las nueve entidades del modelo de datos, con sus migraciones
- El comando `seed_demo`, que carga datos de prueba siempre iguales
- El endpoint de salud, con dos tests
- El pipeline corriendo en verde, con reporte de cobertura
- `main` protegida con pull request obligatorio, pipeline verde y una aprobación
- Entorno de desarrollo con Docker, que levanta el portal y la base juntos
- Configuración de nginx y systemd versionada y documentada
- Dos fichas de decisión de arquitectura y dos diagramas

**Lo que falta y de qué depende:**

- **Las pantallas del portal**, que es lo grueso de lo que viene
- **El registro, el login y los roles**, que hay que enganchar al sistema de
  autenticación de Django
- **Las pruebas de los modelos**, que hoy no tienen ninguna
- **La integración con la capa de aprovisionamiento**, que depende de acordar
  el contrato con el otro grupo
- **Dónde se ejecutan las tareas programadas en el servidor**, definido como un
  timer de systemd en el diagrama, pero la unidad se escribe cuando haya acceso

Lo que está montado no es funcionalidad: es lo que permite agregar funcionalidad
sin romper nada. Configuración por entorno, verificación automática en cada
cambio, una rama protegida que obliga a revisar, y un despliegue documentado y
reproducible.

---

## Glosario

**ADR** — *Architecture Decision Record*. Un archivo por decisión importante,
con contexto, alternativas y consecuencias.

**Cobertura** — porcentaje de líneas de código que los tests ejecutaron. No dice
si el código está bien, solo si alguien lo probó.

**Fixture** — función que prepara algo que un test necesita. pytest la inyecta
por nombre.

**Gunicorn** — servidor de aplicación que ejecuta Django en producción.

**Linter** — herramienta que revisa el código buscando errores y desviaciones de
estilo, sin ejecutarlo.

**Migración** — archivo que Django genera al cambiar un modelo, con las
instrucciones para actualizar la base de datos.

**Multitenant** — un solo sistema que atiende a varios clientes manteniendo sus
datos aislados entre sí.

**Pipeline** — secuencia de verificaciones automáticas que corre en cada cambio.

**Ruleset** — las reglas de protección de una rama en GitHub.

**systemd** — el gestor de servicios de Linux. Arranca programas al encender la
máquina y los mantiene vivos.

**WSGI** — el estándar que conecta un servidor web con una aplicación Python.
