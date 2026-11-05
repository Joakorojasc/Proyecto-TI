import hashlib
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.http import FileResponse
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes import terminos
from apps.clientes.forms import AceptacionTerminosForm
from apps.clientes.models import AceptacionTerminos, Cliente, UsuarioPortal


class TerminosTests(TestCase):
    def setUp(self) -> None:
        self.datos = {
            "username": "admin@institucion.cl",
            "password1": "ClaveSegura123!",
            "password2": "ClaveSegura123!",
            "razon_social": "Institución de prueba",
            "rut": "76.123.456-0",
            "acepta_terminos": "on",
            "version_terminos": terminos.VERSION_TERMINOS,
        }

    def preparar_cliente(self) -> tuple[User, Cliente]:
        usuario = User.objects.create_user(
            username="existente@institucion.cl", password="ClaveSegura123!"
        )
        cliente = Cliente.objects.create(rut="6-K", razon_social="Institución existente")
        UsuarioPortal.objects.create(usuario=usuario, cliente=cliente)
        return usuario, cliente

    def comprobar_sin_altas(self) -> None:
        self.assertFalse(User.objects.exists())
        self.assertFalse(Cliente.objects.exists())
        self.assertFalse(UsuarioPortal.objects.exists())
        self.assertFalse(AceptacionTerminos.objects.exists())

    def test_documento_publico_es_el_pdf_oficial_completo(self) -> None:
        respuesta = self.client.get(
            reverse("documento_terminos", kwargs={"version": terminos.VERSION_TERMINOS})
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        assert isinstance(respuesta, FileResponse)
        contenido = b"".join(respuesta.streaming_content)
        self.assertEqual(len(contenido), 15034)
        self.assertEqual(hashlib.sha256(contenido).hexdigest(), terminos.SHA256_DOCUMENTO)
        self.assertIn("inline", respuesta["Content-Disposition"])

    def test_documento_desconocido_devuelve_404(self) -> None:
        self.assertEqual(
            self.client.get(
                reverse("documento_terminos", kwargs={"version": "inexistente"})
            ).status_code,
            404,
        )

    def test_documento_no_acepta_post(self) -> None:
        self.assertEqual(
            self.client.post(
                reverse("documento_terminos", kwargs={"version": terminos.VERSION_TERMINOS})
            ).status_code,
            405,
        )

    def test_casilla_desmarcada_y_documento_disponible_en_registro(self) -> None:
        respuesta = self.client.get(reverse("registro"))
        form = respuesta.context["empresa_form"]
        self.assertFalse(form["acepta_terminos"].value())
        self.assertEqual(form["version_terminos"].value(), terminos.VERSION_TERMINOS)
        self.assertContains(
            respuesta, reverse("documento_terminos", kwargs={"version": terminos.VERSION_TERMINOS})
        )
        self.assertNotIn("checked", str(form["acepta_terminos"]))
        self.assertFalse(AceptacionTerminos.objects.exists())

    def test_registro_guarda_institucion_usuario_fecha_y_version(self) -> None:
        antes = timezone.now()
        respuesta = self.client.post(reverse("registro"), self.datos)
        self.assertRedirects(respuesta, reverse("instancias:lista"))
        aceptacion = AceptacionTerminos.objects.get()
        self.assertEqual(aceptacion.cliente, Cliente.objects.get())
        self.assertEqual(aceptacion.usuario, User.objects.get())
        self.assertEqual(aceptacion.version_documento, terminos.VERSION_TERMINOS)
        self.assertTrue(timezone.is_aware(aceptacion.fecha_aceptacion))
        self.assertGreaterEqual(aceptacion.fecha_aceptacion, antes)
        self.assertLessEqual(aceptacion.fecha_aceptacion, timezone.now())
        self.assertEqual(aceptacion.cliente.rut, "76123456-0")
        self.assertTrue(terminos.tiene_aceptacion_vigente(aceptacion.cliente))

    def test_sin_casilla_o_con_false_se_rechaza_sin_altas_parciales(self) -> None:
        for valor in (None, "", "false", "0", "no", "off"):
            with self.subTest(valor=valor):
                datos = dict(self.datos)
                if valor is None:
                    datos.pop("acepta_terminos")
                else:
                    datos["acepta_terminos"] = valor
                respuesta = self.client.post(reverse("registro"), datos)
                self.assertContains(
                    respuesta, "Debes aceptar los términos y condiciones para continuar."
                )
                self.comprobar_sin_altas()

    def test_version_ausente_o_desactualizada_rechaza_registro(self) -> None:
        for version in ("", "sha256-anterior"):
            with self.subTest(version=version):
                respuesta = self.client.post(
                    reverse("registro"), {**self.datos, "version_terminos": version}
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn("version_terminos", respuesta.context["empresa_form"].errors)
                self.comprobar_sin_altas()

    def test_fallo_al_guardar_aceptacion_revierte_toda_la_cuenta(self) -> None:
        with (
            patch(
                "apps.clientes.terminos.AceptacionTerminos.objects.get_or_create",
                side_effect=IntegrityError("fallo de prueba"),
            ),
            self.assertRaises(IntegrityError),
        ):
            self.client.post(reverse("registro"), self.datos)
        self.comprobar_sin_altas()

    def test_fallo_al_crear_perfil_no_deja_usuario_o_empresa(self) -> None:
        with (
            patch(
                "apps.clientes.views.UsuarioPortal.objects.create",
                side_effect=RuntimeError("fallo de prueba"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.client.post(reverse("registro"), self.datos)
        self.comprobar_sin_altas()

    def test_cambio_de_version_entre_validacion_y_guardado_revierte_alta(self) -> None:
        with patch(
            "apps.clientes.views.terminos.registrar_aceptacion",
            side_effect=ValidationError("El documento vigente cambió."),
        ):
            respuesta = self.client.post(reverse("registro"), self.datos)
        self.assertContains(respuesta, "El documento vigente cambió.")
        self.comprobar_sin_altas()

    def test_alta_antigua_redirige_y_no_crea_cliente_sin_responsable(self) -> None:
        for metodo in (self.client.get, self.client.post):
            respuesta = metodo(reverse("registro_cliente"), self.datos)
            self.assertRedirects(respuesta, reverse("registro"))
        self.comprobar_sin_altas()

    def test_cliente_existente_no_acepta_automaticamente(self) -> None:
        usuario, cliente = self.preparar_cliente()
        self.assertFalse(terminos.tiene_aceptacion_vigente(cliente))
        self.assertFalse(terminos.tiene_aceptacion_vigente(Cliente()))
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("aceptar_terminos"))
        self.assertContains(respuesta, "aún no tiene una aceptación registrada")
        self.assertFalse(respuesta.context["form"]["acepta_terminos"].value())
        self.assertFalse(AceptacionTerminos.objects.exists())
        self.assertContains(self.client.get(reverse("seccion_perfil")), reverse("aceptar_terminos"))

    def test_cliente_existente_puede_aceptar_y_repetir_sin_reemplazar_evidencia(self) -> None:
        usuario, cliente = self.preparar_cliente()
        self.client.force_login(usuario)
        datos = {"acepta_terminos": "on", "version_terminos": terminos.VERSION_TERMINOS}
        respuesta = self.client.post(reverse("aceptar_terminos"), datos)
        self.assertRedirects(respuesta, reverse("aceptar_terminos"))
        primero = AceptacionTerminos.objects.values().get()
        self.client.post(reverse("aceptar_terminos"), datos)
        self.assertEqual(AceptacionTerminos.objects.values().get(), primero)
        self.assertTrue(terminos.tiene_aceptacion_vigente(cliente))
        self.assertContains(
            self.client.get(reverse("aceptar_terminos")), "aceptó el documento vigente"
        )

    def test_aceptacion_existente_requiere_casilla_y_version_vigente(self) -> None:
        usuario, cliente = self.preparar_cliente()
        self.client.force_login(usuario)
        respuesta = self.client.post(reverse("aceptar_terminos"), {})
        self.assertContains(respuesta, "Debes aceptar los términos y condiciones")
        respuesta = self.client.post(
            reverse("aceptar_terminos"), {"acepta_terminos": "on", "version_terminos": "anterior"}
        )
        self.assertContains(respuesta, "El documento vigente cambió")
        self.assertNotContains(respuesta, "Campo oculto")
        self.assertFalse(terminos.tiene_aceptacion_vigente(cliente))

    def test_cambio_version_invalida_vigencia_sin_borrar_evidencia(self) -> None:
        usuario, cliente = self.preparar_cliente()
        terminos.registrar_aceptacion(cliente, usuario, terminos.VERSION_TERMINOS)
        with patch.object(terminos, "VERSION_TERMINOS", "sha256-nuevo"):
            self.assertFalse(terminos.tiene_aceptacion_vigente(cliente))
            form = AceptacionTerminosForm(
                data={"acepta_terminos": "on", "version_terminos": self.datos["version_terminos"]}
            )
            self.assertFalse(form.is_valid())
            self.assertIn("version_terminos", form.errors)
        self.assertEqual(AceptacionTerminos.objects.count(), 1)

    def test_no_reemplaza_actor_ni_fecha_si_otro_usuario_repite_aceptacion(self) -> None:
        usuario, cliente = self.preparar_cliente()
        primera = terminos.registrar_aceptacion(cliente, usuario, terminos.VERSION_TERMINOS)
        otro = User.objects.create_user(username="otro@institucion.cl")
        UsuarioPortal.objects.create(usuario=otro, cliente=cliente)
        repetida = terminos.registrar_aceptacion(cliente, otro, terminos.VERSION_TERMINOS)
        self.assertEqual(primera.pk, repetida.pk)
        self.assertEqual(repetida.usuario, usuario)
        self.assertEqual(primera.fecha_aceptacion, repetida.fecha_aceptacion)

    def test_no_puede_registrar_aceptacion_para_otra_institucion(self) -> None:
        usuario, cliente = self.preparar_cliente()
        ajeno = Cliente.objects.create(rut="14-0", razon_social="Ajena")
        with self.assertRaises(PermissionDenied):
            terminos.registrar_aceptacion(ajeno, usuario, terminos.VERSION_TERMINOS)
        self.client.force_login(usuario)
        self.client.post(
            reverse("aceptar_terminos"),
            {
                "acepta_terminos": "on",
                "version_terminos": terminos.VERSION_TERMINOS,
                "cliente_id": ajeno.pk,
            },
        )
        self.assertFalse(terminos.tiene_aceptacion_vigente(ajeno))
        self.assertTrue(terminos.tiene_aceptacion_vigente(cliente))

    def test_flujo_existente_requiere_sesion_y_cliente_asociado(self) -> None:
        respuesta = self.client.get(reverse("aceptar_terminos"))
        self.assertEqual(respuesta.status_code, 302)
        usuario = User.objects.create_user(username="sin-institucion")
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse("aceptar_terminos")).status_code, 404)
        UsuarioPortal.objects.create(usuario=usuario)
        self.assertEqual(self.client.post(reverse("aceptar_terminos"), self.datos).status_code, 404)
        self.assertFalse(AceptacionTerminos.objects.exists())

    def test_seed_no_crea_aceptaciones_automaticas(self) -> None:
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertFalse(AceptacionTerminos.objects.exists())
        for cliente in Cliente.objects.all():
            self.assertFalse(terminos.tiene_aceptacion_vigente(cliente))

    def test_base_protege_una_aceptacion_por_institucion_y_version(self) -> None:
        usuario, cliente = self.preparar_cliente()
        terminos.registrar_aceptacion(cliente, usuario, terminos.VERSION_TERMINOS)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AceptacionTerminos.objects.create(
                cliente=cliente, usuario=usuario, version_documento=terminos.VERSION_TERMINOS
            )
        self.assertEqual(AceptacionTerminos.objects.count(), 1)

    def test_servicio_rechaza_usuario_anonimo(self) -> None:
        _, cliente = self.preparar_cliente()
        with self.assertRaises(PermissionDenied):
            terminos.registrar_aceptacion(cliente, AnonymousUser(), terminos.VERSION_TERMINOS)
        self.assertFalse(AceptacionTerminos.objects.exists())

    def test_aceptar_no_evade_validacion_o_duplicidad_del_rut(self) -> None:
        respuesta = self.client.post(reverse("registro"), {**self.datos, "rut": "76.123.456-7"})
        self.assertIn("rut", respuesta.context["empresa_form"].errors)
        self.comprobar_sin_altas()
        Cliente.objects.create(rut="76123456-0")
        respuesta = self.client.post(reverse("registro"), self.datos)
        self.assertIn("rut", respuesta.context["empresa_form"].errors)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertFalse(User.objects.exists())
        self.assertFalse(AceptacionTerminos.objects.exists())


class MigracionTerminosTests(TransactionTestCase):
    def test_migracion_crea_tabla_sin_aceptar_por_clientes_existentes(self) -> None:
        executor = MigrationExecutor(connection)
        destinos = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("clientes", "0005_integrar_rut_dev")])
            cliente = Cliente.objects.create(rut="6-K", razon_social="Anterior")
            usuario = User.objects.create_user(username="anterior")
            perfil = UsuarioPortal.objects.create(usuario=usuario, cliente=cliente)
            clientes_antes = list(Cliente.objects.values())
            perfiles_antes = list(UsuarioPortal.objects.values())
            MigrationExecutor(connection).migrate(destinos)
            self.assertEqual(clientes_antes, list(Cliente.objects.values()))
            self.assertEqual(perfiles_antes, list(UsuarioPortal.objects.values()))
            self.assertFalse(AceptacionTerminos.objects.exists())
            self.assertFalse(terminos.tiene_aceptacion_vigente(cliente))
            self.assertEqual(UsuarioPortal.objects.get(pk=perfil.pk).usuario_id, usuario.pk)
        finally:
            MigrationExecutor(connection).migrate(destinos)
