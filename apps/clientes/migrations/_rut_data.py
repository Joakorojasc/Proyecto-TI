"""Conversión segura compartida por las dos rutas históricas de migración.

Conservar este módulo: las migraciones publicadas lo usan para instalaciones
nuevas. 0005 vuelve a aplicarlo en bases que ya tenían una de las dos rutas.
"""

from django.apps.registry import Apps
from django.core.exceptions import ValidationError
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from apps.clientes.validators import normalizar_rut


def normalizar_ruts(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Cliente = apps.get_model("clientes", "Cliente")
    clientes = Cliente.objects.using(schema_editor.connection.alias)
    # Los destinos son los RUT que ya usa dev. Los numéricos anteriores solo
    # identifican datos demo si también coinciden nombre y correo del seed.
    demo = [
        ("DEMO-PEQUENO-001", "90000001-4", "76543210-3", "Empresa Demo Pequeña SpA"),
        ("DEMO-MEDIANO-001", "90000002-2", "77777777-7", "Empresa Demo Mediana SpA"),
        ("DEMO-ANUAL-001", "90000003-0", "65123456-5", "Organización Demo Anual SpA"),
    ]
    cambios: list[tuple[int, str | None]] = []
    identificadores: dict[str, list[int]] = {}
    errores: list[str] = []
    registros = clientes.select_for_update().order_by("pk").values_list(
        "pk", "rut", "razon_social", "email_contacto"
    )
    for pk, rut, nombre, correo in registros:
        if rut is None or not rut.strip():
            nuevo = None
        else:
            valor = rut.strip()
            for codigo, anterior, destino, nombre_demo in demo:
                es_demo = nombre == nombre_demo and correo == "demo@ejemplo.invalid"
                if valor == codigo and es_demo:
                    valor = destino
                    break
            try:
                nuevo = normalizar_rut(valor)
            except ValidationError:
                errores.append(f"Cliente ID {pk}: RUT inválido o identificador demo sin confirmar")
                continue
            for codigo, anterior, destino, nombre_demo in demo:
                if (
                    nuevo == anterior
                    and nombre == nombre_demo
                    and correo == "demo@ejemplo.invalid"
                ):
                    nuevo = destino
                    break
            identificadores.setdefault(nuevo, []).append(pk)
        if nuevo != rut:
            cambios.append((pk, nuevo))

    for ids in identificadores.values():
        if len(ids) > 1:
            errores.append(f"RUT equivalente en clientes IDs {ids}")
    if errores:
        raise RuntimeError(
            "No se modificó ningún cliente. Corrige los RUT con los responsables de los datos "
            "y vuelve a ejecutar migrate; no elimines ni fusiones empresas automáticamente. "
            + "; ".join(errores)
        )
    for pk, rut in cambios:
        clientes.filter(pk=pk).update(rut=rut)
