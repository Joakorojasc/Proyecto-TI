# Integración de pagos y DTE en el portal de Edocere

## Propósito y alcance

Este documento describe cómo conectar el portal Django con
una pasarela de pago y un proveedor de Documentos Tributarios Electrónicos
(DTE), y qué trabajo adicional implica operar esa integración en producción.
Es una guía de integración, no una confirmación de que los proveedores,
contratos o endpoints estén habilitados.

La investigación del proyecto propone **Flow para cobros en Chile** y
**SimpleAPI para emitir DTE**. También identifica una posible estrategia futura
para clientes extranjeros. Los precios, comisiones, límites, disponibilidad de
tokenización recurrente y requisitos de cada proveedor deben confirmarse con
ellos antes de contratar o implementar; pueden cambiar.

El objetivo acordado para esta etapa es un MVP en staging validado, no una
integración productiva. Antes de comprometer fechas o habilitar cobros reales,
se deben confirmar los responsables y las reglas comerciales, contables y
tributarias.

## Información técnica verificada en documentación pública

Consulta de las fuentes oficiales indicadas al final del documento, realizada
el **21-11-2026**. Estos datos describen la documentación pública; no confirman
las funciones habilitadas para la cuenta, contrato o comercio de Edocere.
Revalidarlos antes de implementar porque las API y sus límites pueden cambiar.

### Flow

- La documentación publica un ambiente productivo
  (`https://www.flow.cl/api`) y uno de pruebas
  (`https://sandbox.flow.cl/api`).
- Las solicitudes se autentican con `apiKey` y una firma `s` generada con
  HMAC-SHA256 usando `secretKey`: se ordenan alfabéticamente los parámetros,
  se concatenan sus nombres y valores, y se excluye `s` del cálculo. La clave
  secreta debe permanecer solo en el servidor.
- Para `payment/create`, Flow envía al callback un `POST` con
  `application/x-www-form-urlencoded` que contiene un `token`. El portal debe
  usarlo para consultar `/payment/getStatus`; el callback es una notificación,
  no un resultado de pago que se deba aceptar sin verificación servidor a
  servidor. La API distingue la URL de confirmación (`urlConfirmation`) de la
  URL de retorno del navegador (`urlReturn`). Para registrar una tarjeta, la
  documentación describe `/customer/register` y
  `/customer/getRegisterStatus`.
- La API documenta distintas opciones de recurrencia: cargos contra clientes
  registrados (`/customer/charge` y `/customer/collect`) y recursos de
  planes/suscripciones (`/plans/*` y `/subscription/*`). Debe elegirse entre
  que Flow administre el ciclo recurrente y que el portal programe cargos
  contra el cliente registrado; no activar ambos para la misma suscripción.
- El recurso `/invoice/*` de Flow corresponde al importe/cobro generado por
  una suscripción. No asumir que ese recurso es un DTE aceptado por el SII.

### SimpleAPI

- Su documentación presenta `POST /api/v1/dte/generar` para generar distintos
  tipos de DTE con una estructura de entrada común. La colección de Postman
  publica ejemplos multipart con el JSON en `input`, certificado digital PFX
  en `files` y archivo CAF en `files2`. El TipoDTE `33` aparece como Factura
  Electrónica; también se enumeran los tipos `34` (exenta), `61` (nota de
  crédito), `56` (nota de débito) y `110` (factura de exportación), entre
  otros. La elección del documento y los datos a emitir siguen sujetos a
  validación contable y tributaria.
- El ejemplo público del DTE 33 incluye emisor, receptor, detalles, totales,
  IVA, certificado y CAF; el campo `Folio` se describe como folio autorizado
  por el SII. Antes de programar la emisión, confirmar con SimpleAPI si el
  portal debe asignar y enviar folios desde el CAF o si el servicio los
  administra. También definir cómo se validan los datos, impuestos, descuentos
  y redondeos antes de solicitar el DTE.
- La documentación describe autenticación con una API key en el encabezado
  `Authorization` y también menciona un bearer token de 24 horas obtenido desde
  sus endpoints de autenticación. Confirmar con SimpleAPI cuál mecanismo exige
  el endpoint DTE contratado y cómo se renueva.
