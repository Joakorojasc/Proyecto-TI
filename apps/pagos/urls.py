from django.urls import path

from . import views

app_name = "pagos"

urlpatterns = [
    path(
        "suscripcion/<int:suscripcion_id>/checkout/",
        views.checkout_suscripcion,
        name="checkout",
    ),
]
