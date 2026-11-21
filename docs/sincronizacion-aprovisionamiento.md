# Sincronización de aprovisionamiento con tenantctl

## 1. Propósito y alcance

Esta plantilla prepara la lectura de los endpoints v1 del contrato
[`openapi-edocere-v1-rc3.yaml`](../../Aprovisionamiento/openapi-edocere-v1-rc3.yaml) para poblar
las tablas existentes del portal. El contrato marca los endpoints de lectura como
`B_TARGET_V1_PENDING`; su presencia aquí no significa que tenantctl ya esté habilitado.

El cliente solo se ejecuta al invocar el comando. Las pruebas sustituyen `urlopen` o el cliente
completo con mocks, por lo que no requieren un servidor activo ni hacen llamadas reales de red.
La plantilla **no modifica modelos, no crea migraciones y no inventa clientes ni instancias**:
cada tenant remoto debe coincidir con un `Cliente` e `InstanciaMoodle` locales.

## 2. Endpoints RC3 utilizados y descartados

`TenantctlReadClient` llama únicamente a estos endpoints:

| Endpoint | Datos utilizados |
| --- | --- |
| `GET /api/v1/tenants` | Lista tenants; admite `owner_ref`, `limit` y `cursor`. |
| `GET /api/v1/tenants/{tenant_slug}` | Obtiene `primary_hostname`, `status`, `moodle_version` y `branding.site_name` cuando están disponibles. |
| `GET /api/v1/operations` | Obtiene operaciones paginadas; solo se sincronizan las de tipo `PROVISION`. |
| `GET /api/v1/tenants/{tenant_slug}/usage?month=YYYY-MM` | Obtiene el agregado mensual, incluyendo `billable_users` y los metadatos de evidencia. |
| `GET /api/v1/tenants/{tenant_slug}/usage/courses?month=YYYY-MM` | Devuelve páginas de cursos con actividad calificable del mismo snapshot mensual. |

Los endpoints paginados se consultan por página con `limit` y `cursor`; cada respuesta contiene
`next_cursor`. El comando sigue ese cursor hasta recibir `null`. El tamaño máximo usado por la
plantilla es 200. Las páginas de cursos se validan contra el tenant, período, snapshot, revisión y
estado del agregado antes de contar cursos.

Se omiten intencionalmente `backups`, `backup-schedule`, `health`, `overview` y `branding-assets`:
el modelo actual del portal no tiene tablas asociadas para persistir esos datos.

## 3. Mapeo hacia las tablas del portal

### Vinculación de registros existentes

El aprovisionamiento actual del portal envía `owner_ref` como `str(InstanciaMoodle.cliente_id)`.
La plantilla usa esa convención para localizar el `Cliente` local y compara
`primary_hostname` con `InstanciaMoodle.dominio_host`. La coincidencia debe ser única. Si el cliente
o la instancia no existen localmente, falta la identidad o hay más de una coincidencia, el tenant
se informa y se omite; no se crean registros ficticios. Un cambio de hostname requiere acordar
cómo actualizar la correspondencia antes de sincronizarlo.

### `InstanciaMoodle`

| Campo local | Campo de tenantctl |
| --- | --- |
| `nombre` | `branding.site_name`, si está presente |
| `version` | `moodle_version`, si está presente |
| `estado` | `status` |

`PROVISIONING` se normaliza a `PENDING`. Los estados que no tienen una correspondencia local
confirmada —incluido `DEPROVISIONING`— se informan y no sobrescriben el estado actual.

### `SolicitudAprovisionamiento`

Se sincronizan operaciones `PROVISION` de tenants vinculados, usando `operation_id` como clave
para `update_or_create`. Los estados `PENDING`, `RUNNING`, `COMPLETED` y `FAILED` se mapean a los
estados locales equivalentes.

**Limitación del esquema:** el modelo no tiene `intentos`, `codigo_error` ni `detalle_error`.
`attempt_count` y `error` se informan en consola cuando la API los entrega, pero no se persisten.
Almacenarlos requeriría un cambio de modelo y una migración, fuera del alcance acordado.

### `MedicionUsoMensual`

Solo se guarda una medición si `/usage` contiene evidencia válida para el tenant y período y todas
las páginas de `/usage/courses` coinciden con el snapshot del agregado.

| Campo local | Fuente |
| --- | --- |
| `instancia` | Instancia local vinculada |
| `anio`, `mes` | `--month` |
| `usuarios_activos` | `billable_users` |
| `cantidad_cursos` | Número de cursos válidos recibidos en todas las páginas |

