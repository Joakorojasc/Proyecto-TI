from django.test import TestCase
from django.urls import reverse

from apps.clientes.forms import RegistroClienteForm
from apps.clientes.models import Cliente


class RegistroClienteTests(TestCase):
    def test_pagina_registro_carga_bien(self)-> None:
        """Prueba que al entrar a la URL por GET, la página cargue correctamente (código 200)"""
        url = reverse("registro_cliente")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "clientes/registro.html")

    def test_formulario_acepta_datos_correctos(self)-> None:
        """Prueba que el formulario entienda cuando le pasamos datos válidos"""
        datos = {
            "rut": "76.123.456-7",
            "razon_social": "Empresa Prueba",
            "giro": "Educación",
            "direccion_facturacion": "Avenida Siempre Viva 123",
            "email_contacto": "contacto@prueba.com",
        }
        form = RegistroClienteForm(data=datos)
        self.assertTrue(form.is_valid())

    def test_registro_guarda_en_base_de_datos(self)-> None:
        """Prueba que al enviar los datos por POST, se cree el Cliente en la BD"""
        url = reverse("registro_cliente")
        datos = {
            "rut": "76.123.456-7",
            "razon_social": "Empresa Prueba",
            "giro": "Educación",
            "direccion_facturacion": "Avenida Siempre Viva 123",
            "email_contacto": "contacto@prueba.com",
        }
        response = self.client.post(url, data=datos)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(Cliente.objects.first().rut, "76.123.456-7")
