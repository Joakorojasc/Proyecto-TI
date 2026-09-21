from django.contrib.auth.forms import UserCreationForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import EmpresaRegistroForm
from .models import UsuarioPortal


def registro_cliente(request: HttpRequest) -> HttpResponse:
    user_form: UserCreationForm = UserCreationForm()
    empresa_form: EmpresaRegistroForm = EmpresaRegistroForm()

    if request.method == "POST":
        user_form = UserCreationForm(request.POST)
        empresa_form = EmpresaRegistroForm(request.POST)

        if user_form.is_valid() and empresa_form.is_valid():
            auth_user = user_form.save()
            nuevo_cliente = empresa_form.save()

            UsuarioPortal.objects.create(
                cliente=nuevo_cliente, nombre=auth_user.username, rol="Admin"
            )
            return redirect("login")

    return render(request, "registro.html", {"user_form": user_form, "empresa_form": empresa_form})
