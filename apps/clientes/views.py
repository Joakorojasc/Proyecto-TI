from django.http import HttpResponse
from django.shortcuts import redirect, render

from .forms import RegistroClienteForm


def registro_cliente(request)-> HttpResponse:
    if request.method == "POST":
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/")
    else:
        form = RegistroClienteForm()

    return render(request, "clientes/registro.html", {"form": form})
