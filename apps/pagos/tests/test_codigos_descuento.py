"""Pruebas de los códigos de descuento: modelo, elegir plan, checkout y admin."""

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, UsuarioPortal
from apps.pagos.models import CodigoDescuento, Pago
from apps.pagos.services import aplicar_descuento, buscar_codigo, precio_de_referencia
from apps.planes.models import Plan, Suscripcion

pytestmark = pytest.mark.django_db

CLAVE = "Edocere.2026"


@pytest.fixture
def cliente() -> Cliente:
    return Cliente.objects.create(rut="76543210-3", razon_social="Cliente Descuentos")


@pytest.fixture
def usuario(cliente: Cliente) -> User:
    cuenta = User.objects.create_user("pagador@test.cl", password=CLAVE)
    UsuarioPortal.objects.create(usuario=cuenta, cliente=cliente, rol="Admin")
    return cuenta


@pytest.fixture
def plan() -> Plan:
    return Plan.objects.create(
        nombre="Plan Anual Test",
        tipo_plan="anual",
        precio_base=Decimal("10000.00"),
        precio_por_usuario=Decimal("0.00"),
    )


@pytest.fixture
def suscripcion(cliente: Cliente, plan: Plan) -> Suscripcion:
    return Suscripcion.objects.create(
        cliente=cliente, plan=plan, estado="pendiente", fecha_inicio=timezone.now()
    )


@pytest.fixture
def codigo(plan: Plan) -> CodigoDescuento:
    return CodigoDescuento.objects.create(codigo="PUC20", porcentaje=20, plan=plan)


@pytest.fixture
def suscripcion_con_codigo(suscripcion: Suscripcion, codigo: CodigoDescuento) -> Suscripcion:
    suscripcion.codigo_descuento = codigo
    suscripcion.save()
    return suscripcion


def _url_checkout(suscripcion: Suscripcion) -> str:
    return reverse("pagos:checkout", args=[suscripcion.pk])


def _pagar(client: Client, suscripcion: Suscripcion, resultado: str = "aprobado") -> Any:
    datos = {"ultimos_4_digitos": "4242", "marca_tarjeta": "Visa", "resultado": resultado}
    return client.post(_url_checkout(suscripcion), datos)


def _elegir_plan(client: Client, cliente: Cliente, plan: Plan, **extra: str) -> Any:
    url = reverse("planes:seleccionar_plan", args=[cliente.pk])
    return client.post(url, {"plan": plan.pk, **extra})


# --- Modelo ----------------------------------------------------------------


def test_el_codigo_se_guarda_en_mayusculas_y_sin_espacios(plan: Plan) -> None:
    creado = CodigoDescuento.objects.create(codigo="  puc20 ", porcentaje=20, plan=plan)

    assert creado.codigo == "PUC20"


@pytest.mark.parametrize("porcentaje", [0, 101])
def test_porcentaje_fuera_de_rango_no_es_valido(plan: Plan, porcentaje: int) -> None:
    with pytest.raises(ValidationError):
        CodigoDescuento(codigo="MALO", porcentaje=porcentaje, plan=plan).full_clean()


def test_un_codigo_usado_en_un_pago_no_se_puede_borrar(
    codigo: CodigoDescuento, suscripcion: Suscripcion
) -> None:
    Pago.objects.create(
        suscripcion=suscripcion,
        monto=Decimal("8000.00"),
        estado=Pago.ESTADO_APROBADO,
        codigo_descuento=codigo,
    )

    with pytest.raises(ProtectedError):
        codigo.delete()


def test_un_codigo_usado_en_una_suscripcion_no_se_puede_borrar(
    codigo: CodigoDescuento, suscripcion_con_codigo: Suscripcion
) -> None:
    with pytest.raises(ProtectedError):
        codigo.delete()


# --- Cálculo ---------------------------------------------------------------


