from django.test import TestCase

from apps.clientes.models import Cliente

from ..models import (
    EstadoAprovisionamiento,
    EstadoInstancia,
    InstanciaMoodle,
    SolicitudAprovisionamiento,
)
from ..services import AprovisionamientoService


class ReintentosAprovisionamientoTests(TestCase):
    def crear_solicitud(self) -> SolicitudAprovisionamiento:
        cliente = Cliente.objects.create(rut="77020202-7", razon_social="Empresa Demo")
        instancia = InstanciaMoodle.objects.create(
            cliente=cliente,
            nombre="CampusDemo",
            dominio="https://demo.edocere.com",
            estado=EstadoInstancia.PENDIENTE,
        )
        return SolicitudAprovisionamiento.objects.create(instancia=instancia)

    def test_recupera_la_creacion_despues_de_dos_fallos(self) -> None:
        solicitud = self.crear_solicitud()
        service = AprovisionamientoService()

        self.assertFalse(service.procesar_simulado(solicitud, fallos=2))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.intentos, 1)
        self.assertEqual(solicitud.estado, EstadoAprovisionamiento.PENDIENTE)

        self.assertFalse(service.procesar_simulado(solicitud, fallos=2))
        self.assertTrue(service.procesar_simulado(solicitud, fallos=2))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.intentos, 3)
        self.assertEqual(solicitud.estado, EstadoAprovisionamiento.ACTIVA)
        solicitud.instancia.refresh_from_db()
        self.assertEqual(solicitud.instancia.estado, EstadoInstancia.ACTIVA)

    def test_se_detiene_despues_de_tres_fallos(self) -> None:
        solicitud = self.crear_solicitud()
        service = AprovisionamientoService()

        for _ in range(3):
            self.assertFalse(service.procesar_simulado(solicitud, fallos=3))

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.intentos, 3)
        self.assertEqual(solicitud.estado, EstadoAprovisionamiento.FALLIDA)
        solicitud.instancia.refresh_from_db()
        self.assertEqual(solicitud.instancia.estado, EstadoInstancia.FALLIDA)
