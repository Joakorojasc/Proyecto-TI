from typing import Any

from django import forms

from .models import Plan


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
    }

    plan = PlanChoiceField(
        queryset=Plan.objects.all(),
        label="El precio del plan se basa en el número de usuarios activos",
        empty_label=None,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        plan_field = self.fields["plan"]
        assert isinstance(plan_field, forms.ModelChoiceField)
        plan_field.queryset = Plan.objects.filter(cliente__isnull=True).order_by(
            "tipo_plan", "precio_base"
        )
        self.plan_sections = self._build_plan_sections()

    def _build_plan_sections(self) -> list:
        plan_queryset = Plan.objects.filter(cliente__isnull=True).order_by(
            "tipo_plan", "precio_base"
        )
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
