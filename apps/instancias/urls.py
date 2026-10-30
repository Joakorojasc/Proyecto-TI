from django.urls import path

from .views import (
    DetalleInstanciaView,
    EditarInstanciaView,
    ListaInstanciasView,
    crear_instancia,
    reintentar_aprovisionamiento,
)

app_name = "instancias"

urlpatterns = [
    path(
        "cliente/<int:cliente_id>/plan/<int:plan_id>/crear/",
        crear_instancia,
        name="crear",
    ),
    path("<int:pk>/reintentar-aprovisionamiento/", reintentar_aprovisionamiento, name="reintentar"),
    path("", ListaInstanciasView.as_view(), name="lista"),
    path("<int:pk>/", DetalleInstanciaView.as_view(), name="detalle"),
    path("<int:pk>/editar/", EditarInstanciaView.as_view(), name="editar"),
]
