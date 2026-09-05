# Decisión 1 — Estilo de arquitectura y stack tecnológico

## Contexto

Edocere opera Moodle en modo multitenant sobre un único servidor Linux en
Huawei Cloud. El cliente fija el entorno tecnológico: Linux, PHP o Python,
MariaDB, sin contenedores en el servidor.

Somos cinco personas trabajando medio tiempo durante tres meses, con Claude
autorizado como asistente de programación. Rafael pidió explícitamente
tecnología estándar, código comentado y buenas prácticas, para que quien tome
el código después no batalle para entenderlo.

## Alternativas consideradas

**Monolito con Django (elegida).** Un solo proyecto que sirve el panel web, la
consola de administración y las tareas programadas. Python 3.12, Django 5.2
LTS, MariaDB.

**Monolito con Laravel.** Mismo diseño, en PHP. Comparte runtime con Moodle, lo
que simplifica la convivencia en el servidor.

**Frontend separado más API.** Una aplicación en React consumiendo una API
REST. Mayor flexibilidad de interfaz.

**Microservicios.** Un servicio por dominio: clientes, instancias, cobros.

## Decisión

Monolito con Django, desplegado con Gunicorn y nginx sobre el mismo servidor.

## Justificación

Django frente a Laravel se decidió por revisión, no por afinidad tecnológica.
Los cinco integrantes leemos Python con soltura y ninguno conoce Laravel. Con
un asistente de IA generando parte del código, el trabajo se desplaza de
escribir a revisar, y un equipo que no domina el framework aprueba pull
requests sin entender qué aprobó. Laravel además usa facades y métodos mágicos
que un modelo tiende a inventar mal, que es justo lo que no detectaríamos.

Django 5.2 es versión LTS con soporte hasta abril de 2028, lo que responde
directamente al requisito de Rafael de no quedar con tecnología obsoleta. El
panel de administración incluido cubre buena parte de la consola de
superadministrador sin desarrollo adicional.

Se descartaron los microservicios porque el dominio no lo justifica: son unas
diez entidades y un único servidor. Repartirlas en servicios independientes
agrega despliegues, contratos y modos de falla sin resolver ningún problema
que tengamos. Un frontend separado se descartó por costo de tiempo: obliga a
mantener dos aplicaciones y un contrato entre ellas, cuando el MVP son tres
pantallas.

## Consecuencias

El servidor incorpora un runtime que hoy no tiene, y hay que instalar Gunicorn
como servicio de systemd junto a los Moodle existentes. Se mitiga con el
documento de despliegue y con la confirmación de Rafael sobre mantenibilidad.

Al ser un monolito, todo se despliega junto: un cambio en estadísticas obliga a
reiniciar también el panel de pagos. Aceptable para el volumen actual.

Si más adelante Edocere expone una API para ERPs de clientes grandes, tal como
mencionó Rafael, se agrega como una app más dentro del mismo proyecto.
