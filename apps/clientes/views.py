from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

from .forms import EmpresaRegistroForm
from .models import UsuarioPortal


def registro_cliente(request):
    if request.method == 'POST':
        user_form = UserCreationForm(request.POST)
        empresa_form = EmpresaRegistroForm(request.POST)
        
        if user_form.is_valid() and empresa_form.is_valid():
            # 1. Crea credenciales
            auth_user = user_form.save()
            
            # 2. Crea la institución (Cliente)
            nuevo_cliente = empresa_form.save()
            
            # 3. Los vincula en UsuarioPortal
            UsuarioPortal.objects.create(
                cliente=nuevo_cliente,
                nombre=auth_user.username,
                rol='Admin'
            )
            
            return redirect('login')
    else:
        user_form = UserCreationForm()
        empresa_form = EmpresaRegistroForm()
        
    return render(request, 'registro.html', {
        'user_form': user_form, 
        'empresa_form': empresa_form
    })