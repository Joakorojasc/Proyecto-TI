from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.clientes.models import Cliente

from .forms import SeleccionarPlanForm
from .models import Plan, Suscripcion


def seleccionar_plan(request: HttpRequest, cliente_id: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == "POST" and "personalized_plan" in request.POST:
        Plan.objects.get_or_create(
            cliente=cliente,
            tipo_plan="personalizado",
            defaults={
                "nombre": "Plan personalizado",
                "precio_base": None,
                "precio_por_usuario": None,
                "limite_usuarios": None,
            },
        )
        return redirect("home")

    form = SeleccionarPlanForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        plan_seleccionado = form.cleaned_data["plan"]

        with transaction.atomic():
            Suscripcion.objects.create(
                cliente=cliente,
                plan=plan_seleccionado,
                estado="activo",
                fecha_inicio=timezone.now(),
            )

        return redirect("home")

    return render(
        request,
        "seleccionar_plan.html",
        {
            "cliente": cliente,
            "form": form,
        },
    )
