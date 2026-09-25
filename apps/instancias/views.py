from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, QuerySet
from django.views.generic import ListView

from apps.clientes.mixins import AislamientoClienteMixin
from apps.planes.models import Suscripcion

from .models import InstanciaMoodle


class ListaInstanciasView(LoginRequiredMixin, AislamientoClienteMixin, ListView):
    model = InstanciaMoodle
    template_name = "instancias/lista.html"
    context_object_name = "instancias"
    login_url = "/login/"

    def get_queryset(self) -> QuerySet[InstanciaMoodle]:
        queryset = super().get_queryset()
        suscripciones_activas = Suscripcion.objects.filter(estado="activa").select_related("plan")
        return queryset.prefetch_related(
            Prefetch(
                "suscripciones",
                queryset=suscripciones_activas,
                to_attr="suscripciones_activas",
            )
        )
