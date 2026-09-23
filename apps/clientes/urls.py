from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("registro/", views.registro_cliente, name="registro_cliente"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="clientes/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]