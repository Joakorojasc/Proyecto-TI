from typing import Any

from django import forms
from django.db.models import Q

from .models import Plan


class ContactoPlanPersonalizadoForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=150)
    correo = forms.EmailField(label="Correo electrónico")
    mensaje = forms.CharField(
        label="Cuéntanos qué necesitas",
        widget=forms.Textarea,
        min_length=10,
    )


class PlanChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: Plan) -> str:
        return obj.display_label()


class SeleccionarPlanForm(forms.Form):
    PLAN_BLOCKS = {
        "Mensual": {
            "title": "Planes mensuales",
            "description": "Ideal para equipos que requieren pagar mes a mes.",
        },
        "Anual": {
            "title": "Planes anuales",
            "description": "Ahorra con pagos anuales con precios al por mayor.",
        },
        "Personalizado": {
            "title": "Plan personalizado asignado",
            "description": "Planes especiales previamente autorizados para tu institución.",
        },
    }

    plan = PlanChoiceField(
        queryset=Plan.objects.all(),
        label="El precio del plan se basa en el número de usuarios activos",
        empty_label=None,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        cliente_id = kwargs.pop("cliente_id", None)
        super().__init__(*args, **kwargs)
        plan_field = self.fields["plan"]
        assert isinstance(plan_field, forms.ModelChoiceField)
        planes = Plan.objects.filter(cliente__isnull=True)
        if cliente_id is not None:
            planes = Plan.objects.filter(Q(cliente__isnull=True) | Q(cliente_id=cliente_id))
        planes = planes.order_by("tipo_plan", "precio_base")
        plan_field.queryset = planes
        self.plan_sections = self._build_plan_sections(planes)

    def _build_plan_sections(self, plan_queryset: Any) -> list:
        sections = []

        for tipo_plan, config in self.PLAN_BLOCKS.items():
            plans = list(plan_queryset.filter(tipo_plan__iexact=tipo_plan))
            sections.append(
                {
                    "key": tipo_plan,
                    "title": config["title"],
                    "description": config["description"],
                    "plans": plans,
                }
            )

        return sections
