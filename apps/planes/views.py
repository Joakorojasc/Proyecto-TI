from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.clientes.models import Cliente

from .forms import SeleccionarPlanForm
from .models import Plan


@login_required(login_url="/login/")
def planes_disponibles(request: HttpRequest) -> HttpResponse:
    planes_base = Plan.objects.filter(cliente__isnull=True)
    return render(
        request,
        "suscripciones.html",
        {
            "planes_mensuales": planes_base.filter(tipo_plan__iexact="mensual").order_by(
                "precio_base", "nombre"
            ),
            "planes_anuales": planes_base.filter(tipo_plan__iexact="anual").order_by(
                "precio_base", "nombre"
            ),
        },
    )


def seleccionar_plan(request: HttpRequest, cliente_id: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == "POST" and "personalized_plan" in request.POST:
        plan, _ = Plan.objects.get_or_create(
            cliente=cliente,
            tipo_plan="personalizado",
            defaults={
                "nombre": "Plan personalizado",
                "precio_base": None,
                "precio_por_usuario": None,
                "limite_usuarios": None,
            },
        )
        return redirect(
            "instancias:crear",
            cliente_id=cliente.id,
            plan_id=plan.id,
        )

    form = SeleccionarPlanForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        plan_seleccionado = form.cleaned_data["plan"]
        return redirect(
            "instancias:crear",
            cliente_id=cliente.id,
            plan_id=plan_seleccionado.id,
        )

    return render(
        request,
        "seleccionar_plan.html",
        {
            "cliente": cliente,
            "form": form,
        },
    )
