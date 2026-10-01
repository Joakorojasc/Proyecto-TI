from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import InstanciaMoodle
from apps.planes.models import Plan, Suscripcion


class Command(BaseCommand):
    help = "Crea o actualiza el dataset demo determinista del portal."

    @staticmethod
    def fecha_demo(year: int, month: int) -> datetime:
        return timezone.make_aware(datetime(year, month, 1))

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        planes = self.crear_planes()
        clientes = self.crear_clientes()
        instancias = self.crear_instancias(clientes)
        suscripciones = self.crear_suscripciones(instancias, planes)
        self.crear_mediciones(instancias)

        self.stdout.write(
            self.style.SUCCESS(
                "Dataset demo creado o actualizado: "
                f"{len(clientes)} clientes, {len(planes)} planes, "
                f"{len(suscripciones)} suscripciones, {len(instancias)} instancias "
                "y 12 mediciones."
            )
        )

    @staticmethod
    def crear_planes() -> dict[str, Plan]:
        definiciones: list[dict[str, Any]] = [
            {
                "clave": "PLAN-DEMO-MENSUAL",
                "nombre": "Plan mensual demo",
                "tipo_plan": "mensual",
                "precio_base": None,
                "precio_por_usuario": Decimal("1.50"),
                "limite_usuarios": None,
            },
            {
                "clave": "PLAN-DEMO-ANUAL-1000",
                "nombre": "Plan anual demo hasta 1000 usuarios",
                "tipo_plan": "anual",
                "precio_base": Decimal("1000.00"),
                "precio_por_usuario": None,
                "limite_usuarios": 1000,
            },
            {
                "clave": "PLAN-DEMO-ANUAL-2000",
                "nombre": "Plan anual demo hasta 2000 usuarios",
                "tipo_plan": "anual",
                "precio_base": Decimal("1800.00"),
                "precio_por_usuario": None,
                "limite_usuarios": 2000,
            },
            {
                "clave": "PLAN-DEMO-ANUAL-3000",
                "nombre": "Plan anual demo hasta 3000 usuarios",
                "tipo_plan": "anual",
                "precio_base": Decimal("2500.00"),
                "precio_por_usuario": None,
                "limite_usuarios": 3000,
            },
        ]
        planes: dict[str, Plan] = {}
        for definicion in definiciones:
            clave = definicion.pop("clave")
            plan, _ = Plan.objects.update_or_create(
                nombre=definicion["nombre"],
                defaults=definicion,
            )
            planes[clave] = plan
        return planes

    @staticmethod
    def crear_clientes() -> dict[str, Cliente]:
        definiciones: list[dict[str, Any]] = [
            {
                "clave": "DEMO-CLIENTE-PEQUENO",
                "rut": "DEMO-PEQUENO-001",
                "razon_social": "Empresa Demo Pequeña SpA",
            },
            {
                "clave": "DEMO-CLIENTE-MEDIANO",
                "rut": "DEMO-MEDIANO-001",
                "razon_social": "Empresa Demo Mediana SpA",
            },
            {
                "clave": "DEMO-CLIENTE-ANUAL",
                "rut": "DEMO-ANUAL-001",
                "razon_social": "Organización Demo Anual SpA",
            },
        ]
        clientes: dict[str, Cliente] = {}
        for definicion in definiciones:
            clave = definicion.pop("clave")
            cliente, _ = Cliente.objects.update_or_create(
                rut=definicion["rut"],
                defaults={
                    **definicion,
                    "giro": "Demostración de software",
                    "direccion_facturacion": "Dirección demo 100",
                    "email_contacto": "demo@ejemplo.invalid",
                    "created_at": timezone.make_aware(datetime(2026, 1, 1)),
                },
            )
            clientes[clave] = cliente
        return clientes

    @staticmethod
    def crear_suscripciones(
        instancias: dict[str, InstanciaMoodle], plans: dict[str, Plan]
    ) -> dict[str, Suscripcion]:
        definiciones = [
            ("PEQUENA", "PLAN-DEMO-MENSUAL"),
            ("MEDIANA", "PLAN-DEMO-MENSUAL"),
            ("ANUAL_PRINCIPAL", "PLAN-DEMO-ANUAL-2000"),
            ("ANUAL_SECUNDARIA", "PLAN-DEMO-ANUAL-2000"),
        ]
        suscripciones: dict[str, Suscripcion] = {}
        for instancia_clave, plan_clave in definiciones:
            instancia = instancias[instancia_clave]
            plan = plans[plan_clave]
            suscripcion, _ = Suscripcion.objects.update_or_create(
                instancia=instancia,
                defaults={
                    "cliente": instancia.cliente,
                    "plan": plan,
                    "estado": "activa",
                    "fecha_inicio": timezone.make_aware(datetime(2026, 1, 1)),
                },
            )
            suscripciones[instancia_clave] = suscripcion
        return suscripciones

    @staticmethod
    def crear_instancias(clientes: dict[str, Cliente]) -> dict[str, InstanciaMoodle]:
        definiciones = [
            ("PEQUENA", "DEMO-CLIENTE-PEQUENO", "pequena.demo.invalid"),
            ("MEDIANA", "DEMO-CLIENTE-MEDIANO", "mediana.demo.invalid"),
            ("ANUAL_PRINCIPAL", "DEMO-CLIENTE-ANUAL", "anual-principal.demo.invalid"),
            ("ANUAL_SECUNDARIA", "DEMO-CLIENTE-ANUAL", "anual-secundaria.demo.invalid"),
        ]
        instancias: dict[str, InstanciaMoodle] = {}
        for clave, cliente_clave, dominio in definiciones:
            instancia, _ = InstanciaMoodle.objects.update_or_create(
                dominio=dominio,
                defaults={
                    "cliente": clientes[cliente_clave],
                    "version": "5.2-demo",
                    "estado": "activa",
                },
            )
            instancias[clave] = instancia
        return instancias

    @staticmethod
    def crear_mediciones(instancias: dict[str, InstanciaMoodle]) -> None:
        mediciones = {
            "PEQUENA": [(6, 8, 3), (8, 9, 3), (12, 10, 4)],
            "MEDIANA": [(42, 18, 5), (50, 20, 6), (54, 22, 6)],
            "ANUAL_PRINCIPAL": [(1450, 75, 12), (1500, 80, 13), (1550, 86, 14)],
            "ANUAL_SECUNDARIA": [(420, 28, 7), (450, 31, 8), (400, 34, 8)],
        }
        for clave, valores_mensuales in mediciones.items():
            for month, valores in enumerate(valores_mensuales, start=1):
                usuarios_activos, cantidad_cursos, cantidad_categorias = valores
                MedicionUsoMensual.objects.update_or_create(
                    instancia=instancias[clave],
                    mes=month,
                    anio=2026,
                    defaults={
                        "usuarios_activos": usuarios_activos,
                        "cantidad_cursos": cantidad_cursos,
                        "cantidad_categorias": cantidad_categorias,
                    },
                )
