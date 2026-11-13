from django.urls import path

from . import views

app_name = "planes"

urlpatterns = [
    path(
        "contacto/",
        views.contacto_plan_personalizado,
        name="contacto_plan_personalizado",
    ),
    path(
        "cliente/<int:cliente_id>/seleccionar-plan/",
        views.seleccionar_plan,
        name="seleccionar_plan",
    ),
]
