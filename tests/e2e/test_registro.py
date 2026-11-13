"""Registro de una institución nueva por el formulario real.

Los campos se buscan por su atributo name, igual que en el login: es el contrato
que usa la vista. El hidden version_terminos ya viene con valor y no se toca.
"""

from django.contrib.auth.models import User
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from apps.clientes.models import Cliente, UsuarioPortal
from tests.e2e.conftest import CLAVE
from tests.e2e.paginas import RUTA_INSTANCIAS, ir_a, menu

RUTA_REGISTRO = "/registro/"

# Distintos de los de cuenta y cuenta_ajena. El RUT tiene dígito verificador válido.
CORREO_NUEVO = "nueva@recorrido.invalid"
RUT_NUEVO = "78.111.222-4"
RAZON_SOCIAL_NUEVA = "Fundación Registro Nuevo"
NOMBRE_NUEVO = "Camila"
APELLIDO_NUEVO = "Soto"


def abrir_documento_terminos(page: Page) -> None:
    """Abre el PDF en la pestaña nueva, que es lo que habilita la casilla.

    El portal exige que el documento se haya pedido al servidor; sin eso la
    casilla llega deshabilitada y el registro se rechaza.
    """
    with page.expect_popup() as pestana:
        page.get_by_role("link", name="Leer el documento completo").click()
    pestana.value.close()


def llenar_registro(page: Page, base: str) -> None:
    """Abre el registro y completa todo menos los términos."""
    ir_a(page, base, RUTA_REGISTRO)
    page.locator("input[name='username']").fill(CORREO_NUEVO)
    page.locator("input[name='password1']").fill(CLAVE)
    page.locator("input[name='password2']").fill(CLAVE)
    page.locator("input[name='first_name']").fill(NOMBRE_NUEVO)
    page.locator("input[name='last_name']").fill(APELLIDO_NUEVO)
    page.locator("input[name='razon_social']").fill(RAZON_SOCIAL_NUEVA)
    page.locator("input[name='rut']").fill(RUT_NUEVO)


def test_registra_una_institucion_y_queda_con_sesion_en_el_listado(
    orm_con_playwright: None, transactional_db: None, page: Page, live_server: LiveServer
) -> None:
    base = live_server.url
    llenar_registro(page, base)
    casilla = page.locator("input[name='acepta_terminos']")
    expect(casilla).to_be_disabled()

    abrir_documento_terminos(page)
    casilla.check()
    page.get_by_role("button", name="Crear Cuenta").click()

    expect(page).to_have_url(f"{base}{RUTA_INSTANCIAS}")
    expect(page.get_by_role("heading", name="Mis Instancias")).to_be_visible()
    expect(menu(page).get_by_role("button", name="Cerrar Sesión")).to_be_visible()
    expect(page.get_by_text("Aún no tienes instancias Moodle asociadas.")).to_be_visible()
    assert User.objects.filter(username=CORREO_NUEVO).exists()
    assert Cliente.objects.filter(razon_social=RAZON_SOCIAL_NUEVA).exists()
    portal = UsuarioPortal.objects.get(email=CORREO_NUEVO)
    assert portal.nombre == f"{NOMBRE_NUEVO} {APELLIDO_NUEVO}"


def test_sin_aceptar_los_terminos_no_crea_la_cuenta(
    orm_con_playwright: None, transactional_db: None, page: Page, live_server: LiveServer
) -> None:
    base = live_server.url
    llenar_registro(page, base)
    abrir_documento_terminos(page)

    page.get_by_role("button", name="Crear Cuenta").click()

    expect(page).to_have_url(f"{base}{RUTA_REGISTRO}")
    expect(
        page.get_by_text("Debes aceptar los términos y condiciones para continuar.")
    ).to_be_visible()
    assert not User.objects.filter(username=CORREO_NUEVO).exists()
    assert not Cliente.objects.filter(razon_social=RAZON_SOCIAL_NUEVA).exists()


def test_sin_abrir_el_documento_la_casilla_queda_bloqueada(
    orm_con_playwright: None, transactional_db: None, page: Page, live_server: LiveServer
) -> None:
    base = live_server.url
    llenar_registro(page, base)

    casilla = page.locator("input[name='acepta_terminos']")
    expect(casilla).to_be_disabled()
    expect(page.get_by_text("Abre el documento para poder aceptarlo.")).to_be_visible()

    abrir_documento_terminos(page)

    expect(casilla).to_be_enabled()
    expect(page.get_by_text("Abre el documento para poder aceptarlo.")).to_have_count(0)
