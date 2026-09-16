# Decisión 2 — Despliegue, integración continua y entrega continua

## Contexto

El cliente prohíbe contenedores en el servidor. El portal debe convivir con
las instancias Moodle en la misma máquina de Huawei Cloud sin afectarlas.

Rafael no espera producción en esta etapa: el objetivo es un staging validado.
El acceso a ese servidor depende de una coordinación entre Rafael y Jorge
todavía sin fecha comprometida.

## Alternativas consideradas

**Docker en desarrollo, despliegue directo en el servidor (elegida).**
Contenedores solo para la base de datos local; en el servidor, Gunicorn como
servicio de systemd detrás de nginx.

**Docker en todos lados.** Descartada por restricción explícita del cliente.

**Despliegue manual por SSH.** Copiar archivos a mano en cada actualización.

**Entrega continua completa desde el primer día.** El pipeline despliega solo
a staging tras cada merge.

## Decisión

Integración continua completa desde ahora: en cada pull request corren Ruff,
mypy y pytest con cobertura, y `main` está protegida exigiendo pipeline verde
más una aprobación. La entrega continua queda como script documentado y se
automatiza cuando exista acceso al servidor.

## Justificación

Separar integración de entrega permite tener la mitad valiosa funcionando hoy
sin depender de un acceso que no controlamos. La verificación automática es
además la única defensa real contra el código generado por IA: sin ella, el
riesgo de introducir errores sutiles crece con la velocidad.

El despliegue manual se descartó porque no es reproducible ni deja registro de
qué versión está corriendo. El script documentado con systemd cuesta lo mismo y
es auditable.

Automatizar la entrega antes de tener el servidor habría significado escribir
un pipeline que no podemos probar, que es peor que no tenerlo.

## Consecuencias

El primer despliegue a staging se hará a mano siguiendo `docs/despliegue.md`, y
recién después se automatiza. Queda registrado como hito bloqueado en el plan
de trabajo y como riesgo con dueño.

El pipeline mide y publica la cobertura, pero no la usa como umbral de corte.
Con el dominio todavía sin modelos, un mínimo obligatorio solo induciría tests
de relleno para mantener el pipeline verde. Cuando el portal tenga lógica de
negocio se evaluará fijar un umbral con sentido.

El rollback requiere que las migraciones sean compatibles hacia atrás dentro de
un mismo sprint: no se borran ni renombran columnas en la misma versión en que
se dejan de usar. Esa regla queda en el documento de despliegue.
