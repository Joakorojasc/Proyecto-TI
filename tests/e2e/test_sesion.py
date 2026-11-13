"""Sesión: lo que pasa sin entrar, al equivocarse de clave y al salir."""

import re

from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from tests.e2e.conftest import CuentaDemo
from tests.e2e.paginas import RUTA_INSTANCIAS, RUTA_LOGIN, iniciar_sesion, ir_a, menu


def manda_al_login(page: Page, base: str) -> None:
    """Comprueba que se está en el login, venga o no con el parámetro next."""
    expect(page).to_have_url(re.compile(rf"^{re.escape(base)}{RUTA_LOGIN}(\?.*)?$"))
    expect(page.get_by_role("button", name="Entrar")).to_be_visible()


def test_sin_sesion_el_listado_manda_al_login(page: Page, live_server: LiveServer) -> None:
    base = live_server.url

    ir_a(page, base, RUTA_INSTANCIAS)

    manda_al_login(page, base)


def test_clave_incorrecta_deja_en_el_login_con_un_error(
    page: Page, live_server: LiveServer, cuenta: CuentaDemo
) -> None:
    base = live_server.url
    ir_a(page, base, RUTA_LOGIN)

    page.locator("input[name='username']").fill(cuenta.correo)
    page.locator("input[name='password']").fill("NoEsLaClave999!")
    page.get_by_role("button", name="Entrar").click()

    manda_al_login(page, base)
    expect(page.get_by_text(re.compile(r"correct", re.IGNORECASE))).to_be_visible()
    expect(page.get_by_role("heading", name="Portal de Instancias")).not_to_be_visible()


def test_cerrar_sesion_vuelve_al_login_y_ya_no_deja_entrar(
    page: Page, live_server: LiveServer, cuenta: CuentaDemo
) -> None:
    base = live_server.url
    iniciar_sesion(page, base, cuenta.correo, cuenta.clave)

    menu(page).get_by_role("button", name="Cerrar Sesión").click()
    manda_al_login(page, base)

    ir_a(page, base, RUTA_INSTANCIAS)
    manda_al_login(page, base)
