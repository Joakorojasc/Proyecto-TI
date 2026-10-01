from django.urls import path

from .views import DetalleInstanciaView, ListaInstanciasView

app_name = "instancias"

urlpatterns = [
    path("", ListaInstanciasView.as_view(), name="lista"),
    path("<int:pk>/", DetalleInstanciaView.as_view(), name="detalle"),
]
