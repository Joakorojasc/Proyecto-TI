"""Configuración compartida de pytest.

pytest carga este archivo automáticamente antes de los tests. Acá van las
fixtures que sirven a todo el proyecto, para no repetirlas en cada app.
"""

import pytest
from django.contrib.auth.models import User

from apps.clientes.models import Cliente, UsuarioPortal


@pytest.fixture
def superadmin(db: None) -> User:
    """Usuario con rol de superadministrador.

    Corresponde a Rafael en el modelo de usuarios: ve todos los clientes e
    instancias y puede impersonar. Lo usamos en los tests de la consola.
    """
    return User.objects.create_superuser(
        username="rafael",
        email="rafael@edocere.cl",
        password="clave-de-prueba",
    )


@pytest.fixture
def usuario_cliente(db: None) -> User:
    """Usuario con rol de cliente.

    Solo debe ver sus propias instancias. Sirve para verificar que el
    aislamiento entre clientes funciona: un cliente nunca ve datos de otro.
    """
    cliente = Cliente.objects.create(
        rut="76.123.456-7",
        razon_social="Cliente Demo",
    )
    usuario = User.objects.create_user(
        username="cliente-demo",
        email="contacto@cliente-demo.cl",
        password="clave-de-prueba",
    )
    UsuarioPortal.objects.create(
        usuario=usuario,
        cliente=cliente,
        nombre=usuario.username,
        rol="Admin",
    )
    return usuario