Al actualizar una fila existente solo se modifican `usuarios_activos` y `cantidad_cursos`;
`usuarios_inscritos`, `total_matriculas` y `cantidad_categorias` se preservan. Esos tres campos se
inicializan en `0` únicamente al crear una fila nueva desde tenantctl. Si no hay evidencia válida
del agregado o de los cursos, no se crea ni actualiza la medición; la ausencia de evidencia nunca
se guarda como cero.

#### Cobertura de métricas y diferencia con CSV

La sincronización API no completa todas las métricas del portal. `usuarios_inscritos`,
`total_matriculas` y `cantidad_categorias` no vienen de estos endpoints y no se deducen de
`billable_users` ni del conteo de cursos. La vista calcula `matriculados_por_curso` como
`total_matriculas / cantidad_cursos` cuando ambos valores existen; no reconstruye las otras
métricas. También consolida las mediciones disponibles entre instancias, sin generar valores
faltantes. Por eso, una fila nueva sincronizada solo desde tenantctl puede mostrar cero o ausencia
de datos en métricas complementarias, no uso real.

La carga CSV funciona de otra manera: `importar_mediciones` recibe directamente las cinco métricas
(`usuarios_inscritos`, `usuarios_activos`, `cantidad_cursos`, `total_matriculas` y
`cantidad_categorias`). Un CSV con valores reales puede completar los campos que esta API no
entrega. No hay un cálculo automático que convierta la carga parcial de la API en todas las
métricas disponibles en el portal.

## 4. Configuración y autenticación

Configurar estas variables en el entorno del proceso:

| Variable | Requisito |
| --- | --- |
| `TENANTCTL_API_BASE_URL` | Obligatoria. Origen de tenantctl, sin ruta, query ni fragmento; por ejemplo `https://tenantctl.example.cl`. El cliente agrega `/api/v1`. Exige HTTPS en hosts remotos; HTTP solo se permite para `localhost`, `127.0.0.1` o `::1`. |
| `TENANTCTL_SERVICE_TOKEN` | Obligatoria. Bearer del cliente de servicio. |
| `TENANTCTL_ACTOR_ASSERTION` | Opcional. Solo se envía en solicitudes que deban representar a un actor humano; no se configura en el batch nocturno. |

El cliente envía `Authorization: Bearer <TENANTCTL_SERVICE_TOKEN>` y agrega
`X-Panel-Actor-Assertion` únicamente cuando `TENANTCTL_ACTOR_ASSERTION` tiene valor. Para cron,
Edocere debe aprovisionar un cliente de servicio dedicado con permiso `operations:system` y un
actor de sistema auditable; no se debe fabricar ni reutilizar una assertion humana. Antes de
producción, confirmar con Edocere que este mecanismo batch está habilitado para los endpoints v1.

El cliente batch también necesita los permisos de lectura exigidos por las rutas que consulta:

| Ruta | Permiso de lectura del contrato |
| --- | --- |
| `GET /api/v1/tenants` y `GET /api/v1/tenants/{tenant_slug}` | `tenants:read` |
| `GET /api/v1/operations` | `operations:read` |
| `GET /api/v1/tenants/{tenant_slug}/usage` y `/usage/courses` | `usage:read` |

No asumir que `operations:system` concede automáticamente estos permisos de lectura; Edocere debe
confirmar la asignación efectiva al cliente de servicio.

**Punto que debe resolverse contra RC3:** el bloque global `security` del OpenAPI declara Bearer y
`X-Panel-Actor-Assertion`, mientras que la sección de autorización describe el batch
`operations:system` sin assertion humana. Esta plantilla omite la cabecera cuando la variable
opcional no está configurada. Edocere debe confirmar y documentar cómo se expresa esa excepción en
la configuración desplegada; de lo contrario, el servidor podría rechazar el batch por
autenticación.

Tratamiento de respuestas:

- Un `404` se convierte en `None`. La ausencia del listado principal de tenants o del listado de
  operaciones detiene la sincronización con `CommandError`; un detalle de tenant no disponible
  solo omite su actualización.
- Un `409` se convierte en `None` únicamente en endpoints de uso cuando el cuerpo indica
  `error: USAGE_DATA_UNAVAILABLE`.
- Un `404` o ese `409` en uso no crea una medición ni se convierte en cero. Otros errores HTTP,
  errores de red, JSON inválido o configuración incorrecta se convierten en `TenantctlReadError`;
  el comando los transforma en `CommandError`, de modo que cron recibe un código de salida distinto
  de cero.

`--dry-run` consulta tenantctl y valida las respuestas, pero no escribe en la base de datos. No es
un modo sin red.

