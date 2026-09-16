from django.contrib import admin

from .models import DocumentoTributario, Pago

admin.site.register([Pago, DocumentoTributario])