- La documentación publica para la API DTE un límite de hasta 3 consultas por
  segundo y 40 por minuto. El proceso de emisión y sus reintentos debe
  respetarlo, aplicar espera ante limitación y no reintentar indefinidamente.
- SimpleAPI indica que para probar emisión se requiere API key, certificado
  digital vigente y CAF de certificación del emisor. Acordar cómo se obtienen,
  protegen y separan estos artefactos para certificación y producción. Los
  ejemplos de API no sustituyen la validación del SII ni la revisión contable.

## Estado actual del portal

El repositorio contiene modelos para `MedioPago`, `Pago` y
`DocumentoTributario` en [`apps/pagos/models.py`](../apps/pagos/models.py), y
una vista de checkout en [`apps/pagos/views.py`](../apps/pagos/views.py) que
usa `CheckoutSimuladoForm` de [`apps/pagos/forms.py`](../apps/pagos/forms.py):
el token, el resultado del pago y el comprobante son simulados. **No se conecta
a Flow ni emite un DTE real con SimpleAPI**. El campo `token_simulado` no debe
tratarse como un token real del proveedor. La ruta de checkout está declarada
en [`apps/pagos/urls.py`](../apps/pagos/urls.py), incluida desde
[`config/urls.py`](../config/urls.py).

La estructura de despliegue existente usa Django, Gunicorn, nginx, MariaDB y
servicios del sistema. El documento de despliegue no incluye todavía un proceso
de cobros recurrentes. El trabajo para programar pagos mensuales, procesar
notificaciones de Flow, emitir DTE y reconciliar resultados es parte pendiente (por desarrollar posteriormente).

## Arquitectura objetivo

El portal conserva la responsabilidad sobre clientes, suscripciones, precios,
pagos y documentos. Flow procesa el medio de pago y SimpleAPI solicita/emite el
DTE. Ningún proveedor reemplaza la lógica de negocio del portal.

```text
Navegador del cliente
        │
        ├── inicia checkout / confirma la suscripción
        ▼
Portal Django ───────► Flow
        │                │
        │                └── notificación de resultado (webhook)
        ▼
MariaDB: pago y estado de suscripción
        │
        └── tarea de emisión ─────► SimpleAPI ─────► SII
                                      │
                                      └── folio, estado y representación del DTE
```

La llamada de retorno del navegador no es evidencia suficiente de pago. Para
Flow, el callback descrito públicamente contiene un token enviado por POST; el
portal debe verificar el estado consultando su API autenticada. No asumir que el
callback incluye una firma propia ni que su cuerpo basta para aprobar el pago.
La integración debe seguir la documentación vigente de ambos proveedores.

## Flujo propuesto

### 1. Contratación y tokenización

1. El usuario autenticado elige un plan y el portal calcula el precio,
   descuentos, moneda, periodicidad e impuestos aplicables.
2. El portal crea o recupera una suscripción pendiente y un intento de pago
   pendiente con una referencia interna única.
3. La captura de los datos de tarjeta se realiza mediante el componente o flujo
   alojado/recomendado por Flow. El portal no debe recibir ni guardar número
   completo de tarjeta ni CVV.
4. Si el producto contratado admite cobros recurrentes tokenizados, Flow
   devuelve una referencia/token. El portal guarda únicamente el identificador
   que el proveedor autorice almacenar, asociado al cliente y con el mínimo
   acceso necesario.
5. Se redirige al usuario al flujo del proveedor y se muestra el pago como
   pendiente hasta confirmar su resultado por servidor.

En el código actual, el checkout que habría que reemplazar o extender está en
`apps/pagos/views.py` y el formulario simulado en `apps/pagos/forms.py`; la
ruta existente está en `apps/pagos/urls.py`. El cálculo de descuento y precio
ya está centralizado en `apps/pagos/services.py`.

Antes de construir este flujo, hay que confirmar con Flow el producto exacto
para tokenización y cobros recurrentes, las condiciones de uso del token, las
marcas admitidas, moneda, requisitos de autenticación (por ejemplo 3-D Secure)
y el onboarding del comercio.

### 2. Confirmación del pago

