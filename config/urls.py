from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

from apps.clientes.forms import LoginForm
from apps.clientes.views import registro_usuario
from apps.core.views import health, home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("health/", health, name="health"),
    path("core/", include(("apps.core.urls", "core"), namespace="core")),
    path("", include("apps.core.urls")),
    path("clientes/", include("apps.clientes.urls")),
    path("instancias/", include("apps.instancias.urls")),
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
        login_required(
            TemplateView.as_view(template_name="suscripciones.html"),
            login_url="/login/",
        ),
        name="seccion_suscripciones",
    ),
    path(
        "facturacion/",
        login_required(
            TemplateView.as_view(template_name="facturacion.html"),
            login_url="/login/",
        ),
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
        login_required(
            TemplateView.as_view(template_name="perfil.html"),
            login_url="/login/",
        ),
        name="seccion_perfil",
    ),
]
