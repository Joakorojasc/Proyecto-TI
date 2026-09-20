from django.contrib import admin
from django.urls import include, path
# from django.views.generic import TemplateView  # Para ver el esqueleto

urlpatterns = [
    path("admin/", admin.site.urls),
    # path("test-esqueleto/", TemplateView.as_view(template_name="base.html")), # Para ver el esqueleto
    path("", include("apps.core.urls")),
]
