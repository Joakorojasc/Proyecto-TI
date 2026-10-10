from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    EmpresaRegistroForm,
    PerfilInstitucionForm,
    RegistroClienteForm,
    UsuarioRegistroForm,
)
from .models import UsuarioPortal


def perfil_institucion(request: HttpRequest) -> HttpResponse:
    usuario_portal = get_object_or_404(
        UsuarioPortal.objects.select_related("cliente"),
        usuario_id=request.user.pk,
    )
    if usuario_portal.cliente is None:
        raise Http404("El usuario no tiene una institución asociada.")

    cliente = usuario_portal.cliente
    form = PerfilInstitucionForm(request.POST or None, instance=cliente)

    if request.method == "POST" and form.is_valid():
        if not request.user.check_password(form.cleaned_data["confirmacion_contrasena"]):
            form.add_error(
                "confirmacion_contrasena",
                "La contraseña ingresada no es correcta.",
            )
        else:
            form.save()
            messages.success(request, "Los cambios del perfil se guardaron correctamente.")
            return redirect("seccion_perfil")

    return render(
        request,
        "perfil.html",
        {
            "form": form,
            "cliente": cliente,
        },
    )


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