1. Para el flujo documentado de `payment/create`, Flow envía al callback HTTPS
   un POST de formulario con `token`. El portal conserva el token para hacer
   una consulta servidor a servidor a `/payment/getStatus`, firmada con las
   credenciales del comercio.
2. Correlaciona la respuesta verificada con la referencia interna del pago y
   comprueba monto, moneda, orden y comercio antes de modificar el estado. No
   confía en el navegador ni en los datos del callback como confirmación de
   pago. Para registro de tarjeta, usar el flujo distinto de
   `/customer/register` y verificarlo con `/customer/getRegisterStatus`.
3. El portal registra el identificador del evento/transacción y actualiza el
   pago. Los eventos duplicados deben ser idempotentes: procesar la misma
   notificación más de una vez no puede crear cobros, activar una suscripción
   ni emitir documentos duplicados.
4. Solo una confirmación válida permite marcar el pago aprobado y activar la
   suscripción. Un rechazo deja la suscripción pendiente o aplica la política
   comercial acordada.

La recepción del webhook necesitará una ruta pública y una vista específicas
en `apps/pagos/urls.py` y `apps/pagos/views.py` (o módulos nuevos separados).
El manejo del callback, la firma de las llamadas salientes a Flow y la consulta
de estado deben quedar en un adaptador nuevo, no mezclados con la vista ni con
el estado de negocio existente en `apps/pagos/services.py`. La firma oficial
ordena parámetros alfabéticamente y usa HMAC-SHA256 con `secretKey`; conviene
probarla con vectores de la documentación o la colección oficial antes de
aceptar cobros.

### 3. Emisión del documento tributario

1. Para el modelo B2B, el documento base a considerar es la **Factura
   Electrónica Afecta a IVA (DTE 33)**, sujeto a validación contable. Un pago
   aprobado queda listo para emitir el documento que corresponda. Se valida que
   existan los datos tributarios del cliente y los datos de la venta que
   requiere SimpleAPI.
2. El portal solicita a SimpleAPI el tipo de DTE acordado. La colección pública
   muestra un endpoint de generación con entrada multipart; no se ha verificado
   un `Idempotency-Key` ni una garantía de idempotencia del proveedor. El portal
   debe evitar duplicados mediante una referencia única local al pago,
   exclusión mutua y consulta/reconciliación antes de reintentar una solicitud
   cuyo resultado sea incierto. La respuesta se almacena: proveedor,
   identificador de solicitud, tipo de documento, folio, estado y URL o
   referencia segura al PDF/XML, si el contrato lo permite.
3. La respuesta del proveedor y la aceptación del SII se registran como estados
   separados si la API distingue entre ellos. El portal muestra al cliente el
   documento solo cuando esté disponible y aceptado según la regla que defina
   Edocere.
4. Si el proveedor no responde o falla, el pago permanece aprobado y el
   documento queda **pendiente de emisión/reintento**. No se vuelve a cobrar
   para resolver una falla de facturación. Los reintentos consultan primero si
   el documento ya fue creado, para evitar folios duplicados.

El equipo contable de Edocere debe definir qué operación genera DTE, cuándo se
emite, qué datos son obligatorios, cómo se manejan anulaciones/notas de crédito
y qué estados se muestran. La API puede emitir documentos, pero no decide el
tratamiento tributario correcto. El registro de cada documento parte del modelo
`DocumentoTributario` en `apps/pagos/models.py`; su integración requerirá
ampliarlo y generar una migración. Los datos de facturación existentes del
cliente están en `apps/clientes/models.py`.

### 4. Cobros recurrentes

Primero hay que elegir el modelo de recurrencia. Flow documenta suscripciones
con planes y también cargos contra un cliente registrado. Si se usa la
suscripción administrada por Flow, el portal debe sincronizar y conciliar sus
ciclos y resultados; si el portal administra el calendario, una tarea
programada independiente busca las suscripciones que vencen, crea un intento
por ciclo y solicita el cargo con la referencia del cliente/token. No crear
simultáneamente una suscripción recurrente en Flow y un timer local para cobrar
los mismos periodos. En ambos modelos se necesita:

