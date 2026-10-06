from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import EmpresaRegistroForm, RegistroClienteForm, UsuarioRegistroForm
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
    user_form: UsuarioRegistroForm
    empresa_form: EmpresaRegistroForm

    if request.method == "POST":
        user_form = UsuarioRegistroForm(request.POST)
        empresa_form = EmpresaRegistroForm(request.POST)

        if user_form.is_valid() and empresa_form.is_valid():
            with transaction.atomic():
                auth_user = user_form.save()
                nuevo_cliente = empresa_form.save(commit=False)
                nuevo_cliente.email_contacto = auth_user.email
                nuevo_cliente.save()

                grupo_cliente, _ = Group.objects.get_or_create(name="Cliente")
                auth_user.groups.add(grupo_cliente)

                UsuarioPortal.objects.create(
                    usuario=auth_user,
                    cliente=nuevo_cliente,
                    nombre=auth_user.username,
                    email=auth_user.email,
                    rol="Admin",
                )

            login(request, auth_user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("instancias:lista")
    else:
        user_form = UsuarioRegistroForm()
        empresa_form = EmpresaRegistroForm()

    return render(
        request,
        "registro.html",
        {
            "user_form": user_form,
            "empresa_form": empresa_form,
        },
    )
