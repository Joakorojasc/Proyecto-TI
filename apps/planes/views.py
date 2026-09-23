from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.clientes.models import Cliente

from .forms import SeleccionarPlanForm
from .models import Suscripcion


def seleccionar_plan(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    form = SeleccionarPlanForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        plan = form.cleaned_data["plan"]

        Suscripcion.objects.create(
            cliente=cliente,
            plan=plan,
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
    