- Una clave única de ciclo (por ejemplo, suscripción + periodo) para impedir
  cobros repetidos.
- Exclusión mutua o bloqueo al procesar una suscripción, y reintentos con
  backoff solo para errores transitorios.
- Manejo diferenciado de rechazo, timeout y resultado desconocido. Ante timeout
  primero se consulta al proveedor; no se repite a ciegas un cargo.
- Una política aprobada para reintentos, notificación al cliente, suspensión,
  reactivación, cancelación y cambios de plan.
- Una política de devolución y reversa. La API de Flow documenta operaciones
  distintas para reembolsos y reversas de cargos; validar elegibilidad, estados
  y plazos vigentes antes de ofrecerlas desde el portal.
- Registro auditable del intento, respuesta normalizada y referencias del
  proveedor, sin guardar secretos ni datos completos de tarjeta.

Si Edocere elige que el portal administre los ciclos, el cobro debe ejecutarse
como tarea programada/servicio supervisado (por ejemplo, un timer de systemd),
no dentro de una petición de Gunicorn. El despliegue actual separa las tareas
programadas del portal web, pero falta definir e instalar el comando y su timer
para cobros. No existe aún un comando de pagos en
`apps/pagos/management/commands/`; habría que crearlo, junto con las unidades
`.service`/`.timer` correspondientes en `deploy/`. La instalación de servicios
se describe en [despliegue.md](despliegue.md) y
[`deploy/README.md`](../deploy/README.md).

## Datos y cambios esperados

El esquema actual es un punto de partida, no el contrato productivo. Antes de
conectar los proveedores, revisar y ampliar con migraciones:

- `MedioPago`: sustituir el concepto de `token_simulado` por una referencia
  protegida del token del proveedor, proveedor, estado, fechas y metadatos
  estrictamente necesarios. El modelo está en `apps/pagos/models.py`; registrar
  los cambios en una nueva migración bajo `apps/pagos/migrations/`. No guardar
  PAN ni CVV.
- `Pago`: asociar referencia/idempotency key interna, identificador de
  transacción del PSP, `commerceOrder`/`flowOrder` y `customerId` cuando
  correspondan, moneda, periodo cobrado, estado normalizado, timestamps y
  datos mínimos para reconciliación. Modificar `Pago` en
  `apps/pagos/models.py` y revisar sus usos en `apps/pagos/views.py` y
  `apps/pagos/services.py`.
- `DocumentoTributario`: almacenar referencia del proveedor, estado de emisión
  y aceptación, tipo, folio, fechas y ubicación/referencia protegida del
  documento. Está definido en `apps/pagos/models.py`; crear la migración
  correspondiente. Definir unicidad para evitar más de un DTE por el mismo
  concepto salvo casos autorizados (por ejemplo, nota de crédito y nueva
  emisión).
- Datos de facturación del cliente: acordar y validar (Edocere) qué
  identificación tributaria, razón social, domicilio, giro y demás datos
  comerciales/tributarios se necesitan. El modelo `Cliente` está en
  `apps/clientes/models.py`; cualquier ampliación necesita su propia migración
  en `apps/clientes/migrations/`.

Mantener los cambios de base de datos compatibles con el procedimiento de
rollback descrito en la [guía de despliegue](despliegue.md).

## Configuración y conexión al portal entregado

1. **Obtener el contrato de integración** de Edocere: dominio del portal,
   entornos de staging/producción, flujo esperado para checkout, reglas de
   autenticación, propietario del dominio y contacto técnico.
2. **Confirmar cuentas y productos** con Flow y SimpleAPI: acceso a sandbox,
   credenciales, APIs habilitadas, callback/webhook, certificados o firma,
   límites, soporte, precios y proceso de paso a producción.
3. **Implementar adaptadores en `apps/pagos`** que encapsulen cada API y
   conviertan las respuestas externas a estados internos estables. Los
   resultados confirmados de Flow deben actualizar el estado de `Pago` (`aprobado`,
   `pendiente` o `rechazado`) que consume
   `estado_cliente_para_instancia` en `apps/pagos/services.py`, respetando que
   ese servicio determina el acceso a partir del último intento de pago de la
   suscripción. El checkout, la lógica de suscripción y las pantallas no deben
   depender de formatos propietarios. Hoy no hay adaptadores de proveedores:
   se pueden crear, por ejemplo, en `apps/pagos/integrations/flow.py` y
   `apps/pagos/integrations/simpleapi.py`, manteniéndolos separados de
   `apps/pagos/services.py`, que contiene lógica de negocio.
