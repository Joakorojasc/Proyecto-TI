from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.clientes.permisos import obtener_cliente_autorizado
from apps.pagos.views import pagos_del_cliente

from .forms import ContactoPlanPersonalizadoForm, SeleccionarPlanForm
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
            "pagos": pagos_del_cliente(request),
        },
    )


@login_required(login_url="/login/")
def contacto_plan_personalizado(request: HttpRequest) -> HttpResponse:
    form = ContactoPlanPersonalizadoForm(
        request.POST or None,
        initial={"correo": request.user.email},
    )
    enviado = request.method == "POST" and form.is_valid()
    return render(
        request,
        "contacto_plan_personalizado.html",
        {"form": form, "enviado": enviado},
    )


@login_required(login_url="/login/")
def seleccionar_plan(request: HttpRequest, cliente_id: int) -> HttpResponse:
    cliente = obtener_cliente_autorizado(request, cliente_id)
    form = SeleccionarPlanForm(request.POST or None, cliente_id=cliente.id)

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
