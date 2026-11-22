"""Carga mediciones de uso mensual desde un CSV."""

import csv
import io
from collections import defaultdict
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import InstanciaMoodle

METRICAS = (
    "usuarios_inscritos",
    "usuarios_activos",
    "cantidad_cursos",
    "total_matriculas",
    "cantidad_categorias",
)
COLUMNAS = ("dominio", "anio", "mes", *METRICAS)
ANIO_MINIMO = 2000
# Lo máximo que cabe en un IntegerField de MariaDB. SQLite aceptaría más.
ENTERO_MAXIMO = 2_147_483_647


class FilaInvalida(Exception):
    """Una fila que no se puede cargar. El mensaje explica por qué."""


def _host(dominio: str | None) -> str:
    """Host del dominio, con o sin https://. Si no se puede interpretar devuelve vacío."""
    try:
        return InstanciaMoodle(dominio=dominio).dominio_host
    except ValueError:
        return ""


def _entero(texto: str, columna: str) -> int:
    try:
        valor = int(texto)
    except ValueError:
        raise FilaInvalida(f"{columna} debe ser un número entero: {texto!r}") from None
    if not 0 <= valor <= ENTERO_MAXIMO:
        raise FilaInvalida(f"{columna} está fuera de rango: {texto}")
    return valor


def _periodo(anio_texto: str, mes_texto: str) -> tuple[int, int]:
    if not anio_texto or not mes_texto:
        raise FilaInvalida("faltan anio o mes")
    anio = _entero(anio_texto, "anio")
    mes = _entero(mes_texto, "mes")
    if not 1 <= mes <= 12:
        raise FilaInvalida(f"mes debe estar entre 1 y 12: {mes}")
    if anio < ANIO_MINIMO:
        raise FilaInvalida(f"anio no parece válido: {anio}")
    # La pantalla informa el período más reciente. Uno futuro dejaría a las demás
    # instancias sin datos.
    hoy = timezone.localdate()
    if (anio, mes) > (hoy.year, hoy.month):
        raise FilaInvalida(f"el período {mes}/{anio} todavía no ocurre")
    return anio, mes


def _instancia(dominio: str, por_host: dict[str, list[InstanciaMoodle]]) -> InstanciaMoodle:
    if not dominio:
        raise FilaInvalida("falta el dominio")
    candidatas = por_host.get(_host(dominio), [])
    if not candidatas:
        raise FilaInvalida(f"no hay una instancia con el dominio {dominio}")
    if len(candidatas) > 1:
        raise FilaInvalida(f"el dominio {dominio} coincide con {len(candidatas)} instancias")
    return candidatas[0]


def _leer_filas(ruta: str) -> list[tuple[int, dict[str, str]]]:
    """Lee el archivo completo antes de escribir, para no dejar una carga a medias."""
    try:
        contenido = Path(ruta).read_text(encoding="utf-8-sig")
    except OSError as error:
        raise CommandError(f"No se pudo abrir {ruta}: {error}") from error
    except UnicodeDecodeError as error:
        raise CommandError(f"{ruta} no está en UTF-8. Guárdalo como CSV UTF-8.") from error

    # Excel en español separa con punto y coma.
    delimitador = ";" if ";" in contenido.partition("\n")[0] else ","
    lector = csv.DictReader(io.StringIO(contenido), delimiter=delimitador)
    lector.fieldnames = [columna.strip().lower() for columna in lector.fieldnames or []]
    faltantes = [columna for columna in COLUMNAS if columna not in lector.fieldnames]
    if faltantes:
        raise CommandError(f"Al archivo le faltan columnas: {', '.join(faltantes)}")
    try:
        return [(lector.line_num, fila) for fila in lector]
    except csv.Error as error:
        raise CommandError(f"No se pudo leer {ruta}: {error}") from error


class Command(BaseCommand):
    help = "Crea o actualiza mediciones de uso mensual desde un CSV. Las filas inválidas se omiten."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("archivo", help="Ruta del CSV")

    def handle(self, *args: Any, **options: Any) -> None:
        filas = _leer_filas(options["archivo"])

        por_host: defaultdict[str, list[InstanciaMoodle]] = defaultdict(list)
        for instancia in InstanciaMoodle.objects.all():
            # Sin este filtro, un dominio mal escrito en el CSV calzaría con las
            # instancias que no tienen dominio.
            if host := _host(instancia.dominio):
                por_host[host].append(instancia)

        creadas = actualizadas = omitidas = 0
        vistas: set[tuple[int, int, int]] = set()
        for linea, fila in filas:
            try:
                if self._cargar_fila(fila, por_host, vistas):
                    creadas += 1
                else:
                    actualizadas += 1
            except FilaInvalida as error:
                omitidas += 1
                self.stderr.write(f"Línea {linea}: {error}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Importación terminada: {creadas} creadas, {actualizadas} actualizadas "
                f"y {omitidas} omitidas."
            )
        )

    @staticmethod
    def _cargar_fila(
        fila: dict[str, str],
        por_host: dict[str, list[InstanciaMoodle]],
        vistas: set[tuple[int, int, int]],
    ) -> bool:
        """Guarda la fila y dice si creó una medición nueva."""
        # csv deja los valores sobrantes bajo la clave None. Suele ser un separador
        # de más, como un "1,950" sin comillas, que correría las columnas.
        if None in fila:
            raise FilaInvalida("tiene más columnas que el encabezado")

        valores = {columna: (fila.get(columna) or "").strip() for columna in COLUMNAS}
        instancia = _instancia(valores["dominio"], por_host)
        anio, mes = _periodo(valores["anio"], valores["mes"])
        # Una celda vacía significa que no hay dato, así que no borra el que ya estaba.
        metricas = {
            columna: _entero(valores[columna], columna) for columna in METRICAS if valores[columna]
        }
        if not metricas:
            raise FilaInvalida("no trae ninguna métrica")

        clave = (instancia.pk, anio, mes)
        if clave in vistas:
            raise FilaInvalida(f"el período {mes}/{anio} de esta instancia ya venía en el archivo")
        vistas.add(clave)

        try:
            _, creada = MedicionUsoMensual.objects.update_or_create(
                instancia=instancia, anio=anio, mes=mes, defaults=metricas
            )
        except MedicionUsoMensual.MultipleObjectsReturned:
            raise FilaInvalida(
                f"ya hay varias mediciones de {mes}/{anio} para esta instancia. Hay que revisarlas."
            ) from None
        return creada