4. **Configurar secretos fuera del código**: credenciales de API, claves de
   firma y secretos de webhook en el gestor de secretos o mecanismo aprobado
   por Edocere. Las variables de entorno deben ser distintas por entorno; no se
   versionan en Git ni se escriben en logs. La carga de variables se configura
   en `config/settings/base.py`; documentar solo nombres y valores de ejemplo
   no sensibles en `.env.example`.
5. **Publicar los callbacks HTTPS** de staging y producción en los paneles de
   los proveedores. Validar conectividad entrante, certificados, rutas y
   respuestas esperadas; las rutas se declararán en `apps/pagos/urls.py` y se
   conectarán desde `config/urls.py`. La terminación HTTPS y el proxy se
   configuran en `deploy/nginx.conf`. No dejar endpoints de administración
   expuestos para resolver callbacks.
6. **Aplicar migraciones y desplegar** en staging siguiendo
   [despliegue.md](despliegue.md). Configurar el proceso de cobro programado
   solamente después de validar pagos de prueba, sin cargos reales.
7. **Probar el flujo de punta a punta** y reconciliar el pago, el estado de
   suscripción, el DTE en SimpleAPI/SII y lo visible en el portal. Luego obtener
   la aceptación funcional, contable y operativa antes de habilitar producción.
   Añadir pruebas focalizadas en `apps/pagos/tests/` junto a las pruebas
   existentes de vistas y modelos.

## Producción: qué implica

La puesta en producción no es solo cambiar una URL o API key. Requiere como
mínimo:

### Antes del despliegue

- Cuenta de comercio activa, contrato/tarifas aprobados, credenciales live,
  onboarding y habilitación de cobros recurrentes en Flow.
- Cuenta, plan, límites, credenciales y permisos de emisión de DTE aprobados
  con SimpleAPI; confirmar comunicación y resultado de aceptación en el SII.
- Dominio y HTTPS operativos, endpoints de webhook registrados y probados,
  y reglas de red que permitan la comunicación saliente/entrante necesaria.
  Revisar `deploy/nginx.conf`, `deploy/portal.service` y
  `config/settings/production.py`; son configuraciones de referencia y deben
  validarse en el entorno real de Edocere.
- Confirmar los límites vigentes de API con cada proveedor y probar el manejo
  de respuestas de limitación. Para SimpleAPI, la documentación pública indica
  hasta 3 solicitudes por segundo y 40 por minuto para DTE; verificar el plan y
  límite efectivo de la cuenta antes de dimensionar un lote de emisión.
- Confirmación de reglas de precio, IVA, moneda, periodos, prorrateos,
  descuentos, cancelaciones, devoluciones, documentos y vencimientos por
  Edocere y su asesor contable/tributario.
- Aprobación del tratamiento de clientes internacionales. La investigación
  advierte que Flow cobra en CLP/UF y puede tener restricciones de aceptación
  para tarjetas extranjeras; verificar condiciones actuales. Stripe no debe
  asumirse disponible para una entidad chilena. Antes de añadir otro PSP,
  resolver con Contabilidad quién emite el documento para evitar que el PSP y
  SimpleAPI documenten dos veces la misma venta.
- Backups verificables de MariaDB, acceso operacional restringido, monitoreo y
  responsables de atención ante pagos desconocidos o fallos de emisión.

### Pruebas de aceptación obligatorias

- Pago aprobado, rechazado, cancelado y abandonado; notificación duplicada,
  inválida o tardía; timeout y consulta de estado.
- El navegador vuelve antes/después del webhook sin cambiar por sí solo el
  estado de pago.
- Cobro recurrente repetido, dos tareas simultáneas, respuesta desconocida y
  reintento sin duplicación de cargo.
