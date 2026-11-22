"""Fixtures de los recorridos en navegador.

Todo lo que vive en esta carpeta queda marcado como e2e, así que la corrida
normal de pytest no lo toca. Para correr los recorridos: pytest -m e2e
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth.models import User

from apps.clientes.models import Cliente, UsuarioPortal
from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import EstadoInstancia, InstanciaMoodle

CARPETA = Path(__file__).parent

CORREO = "demo@recorrido.invalid"
CLAVE = "ClaveSegura123!"
RAZON_SOCIAL = "Institución Recorrido SpA"
RUT = "76.123.456-0"

# Una medición es activos, cursos, categorías, inscritos y matrículas.
Medicion = tuple[int, int, int, int, int]
# Por instancia: nombre, dominio y las mediciones desde enero de 2026, mes a mes.
Instancias = tuple[tuple[str, str, tuple[Medicion, ...]], ...]

INSTANCIAS: Instancias = (
    ("Campus Uno", "campus-uno.demo.invalid", ((40, 10, 3, 55, 120), (44, 12, 4, 60, 156))),
    ("Campus Dos", "campus-dos.demo.invalid", ((18, 5, 2, 25, 40), (20, 6, 2, 28, 54))),
)

# El otro cliente. Nombres y números que no se confunden con los de la cuenta,
# para que comprobar que no aparecen sea concluyente.
CORREO_AJENO = "ajeno@recorrido.invalid"
RAZON_SOCIAL_AJENA = "Corporación Ajena Ltda"
RUT_AJENO = "77.654.321-7"
INSTANCIAS_AJENAS: Instancias = (
    (
        "Campus Ajeno",
        "campus-ajeno.demo.invalid",
        ((700, 30, 9, 9000, 900), (777, 31, 9, 9999, 999)),
    ),
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Marca como e2e cada test de esta carpeta, para que nadie se olvide.

    Recibe todos los tests de la corrida, no solo los de acá, así que hay que
    filtrar por carpeta antes de marcar.
    """
    for item in items:
        if CARPETA in item.path.parents:
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    """Escritorio de 1280x800. En anchos chicos la barra lateral se comporta distinto."""
    return {**browser_context_args, "viewport": {"width": 1280, "height": 800}}


@pytest.fixture(scope="session")
def orm_con_playwright() -> None:
    """Deja que el ORM funcione mientras Playwright tiene su loop andando.

    La API sincrónica de Playwright mantiene un loop de asyncio en este mismo
    hilo. Django detecta ese loop y corta cualquier consulta con
    SynchronousOnlyOperation, pensando que es una vista async mal escrita. Acá
    no hay nada async: el servidor de prueba corre en su propio hilo.

    Se activa solo cuando un recorrido lo pide, así la corrida normal conserva
    la protección.
    """
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"


@dataclass(frozen=True)
class CuentaDemo:
    """Lo que un recorrido necesita para entrar y reconocer lo que ve."""

    usuario: User
    correo: str
    clave: str
    cliente: Cliente
    razon_social: str
    instancias: list[InstanciaMoodle]
    nombres: tuple[str, ...]


def crear_cuenta(
    correo: str, razon_social: str, rut: str, instancias_datos: Instancias
) -> CuentaDemo:
    """Arma un cliente con su usuario, sus instancias y sus mediciones."""
    cliente = Cliente.objects.create(rut=rut, razon_social=razon_social, email_contacto=correo)
    usuario = User.objects.create_user(username=correo, email=correo, password=CLAVE)
    UsuarioPortal.objects.create(
        usuario=usuario,
        cliente=cliente,
        nombre="Demo Recorrido",
        email=correo,
        rol="Admin",
    )

    instancias: list[InstanciaMoodle] = []
    for nombre, dominio, mediciones in instancias_datos:
        instancia = InstanciaMoodle.objects.create(
            cliente=cliente,
            nombre=nombre,
            dominio=dominio,
            version="5.2-demo",
            estado=EstadoInstancia.ACTIVE,
        )
        for mes, valores in enumerate(mediciones, start=1):
            activos, cursos, categorias, inscritos, matriculas = valores
            MedicionUsoMensual.objects.create(
                instancia=instancia,
                mes=mes,
                anio=2026,
                usuarios_activos=activos,
                cantidad_cursos=cursos,
                cantidad_categorias=categorias,
                usuarios_inscritos=inscritos,
                total_matriculas=matriculas,
            )
        instancias.append(instancia)

    return CuentaDemo(
        usuario=usuario,
        correo=correo,
        clave=CLAVE,
        cliente=cliente,
        razon_social=razon_social,
        instancias=instancias,
        nombres=tuple(nombre for nombre, _, _ in instancias_datos),
    )


@pytest.fixture
def cuenta(orm_con_playwright: None, transactional_db: None) -> CuentaDemo:
    """Un cliente con dos instancias y dos períodos medidos, siempre con los mismos valores.

    Pide transactional_db porque el servidor de prueba corre en otro hilo y no
    ve lo que todavía esté dentro de una transacción sin confirmar.

    El orden de los dos primeros argumentos importa: el permiso del ORM tiene
    que quedar puesto antes de que se arme la base.

    No usa seed_demo a propósito: ese comando es del Bloque 1 y si le cambian
    los datos estos recorridos se caerían sin que nadie los haya tocado.
    """
    return crear_cuenta(CORREO, RAZON_SOCIAL, RUT, INSTANCIAS)


@pytest.fixture
def cuenta_ajena(orm_con_playwright: None, transactional_db: None) -> CuentaDemo:
    """Otro cliente en la misma base, para probar que sus datos no se cruzan."""
    return crear_cuenta(CORREO_AJENO, RAZON_SOCIAL_AJENA, RUT_AJENO, INSTANCIAS_AJENAS)
