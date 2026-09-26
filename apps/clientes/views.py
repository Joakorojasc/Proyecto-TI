from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import EmpresaRegistroForm, RegistroClienteForm
from .models import UsuarioPortal


def registro_cliente(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/")
    else:
        form = RegistroClienteForm()
    return render(request, "clientes/registro.html", {"form": form})


def registro_usuario(request: HttpRequest) -> HttpResponse:
    user_form: UserCreationForm = UserCreationForm()
    empresa_form: EmpresaRegistroForm = EmpresaRegistroForm()

    if request.method == "POST":
        user_form = UserCreationForm(request.POST)
        empresa_form = EmpresaRegistroForm(request.POST)

        if user_form.is_valid() and empresa_form.is_valid():
            auth_user = user_form.save()
            grupo_cliente, created = Group.objects.get_or_create(name="Cliente")
            auth_user.groups.add(grupo_cliente)

            nuevo_cliente = empresa_form.save()

            UsuarioPortal.objects.create(
                cliente=nuevo_cliente, nombre=auth_user.username, rol="Admin"
            )
            with transaction.atomic():
                auth_user = user_form.save()
                nuevo_cliente = empresa_form.save()
                UsuarioPortal.objects.create(
                    usuario=auth_user,
                    cliente=nuevo_cliente,
                    nombre=auth_user.username,
                    rol="Admin",
                )
            return redirect("login")

    return render(request, "registro.html", {"user_form": user_form, "empresa_form": empresa_form})