- Pago aprobado con SimpleAPI disponible, indisponible o respondiendo tarde;
  reintento sin duplicar DTE; validación de datos tributarios incompletos.
- Emisión de un DTE 33 de certificación con datos, folio, certificado y CAF de
  prueba aprobados por Edocere; contrastar montos, IVA, PDF/XML y estado
  informado por SimpleAPI/SII. Probar límites de frecuencia sin generar
  documentos tributarios productivos.
- Despliegue, reinicio del servicio, ejecución del timer, recuperación tras
  caída y restauración probada desde backup. La ejecución del timer aplica si
  el portal es responsable del calendario de cobros.
- Reconciliación de una muestra contra los pagos/liquidaciones de Flow, los
  documentos de SimpleAPI/SII y MariaDB, incluyendo monto, moneda, estado y
  folio. Revisar también devoluciones y reversas.

### Operación continua

- Alertar sobre fallas de webhook, pagos en estado desconocido, intentos
  vencidos, documentos pendientes, diferencias de conciliación y timer que no
  se ejecutó.
- Tener un procedimiento para conciliar y corregir estados de forma auditable,
  emitir/anular documentos conforme a la política contable y atender disputas.
- Conciliar periódicamente los pagos y liquidaciones del PSP con los pagos del
  portal, y las emisiones/aceptaciones del SII con `DocumentoTributario`.
  Diferenciar el importe/invoice de Flow del DTE tributario.
- Rotar credenciales, restringir permisos, revisar accesos y evitar incluir
  tokens, identificaciones tributarias o respuestas sensibles en logs o
  herramientas de monitoreo.
- Acordar responsables, ventanas de soporte, escalamiento a proveedores,
  retención de datos, SLA y procedimiento de incidentes.
- Desplegar cambios de forma gradual: staging primero, revisión de migraciones,
  respaldo, verificación de salud y plan de rollback. Un rollback de código no
  revierte cobros ni DTE emitidos; las correcciones financieras requieren
  conciliación y el procedimiento formal correspondiente. El proceso de
  despliegue está documentado en `docs/despliegue.md`; la configuración de
  servicios vive en `deploy/`.

## Decisiones que Edocere debe cerrar

1. ¿Flow y SimpleAPI son los proveedores aprobados y qué productos/planes
   específicos se contratarán?
2. ¿Qué entidad legal de Edocere vende, cobra y emite cada documento? ¿Quién
   valida los criterios tributarios y las notas de crédito?
3. ¿Qué datos de facturación son obligatorios y en qué momento se solicitan?
4. ¿Quién administrará la recurrencia: las suscripciones/planes de Flow o el
   calendario de cobro del portal? ¿Qué moneda, ciclo, política de
   reintentos/suspensión, cambios y cancelaciones aplican?
5. ¿Cómo se define el flujo internacional: países, monedas, PSP admitidos y
   emisor del documento? ¿El PSP genera algún comprobante/invoice que pueda
   duplicar el documento tributario?
6. ¿Quién administra secretos, webhooks, accesos live, monitoreo y conciliación?
   ¿Qué entornos y casos de prueba entregará/aceptará el equipo del portal?

Hasta cerrar estas decisiones y validar los flujos con ambos proveedores, la
integración debe mantenerse en sandbox y la pantalla debe identificar
claramente el comportamiento como prueba, no como cobro real.

## Fuentes oficiales consultadas

- [Flow — referencia de API REST](https://www.flow.cl/docs/api.html) y
  [especificación OpenAPI publicada](https://www.flow.cl/docs/apiFlow.yaml?v=7).
- [SimpleAPI — documentación para desarrolladores](https://www.simpleapi.cl/Documentacion)
  y [colección oficial de Postman](https://documentacion.simpleapi.cl).

Consulta realizada el **21-11-2026**. Se revisó la documentación pública, no se
ejecutaron llamadas contra cuentas de Flow o SimpleAPI ni se validaron las
credenciales, límites, productos, folios, certificados o acuerdos de Edocere.
La documentación pública puede no coincidir con las funciones habilitadas para
su cuenta; confirmar contrato, ambiente, formatos y casos de prueba directamente
con cada proveedor antes de implementar o emitir documentos reales.
