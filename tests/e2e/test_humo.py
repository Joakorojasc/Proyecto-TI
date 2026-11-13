"""Recorrido de humo: comprueba que la infraestructura E2E sirve.

Un solo recorrido que toca de una vez el servidor real, los archivos estáticos,
el formulario de sesión, la navegación y las migas de pan. Si este pasa, sumar
recorridos es escribir tests y nada más.
"""

from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from tests.e2e.conftest import CuentaDemo
from tests.e2e.paginas import (
    RUTA_INSTANCIAS,
    iniciar_sesion,
    ir_por_menu,
    ir_por_migas,
    migas,
)


def test_entra_navega_a_sus_instancias_y_vuelve_por_las_migas(
    page: Page, live_server: LiveServer, cuenta: CuentaDemo
) -> None:
    base = live_server.url
    primera = cuenta.nombres[0]

    iniciar_sesion(page, base, cuenta.correo, cuenta.clave)
    expect(page.get_by_role("heading", name="Portal de Instancias")).to_be_visible()
    expect(page.get_by_text(cuenta.razon_social)).to_be_visible()

    ir_por_menu(page, "Mis Instancias")
    expect(page).to_have_url(f"{base}{RUTA_INSTANCIAS}")
    for nombre in cuenta.nombres:
        expect(page.get_by_role("link", name=nombre)).to_be_visible()

    page.get_by_role("link", name=primera).click()
    expect(page.get_by_role("heading", name=primera)).to_be_visible()
    assert migas(page) == ["Inicio", "Mis Instancias", primera]

    ir_por_migas(page, "Mis Instancias")
    expect(page).to_have_url(f"{base}{RUTA_INSTANCIAS}")
    expect(page.get_by_role("heading", name="Mis Instancias")).to_be_visible()