## 5. Uso del comando y programación batch (`cron`)

El comando se ejecuta con `python manage.py sincronizar_aprovisionamiento`.

| Opción | Comportamiento |
| --- | --- |
| `--month YYYY-MM` | Período a sincronizar; por defecto usa el mes calendario anterior. |
| `--owner-ref VALOR` | Filtra tenants por `owner_ref`. |
| `--dry-run` | Muestra los cambios previstos sin escribir; sí consulta la API. |
| `--solo-instancias` | Sincroniza instancias y solicitudes; omite mediciones. |
| `--solo-uso` | Sincroniza mediciones; omite actualizaciones de instancias y solicitudes. |

`--solo-instancias` y `--solo-uso` son excluyentes. Ejemplos:

```bash
python manage.py sincronizar_aprovisionamiento
python manage.py sincronizar_aprovisionamiento --month 2026-10 --owner-ref 42
python manage.py sincronizar_aprovisionamiento --month 2026-10 --dry-run
python manage.py sincronizar_aprovisionamiento --solo-instancias
python manage.py sincronizar_aprovisionamiento --month 2026-10 --solo-uso
```

Ejemplo batch Linux: guardar las variables obligatorias en `/etc/edocere/tenantctl.env`, con
permisos restringidos (por ejemplo, `chmod 600`):

```sh
export TENANTCTL_API_BASE_URL="https://tenantctl.example.cl"
export TENANTCTL_SERVICE_TOKEN="<token-del-cliente-de-servicio>"
```

No añadir `TENANTCTL_ACTOR_ASSERTION` al entorno batch. Ejemplo de ejecución diaria a las 03:30:

```cron
30 3 * * * set -a && . /etc/edocere/tenantctl.env && set +a && cd /opt/edocere/portal && /opt/edocere/venv/bin/python manage.py sincronizar_aprovisionamiento >> /var/log/edocere/sincronizacion-aprovisionamiento.log 2>&1
```

El comando recorre las páginas desde el inicio en cada ejecución y actualiza por claves existentes.
`updated_since` en `/operations`, un checkpoint/watermark y locks para evitar ejecuciones
simultáneas son mejoras para evaluar si el volumen crece.

## 6. Pruebas y validación

Las pruebas aisladas están en `apps/instancias/tests/test_sync_command.py`. Sustituyen `urlopen`
o `TenantctlReadClient` con `unittest.mock`; verifican URLs, cabeceras, validación de configuración,
errores HTTP, paginación, mapeos, preservación de métricas y `--dry-run`. No levantan servidores ni
hacen tráfico de red.

Desde la raíz del proyecto, en PowerShell:

```powershell
$env:USE_SQLITE = "1"
python manage.py test apps.instancias.tests.test_sync_command --settings=config.settings.test
```

## 7. Acuerdos pendientes antes de activar en producción (Checklist Edocere)

- [ ] Provisionar y probar el cliente batch con permiso `operations:system`, Bearer de servicio y
  actor de sistema auditable; confirmar que no requiere assertion humana.
- [ ] Confirmar que el cliente batch tiene también `tenants:read`, `operations:read` y `usage:read`
  para los endpoints que consume, y que dichos permisos no dependen de una assertion humana.
- [ ] Resolver la diferencia entre el `security` global de RC3 (Bearer más actor assertion) y el
  flujo automatizado `operations:system` sin assertion; documentar la excepción o el mecanismo
  definitivo antes de emitir credenciales productivas.
- [ ] Confirmar que `owner_ref` persistirá como la referencia acordada para el `Cliente` local y
  definir el procedimiento ante cambios de `primary_hostname`.
- [ ] Confirmar que `/usage/courses` representa cursos con actividad calificable en el mes, no el
  inventario completo de Moodle.
- [ ] Definir el mapeo de estados transitorios como `DEPROVISIONING`; hasta entonces la plantilla
  conserva el estado local para ese valor.
- [ ] Acordar qué respuestas `404` son ausencia esperada y cuáles deben tratarse como falla de
  integración, en particular para lecturas opcionales y listados.
- [ ] Si aumenta el volumen, evaluar `updated_since` para `/operations`, persistencia de checkpoint
  y locks de ejecución.
- [ ] Probar en un entorno de integración habilitado el contrato real, permisos, respuestas,
  paginación y efecto de una corrida `--dry-run` antes de activar escrituras programadas.
- [ ] Evaluar un resumen final de tenants omitidos por causa (sin cliente, hostname no coincidente,
  detalle o evidencia no disponible). Actualmente se escriben avisos individuales; un resumen
  facilitaría revisar los logs batch.
