"""Estadísticas: período informado, sumas del resumen y filas por instancia.

Los números esperados salen de INSTANCIAS en conftest.py, con febrero de 2026
como último período medido.
"""

from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import InstanciaMoodle
from tests.e2e.conftest import CuentaDemo
from tests.e2e.paginas import RUTA_ESTADISTICAS, iniciar_sesion, ir_por_menu, migas


def resumen(page: Page) -> dict[str, str]:
    """Las tarjetas del resumen, de etiqueta a valor."""
    seccion = page.get_by_role("region", name="Resumen del período")
    expect(seccion).to_be_visible()
    valores: dict[str, str] = {}
    for tarjeta in seccion.get_by_role("article").all():
        # Entre párrafos el navegador deja líneas en blanco.
        lineas = [linea.strip() for linea in tarjeta.inner_text().splitlines() if linea.strip()]
        valor, etiqueta, *_ = lineas
        valores[etiqueta] = valor
    return valores


def fila(page: Page, nombre: str) -> list[str]:
    """Las celdas de la fila de una instancia en la tabla "Por instancia"."""
    tabla = page.get_by_role("region", name="Por instancia").get_by_role("table")
    celdas = tabla.get_by_role("row").filter(has_text=nombre).get_by_role("cell")
    return [texto.strip() for texto in celdas.all_inner_texts()]


def test_informa_el_ultimo_periodo_con_las_sumas_de_sus_instancias(
    page: Page, live_server: LiveServer, cuenta: CuentaDemo
) -> None:
    base = live_server.url
    iniciar_sesion(page, base, cuenta.correo, cuenta.clave)

    ir_por_menu(page, "Estadísticas")

    expect(page).to_have_url(f"{base}{RUTA_ESTADISTICAS}")
    expect(page.get_by_text("Último período medido: Febrero 2026")).to_be_visible()
    assert migas(page) == ["Inicio", "Estadísticas"]

    # Febrero: 60 + 28 inscritos, 44 + 20 activos, 12 + 6 cursos, 4 + 2 categorías
    # y 156 + 54 matrículas sobre 18 cursos.
    tarjetas = resumen(page)
    assert tarjetas["Usuarios inscritos"] == "88"
    assert tarjetas["Usuarios activos"] == "64"
    assert tarjetas["Cursos"] == "18"
    assert tarjetas["Categorías"] == "6"
    assert tarjetas["Matriculados por curso"] == "11,7"
    assert tarjetas["Instancias con datos"] == "2 de 2"

    assert fila(page, "Campus Uno")[2:5] == ["60", "44", "12"]
    assert fila(page, "Campus Dos")[2:5] == ["28", "20", "6"]


def test_una_instancia_sin_medicion_en_el_ultimo_periodo_aparece_sin_datos(
    page: Page, live_server: LiveServer, cuenta: CuentaDemo
) -> None:
    """Campus Tres solo midió enero, así que en febrero no tiene números."""
    rezagada = InstanciaMoodle.objects.create(
        cliente=cuenta.cliente,
        nombre="Campus Tres",
        dominio="campus-tres.demo.invalid",
        version="5.2-demo",
        estado="activa",
    )
    MedicionUsoMensual.objects.create(
        instancia=rezagada,
        mes=1,
        anio=2026,
        usuarios_activos=5,
        cantidad_cursos=2,
        cantidad_categorias=1,
        usuarios_inscritos=8,
        total_matriculas=10,
    )
    base = live_server.url
    iniciar_sesion(page, base, cuenta.correo, cuenta.clave)

    ir_por_menu(page, "Estadísticas")

    expect(page.get_by_text("Último período medido: Febrero 2026")).to_be_visible()
    assert fila(page, "Campus Tres")[2:] == ["Sin datos"] * 5
    tarjetas = resumen(page)
    assert tarjetas["Usuarios inscritos"] == "88"
    assert tarjetas["Instancias con datos"] == "2 de 3"
    expect(page.get_by_text("1 sin medición en este período")).to_be_visible()
