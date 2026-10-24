from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from . import terminos
from .forms import (
    AceptacionTerminosForm,
    EmpresaRegistroForm,
    PerfilInstitucionForm,
    UsuarioRegistroForm,
)
from .models import Cliente, UsuarioPortal
from .validators import RUT_DUPLICADO


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
    # El alta antigua no creaba usuario y no podía identificar a quien aceptó.
    return redirect("registro")


def registro_usuario(request: HttpRequest) -> HttpResponse:
    user_form: UsuarioRegistroForm
    empresa_form: EmpresaRegistroForm

    if request.method == "POST":
        user_form = UsuarioRegistroForm(request.POST)
        empresa_form = EmpresaRegistroForm(request.POST)

        if user_form.is_valid() and empresa_form.is_valid():
            try:
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
                    terminos.registrar_aceptacion(
                        nuevo_cliente, auth_user, empresa_form.cleaned_data["version_terminos"]
                    )

            except ValidationError as error:
                empresa_form.add_error("version_terminos", error)
            except IntegrityError:
                if not Cliente.objects.filter(rut=empresa_form.cleaned_data["rut"]).exists():
                    raise
                empresa_form.add_error("rut", RUT_DUPLICADO)
            else:
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


@require_safe
def documento_terminos(request: HttpRequest, version: str) -> FileResponse:
    documento = terminos.DOCUMENTOS_TERMINOS.get(version)
    if documento is None:
        raise Http404("El documento solicitado no está disponible.")
    respuesta = FileResponse(
        documento.open("rb"), content_type="application/pdf", filename="T&C Moodle.pdf"
    )
    respuesta["Cache-Control"] = "public, max-age=31536000, immutable"
    return respuesta


@login_required
@require_http_methods(["GET", "POST"])
def aceptar_terminos(request: HttpRequest) -> HttpResponse:
    perfil = get_object_or_404(
        UsuarioPortal.objects.select_related("cliente"), usuario=request.user
    )
    if perfil.cliente is None:
        raise Http404("El usuario no tiene una institución asociada.")
    cliente = perfil.cliente
    form = AceptacionTerminosForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                terminos.registrar_aceptacion(
                    cliente, request.user, form.cleaned_data["version_terminos"]
                )
        except ValidationError as error:
            form.add_error("version_terminos", error)
        else:
            messages.success(request, "La aceptación de términos y condiciones quedó registrada.")
            return redirect("aceptar_terminos")
    return render(
        request,
        "clientes/terminos.html",
        {
            "cliente": cliente,
            "form": form,
            "aceptacion": cliente.aceptaciones_terminos.filter(
                version_documento=terminos.VERSION_TERMINOS
            ).first(),
            "version_terminos": terminos.VERSION_TERMINOS,
        },
    )
