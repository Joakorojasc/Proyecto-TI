from django.contrib import admin

from .models import Cliente, UsuarioPortal

admin.site.register([Cliente, UsuarioPortal])
