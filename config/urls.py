from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView  # Para ver el esqueleto

from apps.clientes.views import registro_usuario

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="base.html"), name="home"),
    # path("test-esqueleto/", TemplateView.as_view(template_name="base.html")), # Para ver el esqueleto
    path("", include("apps.core.urls")),
    path("clientes/", include("apps.clientes.urls")),
    path("instancias/", include("apps.instancias.urls")),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("registro/", registro_usuario, name="registro"),
]
