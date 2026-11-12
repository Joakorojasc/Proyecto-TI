"""Pruebas del backoffice del superadministrador (Bloque 4)."""

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, UsuarioPortal
from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import InstanciaMoodle
from apps.pagos.models import DocumentoTributario, Pago
from apps.planes.models import Plan, Suscripcion

pytestmark = pytest.mark.django_db

CLAVE_VALIDA = "Edocere.2026"

LISTADOS = [
    "admin:clientes_cliente_changelist",
    "admin:instancias_instanciamoodle_changelist",
    "admin:planes_plan_changelist",
    "admin:planes_suscripcion_changelist",
    "admin:estadisticas_medicionusomensual_changelist",
    "admin:pagos_pago_changelist",
    "admin:pagos_documentotributario_changelist",
]
ALTAS = [
    "admin:clientes_cliente_add",
    "admin:instancias_instanciamoodle_add",
    "admin:planes_plan_add",
]


@pytest.fixture
def datos_comerciales(db: None) -> Cliente:
    """Un cliente con instancia, suscripción, medición, pago y documento."""
    cliente = Cliente.objects.create(rut="76543210-3", razon_social="Empresa Backoffice")
    plan = Plan.objects.create(nombre="Plan Mensual", tipo_plan="mensual")
    instancia = InstanciaMoodle.objects.create(
        cliente=cliente, nombre="Campus", dominio="https://campus.edocere.com"
    )
    suscripcion = Suscripcion.objects.create(
        instancia=instancia,
        cliente=cliente,
        plan=plan,
        estado="activa",
        fecha_inicio=timezone.now(),
    )
    MedicionUsoMensual.objects.create(
        instancia=instancia,
        mes=2,
        anio=2026,
        usuarios_activos=10,
        cantidad_cursos=3,
        cantidad_categorias=1,
    )
    pago = Pago.objects.create(
        suscripcion=suscripcion,
        monto=Decimal("1000.00"),
        fecha_pago=timezone.now(),
        estado="pagado",
    )
    DocumentoTributario.objects.create(
        pago=pago, tipo_documento="factura", folio=1, url_pdf="https://ejemplo.com/f.pdf"
    )
    return cliente


def _formularios_de_inlines(respuesta: Any) -> dict[str, str]:
    """Datos de control que el admin exige para los bloques asociados (inlines)."""
    datos: dict[str, str] = {}
    for inline in respuesta.context["inline_admin_formsets"]:
        prefijo = inline.formset.prefix
        datos[f"{prefijo}-TOTAL_FORMS"] = "0"
        datos[f"{prefijo}-INITIAL_FORMS"] = "0"
        datos[f"{prefijo}-MIN_NUM_FORMS"] = "0"
        datos[f"{prefijo}-MAX_NUM_FORMS"] = "1000"
    return datos


def _enviar_alta(client: Client, nombre_url: str, datos: dict[str, Any]) -> Any:
    url = reverse(nombre_url)
    completos = {**datos, **_formularios_de_inlines(client.get(url))}
    return client.post(url, completos)


# --- Accesos ---------------------------------------------------------------


@pytest.mark.parametrize("nombre_url", LISTADOS + ALTAS)
def test_anonimo_es_enviado_al_login_del_admin(client: Client, nombre_url: str) -> None:
    respuesta = client.get(reverse(nombre_url))

    assert respuesta.status_code == 302
    assert "/admin/login/" in respuesta["Location"]


@pytest.mark.parametrize("nombre_url", LISTADOS + ALTAS)
def test_usuario_cliente_no_accede_al_admin(
    client: Client, usuario_cliente: User, nombre_url: str
) -> None:
    client.force_login(usuario_cliente)

    respuesta = client.get(reverse(nombre_url))

    assert respuesta.status_code == 302
    assert "/admin/login/" in respuesta["Location"]


@pytest.mark.parametrize("nombre_url", LISTADOS + ALTAS)
def test_staff_sin_permisos_recibe_403(client: Client, nombre_url: str) -> None:
    operador = User.objects.create_user("operador", password=CLAVE_VALIDA, is_staff=True)
    client.force_login(operador)

    assert client.get(reverse(nombre_url)).status_code == 403


