"""Aislamiento entre clientes, visto desde el navegador.

Las vistas ya tienen pruebas de esto. Acá se comprueba lo que de verdad llega a
la pantalla, que es lo único que una prueba de vista no puede asegurar.
"""

from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from tests.e2e.conftest import CuentaDemo
from tests.e2e.paginas import RUTA_INSTANCIAS, iniciar_sesion, ir_a, ir_por_menu

# Números que solo tiene el otro cliente.
NUMEROS_AJENOS = ("9999", "777")


def no_muestra_nada_ajeno(page: Page, ajena: CuentaDemo) -> None:
    """Revisa el texto completo de la página, no solo lo que está a la vista."""
    cuerpo = page.locator("body")
    for texto in (ajena.razon_social, *ajena.nombres, *NUMEROS_AJENOS):
        expect(cuerpo).not_to_contain_text(texto)


def test_no_ve_datos_de_otro_cliente_en_ninguna_pantalla(
    page: Page, live_server: LiveServer, cuenta: CuentaDemo, cuenta_ajena: CuentaDemo
) -> None:
    base = live_server.url
    iniciar_sesion(page, base, cuenta.correo, cuenta.clave)
    no_muestra_nada_ajeno(page, cuenta_ajena)

    ir_por_menu(page, "Mis Instancias")
    expect(page.get_by_role("link", name=cuenta.nombres[0])).to_be_visible()
    no_muestra_nada_ajeno(page, cuenta_ajena)

    ir_por_menu(page, "Estadísticas")
    expect(page.get_by_role("heading", name="Estadísticas", level=1)).to_be_visible()
    no_muestra_nada_ajeno(page, cuenta_ajena)


def test_pedir_a_mano_el_detalle_de_una_instancia_ajena_no_la_muestra(
    page: Page, live_server: LiveServer, cuenta: CuentaDemo, cuenta_ajena: CuentaDemo
) -> None:
    base = live_server.url
    ajena = cuenta_ajena.instancias[0]
    iniciar_sesion(page, base, cuenta.correo, cuenta.clave)

    respuesta = page.goto(f"{base}{RUTA_INSTANCIAS}{ajena.pk}/")

    assert respuesta is not None
    assert respuesta.status == 404
    no_muestra_nada_ajeno(page, cuenta_ajena)


def test_el_otro_cliente_si_ve_lo_suyo(
    page: Page, live_server: LiveServer, cuenta: CuentaDemo, cuenta_ajena: CuentaDemo
) -> None:
    """Control del anterior: el 404 se debe al aislamiento y no a una ruta mala."""
    base = live_server.url
    ajena = cuenta_ajena.instancias[0]
    iniciar_sesion(page, base, cuenta_ajena.correo, cuenta_ajena.clave)

    ir_a(page, base, f"{RUTA_INSTANCIAS}{ajena.pk}/")

    expect(page.get_by_role("heading", name=cuenta_ajena.nombres[0])).to_be_visible()
    expect(page.locator("body")).not_to_contain_text(cuenta.nombres[0])
