from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

from apps.clientes.forms import LoginForm
from apps.clientes.views import perfil_institucion, registro_usuario
from apps.core.views import health, home
from apps.pagos.views import facturacion
from apps.planes.views import planes_disponibles

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("health/", health, name="health"),
    path("core/", include(("apps.core.urls", "core"), namespace="core")),
    path("clientes/", include("apps.clientes.urls")),
    path("instancias/", include("apps.instancias.urls")),
    path("pagos/", include("apps.pagos.urls")),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="login.html", authentication_form=LoginForm),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("registro/", registro_usuario, name="registro"),
    path("planes/", include("apps.planes.urls")),
    path(
        "suscripciones/",
        planes_disponibles,
        name="seccion_suscripciones",
    ),
    path(
        "facturacion/",
        facturacion,
        name="seccion_facturacion",
    ),
    path(
        "estadisticas/",
        login_required(
            TemplateView.as_view(template_name="estadisticas.html"),
            login_url="/login/",
        ),
        name="seccion_estadisticas",
    ),
    path(
        "perfil/",
        perfil_institucion,
        name="seccion_perfil",
    ),
]
