from django import forms

from .models import Plan


class SeleccionarPlanForm(forms.Form):
    plan = forms.ModelChoiceField(
        queryset=Plan.objects.all(),
        label="Selecciona un plan",
        empty_label=None,
        widget=forms.RadioSelect,
    )

    def label_from_instance(self, obj: Plan) -> str:
        precio = obj.precio_base if obj.precio_base is not None else 0
        return f"{obj.nombre} · {obj.tipo_plan} · ${precio:,.0f}"
