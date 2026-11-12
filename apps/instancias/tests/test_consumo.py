import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.consumo import calcular_consumo
from apps.instancias.models import InstanciaMoodle
from apps.planes.models import Plan, Suscripcion


@pytest.mark.parametrize(
    ("activos", "estado", "disponibles"),
    [(799, "normal", 201), (800, "advertencia", 200), (1000, "limite", 0), (1200, "limite", 0)],
)
def test_calculo_y_umbrales(activos: int, estado: str, disponibles: int) -> None:
    medicion = MedicionUsoMensual(anio=2026, mes=3, usuarios_activos=activos)
    suscripcion = Suscripcion(plan=Plan(limite_usuarios=1000))
    consumo = calcular_consumo(medicion, [suscripcion])

    assert consumo.porcentaje == activos / 10
    assert consumo.estado == estado
    assert consumo.disponibles == disponibles
    assert consumo.valor_barra == min(activos, 1000)


def test_datos_incompletos_y_tramo_gratuito() -> None:
    medicion = MedicionUsoMensual(anio=2026, mes=3, usuarios_activos=12)
    plan = Suscripcion(plan=Plan(limite_usuarios=100))
    gratis = Suscripcion(plan=Plan(tipo_plan="Mensual", limite_usuarios=10))
    indefinido = Suscripcion(plan=Plan(limite_usuarios=None))

    assert calcular_consumo(None, [plan]).activos is None
    assert calcular_consumo(medicion, []).mensaje_plan == "Sin suscripción activa"
    assert calcular_consumo(medicion, [plan, gratis]).limite is None
    for suscripcion in (gratis, indefinido):
        consumo = calcular_consumo(medicion, [suscripcion])
        assert consumo.activos == 12
        assert consumo.porcentaje is None
        assert consumo.disponibles is None


@pytest.mark.django_db
def test_portal_y_admin_muestran_consumo_por_instancia(
    client: Client, usuario_cliente: User, superadmin: User
) -> None:
    cliente = usuario_cliente.usuarioportal.cliente
    assert cliente is not None
    otro_cliente = Cliente.objects.create(razon_social="Otra institución")
    for nombre, propietario, activos, limite in (
        ("Campus A", cliente, 80, 100),
        ("Campus B", cliente, 150, 120),
        ("Campus ajeno", otro_cliente, 33, 500),
    ):
        instancia = InstanciaMoodle.objects.create(cliente=propietario, nombre=nombre)
        plan = Plan.objects.create(nombre=f"Plan {nombre}", limite_usuarios=limite)
        Suscripcion.objects.create(
            instancia=instancia, cliente=propietario, plan=plan, estado="activa"
        )
        MedicionUsoMensual.objects.create(
            instancia=instancia, anio=2026, mes=3, usuarios_activos=activos
        )
        MedicionUsoMensual.objects.create(
            instancia=instancia, anio=2025, mes=12, usuarios_activos=1
        )

    client.force_login(usuario_cliente)
    admin_url = reverse("admin:instancias_instanciamoodle_changelist")
    assert client.get(admin_url).status_code == 302
    portal = client.get(reverse("instancias:lista"))
    client.force_login(superadmin)
    admin = client.get(admin_url)

    for respuesta in (portal, admin):
        assert respuesta.status_code == 200
        contenido = respuesta.content.decode()
        assert "80 de 100 usuarios activos (80 %)" in contenido
        assert "150 de 120 usuarios activos (125 %)" in contenido
        assert "marzo 2026" in contenido.lower()
        assert "consumo-instancia__barra--advertencia" in contenido
        assert "consumo-instancia__barra--limite" in contenido
        assert "1 de 100 usuarios activos" not in contenido
    assert "33 de 500 usuarios activos" not in portal.content.decode()
    assert "33 de 500 usuarios activos" in admin.content.decode()
