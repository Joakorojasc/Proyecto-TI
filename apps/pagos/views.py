from decimal import Decimal
from secrets import token_urlsafe

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.clientes.mixins import get_cliente_autorizado
from apps.instancias.forms import CrearInstanciaForm
from apps.planes.models import Suscripcion

from .forms import CheckoutSimuladoForm
from .models import DocumentoTributario, MedioPago, Pago


def pagos_del_cliente(request: HttpRequest, cliente_id: int | None = None) -> QuerySet[Pago]:
    usuario_portal = getattr(request.user, "usuarioportal", None)
    if cliente_id is None and usuario_portal is not None:
        cliente_id = usuario_portal.cliente_id
    if cliente_id is None:
        return Pago.objects.none()
    return (
        Pago.objects.filter(suscripcion__cliente_id=cliente_id)
        .select_related("suscripcion__plan", "suscripcion__instancia")
        .prefetch_related("documentotributario")
        .order_by("-fecha_pago", "-id")
    )


@login_required(login_url="/login/")
def facturacion(request: HttpRequest) -> HttpResponse:
    cliente_id = request.GET.get("cliente_id")
    cliente = None
    if cliente_id and (request.user.is_staff or request.user.is_superuser):
        cliente = get_cliente_autorizado(request, int(cliente_id))
    return render(
        request,
        "facturacion.html",
        {"pagos": pagos_del_cliente(request, cliente.id if cliente else None)},
    )


@login_required(login_url="/login/")
def checkout_suscripcion(request: HttpRequest, suscripcion_id: int) -> HttpResponse:
    suscripcion = get_object_or_404(
        Suscripcion.objects.select_related("cliente", "plan"),
        id=suscripcion_id,
    )
    cliente = get_cliente_autorizado(request, suscripcion.cliente_id)
    form = CheckoutSimuladoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        resultado = request.POST.get("resultado")
        if resultado not in {"aprobado", "rechazado"}:
            form.add_error(None, "Selecciona un resultado de simulación válido.")
        else:
            with transaction.atomic():
                medio_pago, _ = MedioPago.objects.update_or_create(
                    cliente=cliente,
                    token_simulado=(form.cleaned_data["token_simulado"] or token_urlsafe(24)),
                    defaults={
                        "ultimos_4_digitos": form.cleaned_data["ultimos_4_digitos"],
                        "marca_tarjeta": form.cleaned_data["marca_tarjeta"],
                        "activo": True,
                    },
                )
                del medio_pago
                pago = Pago.objects.create(
                    suscripcion=suscripcion,
                    monto=Decimal("0.00"),
                    fecha_pago=timezone.now(),
                    estado=(
                        Pago.ESTADO_APROBADO if resultado == "aprobado" else Pago.ESTADO_RECHAZADO
                    ),
                )
                if resultado == "aprobado":
                    datos_instancia = request.session.get(f"checkout_instancia_{suscripcion.pk}")
                    if datos_instancia is not None:
                        instancia_form = CrearInstanciaForm(data=datos_instancia)
                        if not instancia_form.is_valid():
                            form.add_error(
                                None,
                                "Los datos de la instancia ya no son válidos. "
                                "Vuelve a iniciar la contratación.",
                            )
                            return render(
                                request,
                                "pagos/checkout.html",
                                {
                                    "cliente": cliente,
                                    "suscripcion": suscripcion,
                                    "form": form,
                                },
                            )
                        instancia = instancia_form.save(commit=False)
                        instancia.cliente = cliente
                        instancia.estado = "activa"
                        instancia.save()
                        suscripcion.instancia = instancia
                    DocumentoTributario.objects.create(
                        pago=pago,
                        tipo_documento="comprobante simulado",
                        folio=pago.id,
                    )
                    suscripcion.estado = "activa"
                    suscripcion.fecha_inicio = timezone.now()
                    update_fields = ["estado", "fecha_inicio"]
                    if datos_instancia is not None:
                        update_fields.append("instancia")
                        del request.session[f"checkout_instancia_{suscripcion.pk}"]
                    suscripcion.save(update_fields=update_fields)
                    messages.success(request, "Pago aprobado y comprobante generado.")
                else:
                    suscripcion.estado = "pendiente"
                    suscripcion.save(update_fields=["estado"])
                    messages.error(
                        request,
                        "Pago rechazado: el medio de pago no fue aprobado. Puedes reintentar.",
                    )
            if resultado == "aprobado":
                return redirect("instancias:lista")
            return redirect("pagos:checkout", suscripcion_id=suscripcion.pk)

    return render(
        request,
        "pagos/checkout.html",
        {
            "cliente": cliente,
            "suscripcion": suscripcion,
            "form": form,
        },
    )
