from django.contrib import admin

from .models import DocumentoTributario, MedioPago, Pago

admin.site.register([MedioPago, Pago, DocumentoTributario])
