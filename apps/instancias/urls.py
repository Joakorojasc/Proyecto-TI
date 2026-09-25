from django.urls import path

from .views import ListaInstanciasView

app_name = "instancias"

urlpatterns = [
    path("", ListaInstanciasView.as_view(), name="lista"),
]