def test_buscar_codigo_normaliza_el_texto(codigo: CodigoDescuento, plan: Plan) -> None:
    assert buscar_codigo(" puc20 ", plan) == codigo


@pytest.mark.parametrize("texto", ["", "   ", None, "NOEXISTE"])
def test_buscar_codigo_sin_coincidencia(
    texto: str | None, codigo: CodigoDescuento, plan: Plan
) -> None:
    assert buscar_codigo(texto, plan) is None


def test_un_codigo_inactivo_no_se_encuentra(codigo: CodigoDescuento, plan: Plan) -> None:
    codigo.activo = False
    codigo.save()

    assert buscar_codigo("PUC20", plan) is None


def test_un_codigo_no_vale_para_otro_plan(codigo: CodigoDescuento) -> None:
    otro = Plan.objects.create(nombre="Otro Plan", tipo_plan="anual", precio_base=Decimal("500"))

    assert buscar_codigo("PUC20", otro) is None


def test_aplicar_descuento_calcula_el_porcentaje(codigo: CodigoDescuento) -> None:
    resultado = aplicar_descuento(Decimal("10000.00"), codigo)

    assert resultado.descuento == Decimal("2000.00")
    assert resultado.precio_final == Decimal("8000.00")
    assert resultado.codigo == codigo


def test_aplicar_descuento_redondea_a_dos_decimales(plan: Plan) -> None:
    resultado = aplicar_descuento(
        Decimal("999.99"), CodigoDescuento(codigo="X15", porcentaje=15, plan=plan)
    )

    assert resultado.descuento == Decimal("150.00")
    assert resultado.precio_final == Decimal("849.99")


def test_sin_codigo_el_precio_no_cambia() -> None:
    resultado = aplicar_descuento(Decimal("10000.00"), None)

    assert resultado.descuento == Decimal("0.00")
    assert resultado.precio_final == Decimal("10000.00")
    assert resultado.codigo is None


def test_precio_de_referencia_segun_el_tipo_de_plan() -> None:
    anual = Plan(tipo_plan="anual", precio_base=Decimal("1800"), precio_por_usuario=Decimal("5"))
    mensual = Plan(
        tipo_plan="mensual", precio_base=Decimal("1800"), precio_por_usuario=Decimal("5")
    )

    assert precio_de_referencia(anual) == Decimal("1800")
    assert precio_de_referencia(mensual) == Decimal("5")


# --- Elegir plan -----------------------------------------------------------


def test_el_campo_de_codigo_aparece_solo_en_los_planes_con_codigos(
    client: Client, cliente: Cliente, usuario: User, plan: Plan, codigo: CodigoDescuento
) -> None:
    sin_codigos = Plan.objects.create(
        nombre="Plan Sin Codigos", tipo_plan="anual", precio_base=Decimal("500")
    )
    client.force_login(usuario)

    respuesta = client.get(reverse("planes:seleccionar_plan", args=[cliente.pk]))

    html = respuesta.content.decode()
    assert f'name="codigo_{plan.pk}"' in html
    assert f'name="codigo_{sin_codigos.pk}"' not in html


def test_un_codigo_inactivo_no_muestra_el_campo(
    client: Client, cliente: Cliente, usuario: User, plan: Plan, codigo: CodigoDescuento
) -> None:
    codigo.activo = False
    codigo.save()
    client.force_login(usuario)

    respuesta = client.get(reverse("planes:seleccionar_plan", args=[cliente.pk]))

    assert f'name="codigo_{plan.pk}"' not in respuesta.content.decode()


def test_elegir_plan_con_un_codigo_valido_lo_recuerda(
    client: Client, cliente: Cliente, usuario: User, plan: Plan, codigo: CodigoDescuento
) -> None:
    client.force_login(usuario)

    respuesta = _elegir_plan(client, cliente, plan, **{f"codigo_{plan.pk}": "puc20"})

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("instancias:crear", args=[cliente.pk, plan.pk])
    assert client.session["codigo_descuento"] == {"plan_id": plan.pk, "codigo": "PUC20"}


