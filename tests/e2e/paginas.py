"""Acciones y lecturas que comparten los recorridos.

Los elementos se buscan por rol, etiqueta y texto visible. Nunca por clase de
CSS: las clases son de la hoja de estilos y van a seguir cambiando, y un
recorrido no tiene por qué romperse cuando alguien ajusta un color.
"""

from playwright.sync_api import Locator, Page, expect

RUTA_INICIO = "/"
RUTA_LOGIN = "/login/"
RUTA_INSTANCIAS = "/instancias/"
RUTA_ESTADISTICAS = "/estadisticas/"

MENU = "Navegación principal"
MIGAS = "Ruta de navegación"


def ir_a(page: Page, base: str, ruta: str) -> None:
    """Abre una ruta del portal en el servidor de prueba."""
    page.goto(f"{base}{ruta}")


def iniciar_sesion(page: Page, base: str, correo: str, clave: str) -> None:
    """Entra por el formulario real y espera a quedar en la portada.

    Los campos se buscan por su atributo name porque es el contrato que usa la
    vista. La etiqueta visible dice "Correo electrónico" y podría cambiar.
    """
    ir_a(page, base, RUTA_LOGIN)
    page.locator("input[name='username']").fill(correo)
    page.locator("input[name='password']").fill(clave)
    page.get_by_role("button", name="Entrar").click()
    expect(page).to_have_url(f"{base}{RUTA_INICIO}")


def menu(page: Page) -> Locator:
    """La barra lateral, por su aria-label."""
    return page.get_by_role("complementary", name=MENU)


def ir_por_menu(page: Page, titulo: str) -> None:
    """Hace clic en una entrada de la barra lateral."""
    menu(page).get_by_role("link", name=titulo).click()


def nav_migas(page: Page) -> Locator:
    """La ruta de navegación, por su aria-label.

    Hay que acotar a este nav porque "Inicio" y "Mis Instancias" también son
    enlaces de la barra lateral.
    """
    return page.get_by_role("navigation", name=MIGAS)


def migas(page: Page) -> list[str]:
    """Los textos de la ruta de navegación, en orden."""
    return [texto.strip() for texto in nav_migas(page).get_by_role("listitem").all_inner_texts()]


def ir_por_migas(page: Page, titulo: str) -> None:
    """Hace clic en un eslabón de la ruta de navegación."""
    nav_migas(page).get_by_role("link", name=titulo).click()
