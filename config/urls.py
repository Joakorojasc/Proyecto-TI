from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.clientes.views import registro_usuario
from apps.core.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("", include("apps.core.urls")),
    path("clientes/", include("apps.clientes.urls")),
    path("instancias/", include("apps.instancias.urls")),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("registro/", registro_usuario, name="registro"),
]
