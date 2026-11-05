# Documento de términos de Edocere

El PDF incluido es una copia binaria sin modificaciones de `T&C Moodle.pdf`,
proporcionado por Edocere en Drive:
https://drive.google.com/file/d/11TU5NbCYTaPEpTqWjLYpg7xZ5X0WjbEq/view

SHA-256: `b9f8c61b0d559eda0114ec7e92355a119b5227b6c80c805d45a008b11a46b139`.
El identificador `sha256-<hash completo>` es técnico e interno. El PDF no
declara una versión legal oficial; no se le atribuye una.

## Discrepancia pendiente de validación con Edocere

El PDF vincula la aceptación con la recepción de credenciales de administración.
La reunión del 23 de octubre de 2026 solicitó aceptación explícita antes de crear
Moodle y se acordó recogerla al registrar la institución. Se implementa ese flujo
sin cambiar el PDF. Edocere debe validar la correspondencia entre ambos mecanismos;
esta implementación no afirma que esa discrepancia legal esté resuelta.

## Uso y nuevas versiones

El PDF se entrega por una vista pública de Django desde el archivo empaquetado;
el usuario del portal no necesita una cuenta de Drive. No se transcribe su texto.

Para cambiar el documento, añadir el nuevo PDF oficial con otro nombre/hash y
actualizar `VERSION_TERMINOS` y `DOCUMENTOS_TERMINOS` en `apps/clientes/terminos.py`.
Conservar los archivos y entradas anteriores para poder consultar lo aceptado.
No reemplazar un PDF manteniendo su identificador. Las aceptaciones anteriores
se conservan, pero no se consideran vigentes para la nueva versión.

Bloque 2 puede consultar `tiene_aceptacion_vigente(cliente)` desde ese módulo.
La consulta no concede permisos sobre la institución ni bloquea instancias por sí
sola: el otro bloque debe comprobar pertenencia y autorización antes de usarla.

Las aceptaciones se crean después de validar la casilla y versión. El usuario
debe estar vinculado al cliente por `UsuarioPortal`; se registra su usuario Django.
El alta de cuenta y su aceptación comparten transacción. Repetir una aceptación no
reemplaza su actor ni fecha originales. Clientes anteriores y demo no se aceptan
automáticamente. La ruta antigua de alta sin usuario redirige al registro completo.
