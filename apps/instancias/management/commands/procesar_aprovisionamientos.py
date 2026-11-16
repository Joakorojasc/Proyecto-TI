import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import close_old_connections

from apps.instancias.models import (
    EstadoAprovisionamiento,
    SolicitudAprovisionamiento,
)
from apps.instancias.services import AprovisionamientoError, AprovisionamientoService
from apps.pagos.services import estado_cliente_para_instancia
from apps.planes.models import Suscripcion


class Command(BaseCommand):
    help = "Procesa automáticamente hasta tres intentos de creación simulada."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--simular", action="store_true")
        parser.add_argument("--fallos", type=int, default=0)
        parser.add_argument("--una-vez", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["simular"] or options["fallos"] not in range(4):
            raise CommandError("Usa --simular y --fallos 0, 1, 2 o 3.")
        self.stdout.write("SIMULADOR activo. No instala Moodle real. Ctrl+C para detener.")
        try:
            while True:
                self.procesar_pendientes(options["fallos"])
                if options["una_vez"]:
                    return
                time.sleep(5)
        except KeyboardInterrupt:
            self.stdout.write("\nSimulador detenido.")

    def procesar_pendientes(self, fallos: int) -> None:
        close_old_connections()
        solicitudes = SolicitudAprovisionamiento.objects.filter(
            estado=EstadoAprovisionamiento.PENDIENTE,
        ).select_related("instancia")
        for solicitud in solicitudes:
            suscripcion = (
                Suscripcion.objects.filter(instancia=solicitud.instancia).order_by("-pk").first()
            )
            if (
                suscripcion is None
                or estado_cliente_para_instancia(
                    solicitud.instancia.cliente_id,
                    suscripcion_id=suscripcion.pk,
                )
                != "aprobada"
            ):
                continue
            try:
                activa = AprovisionamientoService().procesar_simulado(solicitud, fallos)
            except AprovisionamientoError as exc:
                self.stderr.write(str(exc))
                continue
            solicitud.refresh_from_db(fields=["intentos"])
            resultado = "Funciona" if activa else "Falla"
            self.stdout.write(
                f"Solicitud {solicitud.pk}: intento {solicitud.intentos}: {resultado}"
            )
