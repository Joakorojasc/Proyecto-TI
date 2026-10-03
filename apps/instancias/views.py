from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from apps.clientes.mixins import AislamientoClienteMixin
from apps.clientes.models import Cliente
from apps.planes.models import Plan, Suscripcion

from .forms import CrearInstanciaForm
from .models import InstanciaMoodle


def crear_instancia(request: HttpRequest, cliente_id: int, plan_id: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, id=cliente_id)
    plan = get_object_or_404(
        Plan.objects.filter(Q(cliente__isnull=True) | Q(cliente=cliente)),
        id=plan_id,
    )
    form = CrearInstanciaForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            instancia = form.save(commit=False)
            instancia.cliente = cliente
            instancia.estado = "activa"
            instancia.save()
            Suscripcion.objects.create(
                cliente=cliente,
                instancia=instancia,
                plan=plan,
                estado="activa",
                fecha_inicio=timezone.now(),
            )

        return redirect("home")

    return render(
        request,
        "instancias/crear.html",
        {
            "cliente": cliente,
            "plan": plan,
            "form": form,
        },
    )


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
