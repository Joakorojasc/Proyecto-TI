from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, QuerySet
from django.views.generic import DetailView, ListView

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


class DetalleInstanciaView(LoginRequiredMixin, AislamientoClienteMixin, DetailView):
    model = InstanciaMoodle
    template_name = "instancias/detalle.html"
    context_object_name = "instancia"
    login_url = "/login/"

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        instancia = self.object
        mediciones = instancia.medicionusomensual_set.order_by("-anio", "-mes")
        context["mediciones"] = mediciones
        context["ultima_medicion"] = mediciones.first()
        return context
