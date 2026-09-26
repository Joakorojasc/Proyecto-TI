from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.test import TestCase

from apps.clientes.mixins import AislamientoClienteMixin
from apps.clientes.models import Cliente, UsuarioPortal
from apps.instancias.models import InstanciaMoodle


class VistaBaseInstancias:
    def get_queryset(self) -> QuerySet[InstanciaMoodle]:
        return InstanciaMoodle.objects.all()


class VistaInstancias(AislamientoClienteMixin, VistaBaseInstancias):
    def __init__(self, user: User) -> None:
        self.request = type("Request", (), {"user": user})()


class AislamientoClienteMixinTests(TestCase):
    def setUp(self) -> None:
        self.cliente_uno = Cliente.objects.create(razon_social="Cliente Uno")
        self.cliente_dos = Cliente.objects.create(razon_social="Cliente Dos")
        self.instancia_uno = InstanciaMoodle.objects.create(
            cliente=self.cliente_uno,
            dominio="uno.example.com",
        )
        self.instancia_dos = InstanciaMoodle.objects.create(
            cliente=self.cliente_dos,
            dominio="dos.example.com",
        )

    def test_usuario_sin_usuario_portal_no_obtiene_datos(self) -> None:
        usuario = User.objects.create_user(username="sin-perfil")

        resultado = VistaInstancias(usuario).get_queryset()

        self.assertQuerySetEqual(resultado, [])

    def test_usuario_portal_sin_cliente_no_obtiene_datos(self) -> None:
        usuario = User.objects.create_user(username="sin-cliente")
        UsuarioPortal.objects.create(usuario=usuario)

        resultado = VistaInstancias(usuario).get_queryset()

        self.assertQuerySetEqual(resultado, [])

    def test_usuario_solo_obtiene_instancias_de_su_cliente(self) -> None:
        usuario = User.objects.create_user(username="cliente-uno")
        UsuarioPortal.objects.create(usuario=usuario, cliente=self.cliente_uno)

        resultado = VistaInstancias(usuario).get_queryset()

        self.assertQuerySetEqual(resultado, [self.instancia_uno])