# --- Listas y filtros ------------------------------------------------------


@pytest.mark.parametrize("nombre_url", LISTADOS)
def test_superadmin_ve_los_listados_con_datos(
    client: Client, superadmin: User, datos_comerciales: Cliente, nombre_url: str
) -> None:
    client.force_login(superadmin)

    assert client.get(reverse(nombre_url)).status_code == 200
    assert client.get(reverse(nombre_url), {"q": "Backoffice"}).status_code == 200


def test_filtro_de_mes_en_mediciones(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    client.force_login(superadmin)
    url = reverse("admin:estadisticas_medicionusomensual_changelist")

    assert client.get(url, {"mes": "2"}).context["cl"].result_count == 1
    assert client.get(url, {"mes": "3"}).context["cl"].result_count == 0


def test_filtro_de_tipo_de_dominio_en_instancias(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    client.force_login(superadmin)
    url = reverse("admin:instancias_instanciamoodle_changelist")

    assert client.get(url, {"tipo_dominio": "edocere"}).context["cl"].result_count == 1
    assert client.get(url, {"tipo_dominio": "propio"}).context["cl"].result_count == 0


# --- Alta de clientes ------------------------------------------------------


def _datos_cliente(**cambios: str) -> dict[str, Any]:
    datos: dict[str, Any] = {
        "razon_social": "Empresa Nueva",
        "rut": "77777777-7",
        "giro": "Educación",
        "direccion_facturacion": "Av. Siempre Viva 123",
        "correo_admin": "nuevo@empresa.cl",
        "password1": CLAVE_VALIDA,
        "password2": CLAVE_VALIDA,
    }
    datos.update(cambios)
    return datos


def test_alta_de_cliente_crea_su_usuario_de_acceso(client: Client, superadmin: User) -> None:
    client.force_login(superadmin)

    respuesta = _enviar_alta(client, "admin:clientes_cliente_add", _datos_cliente())

    assert respuesta.status_code == 302
    cliente = Cliente.objects.get(razon_social="Empresa Nueva")
    assert cliente.created_at is not None
    assert cliente.email_contacto == "nuevo@empresa.cl"
    usuario = User.objects.get(username="nuevo@empresa.cl")
    assert usuario.groups.filter(name="Cliente").exists()
    perfil = UsuarioPortal.objects.get(usuario=usuario)
    assert perfil.cliente_id == cliente.pk
    assert perfil.rol == "Admin"
    client.logout()
    assert client.login(username="nuevo@empresa.cl", password=CLAVE_VALIDA)


def test_alta_de_cliente_rechaza_contrasena_que_no_cumple_la_politica(
    client: Client, superadmin: User
) -> None:
    client.force_login(superadmin)

    respuesta = _enviar_alta(
        client,
        "admin:clientes_cliente_add",
        _datos_cliente(password1="abc", password2="abc"),
    )

    assert respuesta.status_code == 200
    assert not Cliente.objects.filter(razon_social="Empresa Nueva").exists()
    assert not User.objects.filter(username="nuevo@empresa.cl").exists()


def test_alta_de_cliente_rechaza_correo_ya_usado(client: Client, superadmin: User) -> None:
    User.objects.create_user("nuevo@empresa.cl", password=CLAVE_VALIDA)
    client.force_login(superadmin)

    respuesta = _enviar_alta(client, "admin:clientes_cliente_add", _datos_cliente())

    assert respuesta.status_code == 200
    assert not Cliente.objects.filter(razon_social="Empresa Nueva").exists()


# --- Baja lógica -----------------------------------------------------------


def test_suspender_y_reactivar_cliente_no_toca_a_los_usuarios_staff(
    client: Client, superadmin: User
) -> None:
    cliente = Cliente.objects.create(rut="76543210-3", razon_social="Empresa Suspendible")
    normal = User.objects.create_user("normal@test.cl", password=CLAVE_VALIDA)
    staff = User.objects.create_user("staff@test.cl", password=CLAVE_VALIDA, is_staff=True)
    UsuarioPortal.objects.create(usuario=normal, cliente=cliente, rol="Admin")
    UsuarioPortal.objects.create(usuario=staff, cliente=cliente, rol="Admin")
    client.force_login(superadmin)
    url = reverse("admin:clientes_cliente_changelist")

    client.post(
        url,
        {"action": "suspender_clientes", "_selected_action": [cliente.pk]},
        follow=True,
    )
    normal.refresh_from_db()
    staff.refresh_from_db()
    assert not normal.is_active
    assert staff.is_active

    client.post(
        url,
        {"action": "reactivar_clientes", "_selected_action": [cliente.pk]},
        follow=True,
    )
    normal.refresh_from_db()
    assert normal.is_active


def test_cliente_con_historial_no_se_elimina(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    client.force_login(superadmin)
    url = reverse("admin:clientes_cliente_delete", args=[datos_comerciales.pk])

    client.post(url, {"post": "yes"})

    assert Cliente.objects.filter(pk=datos_comerciales.pk).exists()


# --- Planes negociados (4.7) -----------------------------------------------


def test_plan_personalizado_exige_cliente_precio_y_usuarios(
    client: Client, superadmin: User
) -> None:
    client.force_login(superadmin)

    respuesta = _enviar_alta(
        client,
        "admin:planes_plan_add",
        {"nombre": "Negociado", "tipo_plan": "personalizado"},
    )

    assert respuesta.status_code == 200
    errores = respuesta.context["adminform"].form.errors
    assert {"cliente", "precio_base", "limite_usuarios"} <= set(errores)
    assert not Plan.objects.filter(nombre="Negociado").exists()


def test_plan_general_no_puede_tener_cliente(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    client.force_login(superadmin)

    respuesta = _enviar_alta(
        client,
        "admin:planes_plan_add",
        {"nombre": "Mensual con cliente", "tipo_plan": "mensual", "cliente": datos_comerciales.pk},
    )

    assert respuesta.status_code == 200
    assert "cliente" in respuesta.context["adminform"].form.errors
    assert not Plan.objects.filter(nombre="Mensual con cliente").exists()


def test_plan_personalizado_completo_se_guarda(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    client.force_login(superadmin)

    respuesta = _enviar_alta(
        client,
        "admin:planes_plan_add",
        {
            "nombre": "Negociado PUC",
            "tipo_plan": "personalizado",
            "cliente": datos_comerciales.pk,
            "precio_base": "3000",
            "precio_por_usuario": "0",
            "limite_usuarios": "4000",
        },
    )

    assert respuesta.status_code == 302, respuesta.context["adminform"].form.errors
    plan = Plan.objects.get(nombre="Negociado PUC")
    assert plan.cliente_id == datos_comerciales.pk
    assert plan.limite_usuarios == 4000

    

# --- Alta manual de instancias (4.3) ---------------------------------------


def _datos_instancia(cliente: Cliente, plan: Plan, nombre: str) -> dict[str, Any]:
    return {
        "cliente": cliente.pk,
        "nombre": nombre,
        "dominio": f"https://{nombre}.edocere.com",
        "logo_url": "https://ejemplo.cl/logo.png",
        "version": "4.5",
        "estado": "activa",
        "plan": plan.pk,
    }


def test_alta_de_instancia_con_plan_general_crea_la_suscripcion(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    plan = Plan.objects.get(nombre="Plan Mensual")
    client.force_login(superadmin)

    respuesta = _enviar_alta(
        client,
        "admin:instancias_instanciamoodle_add",
        _datos_instancia(datos_comerciales, plan, "nueva-general"),
    )

    assert respuesta.status_code == 302
    instancia = InstanciaMoodle.objects.get(nombre="nueva-general")
    suscripcion = Suscripcion.objects.get(instancia=instancia)
    assert suscripcion.cliente_id == datos_comerciales.pk
    assert suscripcion.plan_id == plan.pk
    assert suscripcion.estado == "activa"


def test_alta_de_instancia_rechaza_plan_negociado_de_otro_cliente(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    otro = Cliente.objects.create(rut="77777777-7", razon_social="Otro Cliente")
    plan_ajeno = Plan.objects.create(
        nombre="Negociado ajeno",
        tipo_plan="personalizado",
        cliente=otro,
        precio_base=Decimal("100"),
        limite_usuarios=5000,
    )
    client.force_login(superadmin)

    respuesta = _enviar_alta(
        client,
        "admin:instancias_instanciamoodle_add",
        _datos_instancia(datos_comerciales, plan_ajeno, "nueva-ajena"),
    )

    assert respuesta.status_code == 200
    assert "plan" in respuesta.context["adminform"].form.errors
    assert not InstanciaMoodle.objects.filter(nombre="nueva-ajena").exists()


def test_alta_de_instancia_acepta_el_plan_negociado_del_mismo_cliente(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    plan_propio = Plan.objects.create(
        nombre="Negociado propio",
        tipo_plan="personalizado",
        cliente=datos_comerciales,
        precio_base=Decimal("100"),
        limite_usuarios=5000,
    )
    client.force_login(superadmin)

    respuesta = _enviar_alta(
        client,
        "admin:instancias_instanciamoodle_add",
        _datos_instancia(datos_comerciales, plan_propio, "nueva-propia"),
    )

    assert respuesta.status_code == 302
    assert Suscripcion.objects.filter(
        instancia__nombre="nueva-propia", plan=plan_propio
    ).exists()


# --- Suscripciones (4.3) ---------------------------------------------------


def test_suscripcion_rechaza_plan_negociado_de_otro_cliente(
    client: Client, superadmin: User, datos_comerciales: Cliente
    ) -> None:
    otro = Cliente.objects.create(rut="77777777-7", razon_social="Otro Cliente")
    plan_ajeno = Plan.objects.create(
        nombre="Negociado ajeno",
        tipo_plan="personalizado",
        cliente=otro,
        precio_base=Decimal("100"),
        limite_usuarios=5000,
    )
    suscripcion = Suscripcion.objects.get(cliente=datos_comerciales)
    client.force_login(superadmin)
    url = reverse("admin:planes_suscripcion_change", args=[suscripcion.pk])
    datos = {
        **_formularios_de_inlines(client.get(url)),
        "instancia": suscripcion.instancia_id,
        "cliente": datos_comerciales.pk,
        "plan": plan_ajeno.pk,
        "estado": "activa",
        "fecha_inicio_0": "2026-11-02",
        "fecha_inicio_1": "10:00:00",
    }

    respuesta = client.post(url, datos)

    assert respuesta.status_code == 200
    assert "plan" in respuesta.context["adminform"].form.errors
    suscripcion.refresh_from_db()
    assert suscripcion.plan_id != plan_ajeno.pk

# --- Alta de suscripciones desde la ficha del cliente ----------------------


def _formset_de_nuevas_suscripciones(respuesta: Any) -> Any:
    return next(
        i.formset
        for i in respuesta.context["inline_admin_formsets"]
        if "instancia" in i.formset.empty_form.fields
    )


def test_ficha_del_cliente_solo_ofrece_instancias_y_planes_que_le_corresponden(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    otro = Cliente.objects.create(rut="77777777-7", razon_social="Otro Cliente")
    InstanciaMoodle.objects.create(
        cliente=otro, nombre="Ajena", dominio="https://ajena.edocere.com"
    )
    Plan.objects.create(
        nombre="Negociado ajeno",
        tipo_plan="personalizado",
        cliente=otro,
        precio_base=Decimal("100"),
        limite_usuarios=5000,
    )
    Plan.objects.create(
        nombre="Negociado propio",
        tipo_plan="personalizado",
        cliente=datos_comerciales,
        precio_base=Decimal("100"),
        limite_usuarios=5000,
    )
    client.force_login(superadmin)

    respuesta = client.get(
        reverse("admin:clientes_cliente_change", args=[datos_comerciales.pk])
    )

    campos = _formset_de_nuevas_suscripciones(respuesta).empty_form.fields
    instancias = set(campos["instancia"].queryset.values_list("nombre", flat=True))
    planes = set(campos["plan"].queryset.values_list("nombre", flat=True))
    assert instancias == {"Campus"}
    assert {"Plan Mensual", "Negociado propio"} <= planes
    assert "Negociado ajeno" not in planes


def test_ficha_del_cliente_rechaza_plan_negociado_de_otro_cliente(
    client: Client, superadmin: User, datos_comerciales: Cliente
) -> None:
    otro = Cliente.objects.create(rut="77777777-7", razon_social="Otro Cliente")
    plan_ajeno = Plan.objects.create(
        nombre="Negociado ajeno",
        tipo_plan="personalizado",
        cliente=otro,
        precio_base=Decimal("100"),
        limite_usuarios=5000,
    )
    instancia = InstanciaMoodle.objects.get(nombre="Campus")
    antes = Suscripcion.objects.count()
    client.force_login(superadmin)
    url = reverse("admin:clientes_cliente_change", args=[datos_comerciales.pk])
    pagina = client.get(url)
    prefijo = _formset_de_nuevas_suscripciones(pagina).prefix
    datos: dict[str, Any] = {
        **_formularios_de_inlines(pagina),
        "razon_social": "Empresa Backoffice",
        "rut": "76543210-3",
        "giro": "Educación",
        "direccion_facturacion": "Av. Siempre Viva 123",
        "email_contacto": "contacto@empresa.cl",
        f"{prefijo}-TOTAL_FORMS": "1",
        f"{prefijo}-0-cliente": datos_comerciales.pk,
        f"{prefijo}-0-instancia": instancia.pk,
        f"{prefijo}-0-plan": plan_ajeno.pk,
        f"{prefijo}-0-estado": "activa",
        f"{prefijo}-0-fecha_inicio_0": "2026-11-02",
        f"{prefijo}-0-fecha_inicio_1": "10:00:00",
    }

    respuesta = client.post(url, datos)

    assert respuesta.status_code == 200
    assert "plan" in _formset_de_nuevas_suscripciones(respuesta).errors[0]
    assert Suscripcion.objects.count() == antes

def test_no_se_crean_usuarios_sueltos_desde_el_admin(
    client: Client, superadmin: User
) -> None:
    client.force_login(superadmin)
    assert client.get(reverse("admin:auth_user_add")).status_code == 403

def test_listado_de_usuarios_del_portal(
    client: Client, superadmin: User, usuario_cliente: User
) -> None:
    client.force_login(superadmin)
    url = reverse("admin:clientes_usuarioportal_changelist")

    respuesta = client.get(url, {"q": "Cliente Demo"})

    assert respuesta.status_code == 200
    assert respuesta.context["cl"].result_count == 1

# --- Usuarios del portal ---------------------------------------------------


def test_texto_del_usuario_del_portal() -> None:
    assert str(UsuarioPortal(nombre="Ana", email="ana@test.cl")) == "Ana"
    assert str(UsuarioPortal(email="ana@test.cl")) == "ana@test.cl"
    assert str(UsuarioPortal(id=7)) == "Usuario del portal 7"


def test_listado_de_usuarios_del_portal_usa_la_cuenta_si_no_hay_nombre(
    client: Client, superadmin: User, usuario_cliente: User
) -> None:
    cuenta = User.objects.create_user("cuenta-sin-nombre", password=CLAVE_VALIDA)
    UsuarioPortal.objects.create(
        usuario=cuenta,
        cliente=usuario_cliente.usuarioportal.cliente,
        email="otro@test.cl",
        rol="Admin",
    )
    client.force_login(superadmin)

    respuesta = client.get(reverse("admin:clientes_usuarioportal_changelist"))

    assert respuesta.status_code == 200
    assert "cuenta-sin-nombre" in respuesta.content.decode()


def test_ficha_del_usuario_del_portal_tiene_un_titulo_legible(
    client: Client, superadmin: User, usuario_cliente: User
) -> None:
    perfil = usuario_cliente.usuarioportal
    client.force_login(superadmin)

    respuesta = client.get(
        reverse("admin:clientes_usuarioportal_change", args=[perfil.pk])
    )

    assert respuesta.status_code == 200
    assert "UsuarioPortal object" not in respuesta.content.decode()