def test_elegir_plan_sin_codigo_no_guarda_nada(
    client: Client, cliente: Cliente, usuario: User, plan: Plan, codigo: CodigoDescuento
) -> None:
    client.force_login(usuario)

    respuesta = _elegir_plan(client, cliente, plan)

    assert respuesta.status_code == 302
    assert "codigo_descuento" not in client.session


def test_elegir_plan_con_un_codigo_inexistente_no_avanza(
    client: Client, cliente: Cliente, usuario: User, plan: Plan, codigo: CodigoDescuento
) -> None:
    client.force_login(usuario)

    respuesta = _elegir_plan(client, cliente, plan, **{f"codigo_{plan.pk}": "NOEXISTE"})

    assert respuesta.status_code == 200
    assert respuesta.context["form"].non_field_errors()
    assert "codigo_descuento" not in client.session


def test_elegir_plan_con_un_codigo_de_otro_plan_no_avanza(
    client: Client, cliente: Cliente, usuario: User, plan: Plan, codigo: CodigoDescuento
) -> None:
    otro = Plan.objects.create(nombre="Otro Plan", tipo_plan="anual", precio_base=Decimal("500"))
    CodigoDescuento.objects.create(codigo="OTRO10", porcentaje=10, plan=otro)
    client.force_login(usuario)

    respuesta = _elegir_plan(client, cliente, plan, **{f"codigo_{plan.pk}": "OTRO10"})

    assert respuesta.status_code == 200
    assert "codigo_descuento" not in client.session


# --- Checkout --------------------------------------------------------------


def test_el_checkout_sin_codigo_muestra_el_precio_completo(
    client: Client, usuario: User, suscripcion: Suscripcion
) -> None:
    client.force_login(usuario)

    respuesta = client.get(_url_checkout(suscripcion))

    assert respuesta.status_code == 200
    assert respuesta.context["detalle"].precio_final == Decimal("10000.00")


def test_el_checkout_aplica_el_codigo_de_la_suscripcion(
    client: Client, usuario: User, suscripcion_con_codigo: Suscripcion
) -> None:
    client.force_login(usuario)

    respuesta = client.get(_url_checkout(suscripcion_con_codigo))

    assert respuesta.context["detalle"].precio_final == Decimal("8000.00")
    assert respuesta.context["detalle"].descuento == Decimal("2000.00")


def test_el_pago_aprobado_queda_registrado_con_el_descuento(
    client: Client, usuario: User, suscripcion_con_codigo: Suscripcion, codigo: CodigoDescuento
) -> None:
    client.force_login(usuario)

    respuesta = _pagar(client, suscripcion_con_codigo)

    assert respuesta.status_code == 302
    pago = Pago.objects.get()
    assert pago.monto == Decimal("8000.00")
    assert pago.monto_descuento == Decimal("2000.00")
    assert pago.codigo_descuento == codigo
    assert pago.estado == Pago.ESTADO_APROBADO


def test_el_pago_sin_codigo_guarda_el_precio_completo(
    client: Client, usuario: User, suscripcion: Suscripcion
) -> None:
    client.force_login(usuario)

    _pagar(client, suscripcion)

    pago = Pago.objects.get()
    assert pago.monto == Decimal("10000.00")
    assert pago.codigo_descuento is None
    assert pago.monto_descuento is None


# --- Admin -----------------------------------------------------------------


def test_el_superadmin_ve_y_crea_codigos_de_descuento(
    client: Client, codigo: CodigoDescuento
) -> None:
    root = User.objects.create_superuser("super-test", "super@test.cl", CLAVE)
    client.force_login(root)

    respuesta = client.get(reverse("admin:pagos_codigodescuento_changelist"))

    assert respuesta.status_code == 200
    assert "PUC20" in respuesta.content.decode()
    assert client.get(reverse("admin:pagos_codigodescuento_add")).status_code == 200
