from django.urls import path

from . import views

urlpatterns = [
    path(
        "cliente/<int:cliente_id>/seleccionar-plan/",
        views.seleccionar_plan,
        name="seleccionar_plan",
    ),
]
