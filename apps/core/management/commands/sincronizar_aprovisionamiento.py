"""Sincroniza tablas locales con los endpoints de lectura de tenantctl v1."""

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import (
    EstadoAprovisionamiento,
    EstadoInstancia,
    InstanciaMoodle,
    SolicitudAprovisionamiento,
)
from apps.instancias.sync_client import JsonObject, TenantctlReadClient, TenantctlReadError

PAGE_SIZE = 200
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
OPERATION_STATES = {
    "PENDING": EstadoAprovisionamiento.PENDIENTE,
    "RUNNING": EstadoAprovisionamiento.EN_PROCESO,
    "COMPLETED": EstadoAprovisionamiento.ACTIVA,
    "FAILED": EstadoAprovisionamiento.FALLIDA,
}
USAGE_METADATA_FIELDS = (
    "tenant_slug",
    "period",
    "period_timezone",
    "activity_definition_version",
    "snapshot_id",
    "revision",
    "status",
)


@dataclass(frozen=True)
class TenantLocal:
    slug: str
    summary: JsonObject
    instance: InstanciaMoodle


@dataclass(frozen=True)
class UsageUpdate:
    instance: InstanciaMoodle
    year: int
    month: int
    active_users: int
    course_count: int


def _previous_month() -> str:
    first_day = timezone.localdate().replace(day=1)
    previous_day = first_day - timedelta(days=1)
    return previous_day.strftime("%Y-%m")


def _hostname(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    raw = value.strip()
    try:
        parsed = urlsplit(raw if "://" in raw else f"//{raw}")
    except ValueError:
        return ""
    return (parsed.hostname or "").lower()


def _fetch_all_pages(
    fetch_page: Callable[..., JsonObject | None],
    **arguments: Any,
) -> list[JsonObject] | None:
    items: list[JsonObject] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()

    while True:
        page = fetch_page(limit=PAGE_SIZE, cursor=cursor, **arguments)
        if page is None:
            return None

        page_items = page.get("items")
        if not isinstance(page_items, list) or not all(
            isinstance(item, dict) for item in page_items
        ):
            raise TenantctlReadError("La página de tenantctl no contiene una lista items válida.")
        if "next_cursor" not in page:
            raise TenantctlReadError("La página de tenantctl no contiene next_cursor.")
        items.extend(page_items)

        next_cursor = page["next_cursor"]
        if next_cursor is None:
            return items
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
            raise TenantctlReadError("tenantctl devolvió un cursor de paginación inválido.")
        seen_cursors.add(next_cursor)
        cursor = next_cursor


def _instance_status(api_status: Any) -> str | None:
    if not isinstance(api_status, str):
        return None
    if api_status == "PROVISIONING":
        return EstadoInstancia.PENDING
    if api_status in EstadoInstancia.values:
        return api_status
    return None


def _usage_is_valid(usage: JsonObject, slug: str, month: str) -> bool:
    active_users = usage.get("billable_users")
    return (
        usage.get("tenant_slug") == slug
        and usage.get("period") == month
        and usage.get("evidence_complete") is True
        and type(active_users) is int
        and active_users >= 0
        and all(
            isinstance(usage.get(field), str) and usage[field]
            for field in (
                "period_timezone",
                "activity_definition_version",
                "snapshot_id",
                "status",
            )
        )
        and type(usage.get("revision")) is int
        and usage["revision"] >= 1
        and usage["status"] in {"PROVISIONAL", "CLOSED"}
    )


class Command(BaseCommand):
    help = "Sincroniza instancias, operaciones y métricas mensuales desde tenantctl v1."

    def add_arguments(self, parser: CommandParser) -> None:
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument("--solo-instancias", action="store_true")
        modes.add_argument("--solo-uso", action="store_true")
        parser.add_argument(
            "--month", default=_previous_month(), help="Período en formato YYYY-MM."
        )
        parser.add_argument("--owner-ref", help="Filtra tenants por el identificador de Edocere.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Consulta la API y muestra los cambios sin escribir en la base de datos.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        month = options["month"]
        if not isinstance(month, str) or not MONTH_RE.fullmatch(month):
            raise CommandError("--month debe tener formato YYYY-MM válido.")

        try:
            client = TenantctlReadClient()
            tenant_pages = _fetch_all_pages(
                client.list_tenants,
                owner_ref=options["owner_ref"],
            )
            if tenant_pages is None:
                raise CommandError(
                    "tenantctl no devolvió la lista de tenants; no se realizaron cambios."
                )

            tenants = self._link_local_tenants(tenant_pages, options["owner_ref"])
            instance_updates: list[tuple[InstanciaMoodle, dict[str, str]]] = []
            operation_updates: list[tuple[str, dict[str, Any]]] = []
            usage_updates: list[UsageUpdate] = []

            if not options["solo_uso"]:
                instance_updates = self._prepare_instances(client, tenants)
                operation_updates = self._prepare_operations(client, tenants)
            if not options["solo_instancias"]:
                usage_updates = self._prepare_usage(client, tenants, month)
        except TenantctlReadError as error:
            raise CommandError(f"Falló la sincronización con tenantctl: {error}") from error

        counts = (len(instance_updates), len(operation_updates), len(usage_updates))
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run: se sincronizarían "
                    f"{counts[0]} instancias, {counts[1]} operaciones y "
                    f"{counts[2]} mediciones; no se escribió en la base de datos."
                )
            )
            return

        with transaction.atomic():
            for instance, defaults in instance_updates:
                InstanciaMoodle.objects.filter(pk=instance.pk).update(**defaults)
            for operation_id, defaults in operation_updates:
                SolicitudAprovisionamiento.objects.update_or_create(
                    operation_id=operation_id,
                    defaults=defaults,
                )
            for usage in usage_updates:
                metrics = {
                    "usuarios_activos": usage.active_users,
                    "cantidad_cursos": usage.course_count,
                }
                MedicionUsoMensual.objects.update_or_create(
                    instancia=usage.instance,
                    anio=usage.year,
                    mes=usage.month,
                    defaults=metrics,
                    create_defaults={
                        **metrics,
                        "usuarios_inscritos": 0,
                        "total_matriculas": 0,
                        "cantidad_categorias": 0,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronización terminada: {counts[0]} instancias, "
                f"{counts[1]} operaciones y {counts[2]} mediciones."
            )
        )

    def _link_local_tenants(
        self,
        summaries: list[JsonObject],
        owner_ref_filter: str | None,
    ) -> dict[str, TenantLocal]:
        clients = {str(client.pk): client for client in Cliente.objects.all()}
        instances_by_owner_host: defaultdict[tuple[int, str], list[InstanciaMoodle]] = defaultdict(
            list
        )
        for instance in InstanciaMoodle.objects.select_related("cliente"):
            host = _hostname(instance.dominio)
            if host:
                instances_by_owner_host[(instance.cliente_id, host)].append(instance)

        tenants: dict[str, TenantLocal] = {}
        duplicate_slugs: set[str] = set()
        for summary in summaries:
            slug = summary.get("tenant_slug")
            owner_ref = summary.get("owner_ref")
            host = _hostname(summary.get("primary_hostname"))
            if not isinstance(slug, str) or not slug or not host:
                self.stderr.write("Tenant omitido: falta tenant_slug o primary_hostname válido.")
                continue
            if owner_ref_filter is not None and str(owner_ref) != owner_ref_filter:
                continue
            client = clients.get(str(owner_ref))
            if client is None:
                self.stderr.write(
                    f"Tenant {slug} omitido: owner_ref {owner_ref!r} no corresponde "
                    "a un Cliente local."
                )
                continue

            matches = instances_by_owner_host.get((client.pk, host), [])
            if len(matches) != 1:
                self.stderr.write(
                    f"Tenant {slug} omitido: {host!r} coincide con {len(matches)} "
                    "instancias del Cliente local."
                )
                continue
            if slug in tenants or slug in duplicate_slugs:
                tenants.pop(slug, None)
                duplicate_slugs.add(slug)
                self.stderr.write(f"Tenant {slug} omitido: aparece más de una vez en la API.")
                continue
            tenants[slug] = TenantLocal(slug, summary, matches[0])

        return tenants

    def _prepare_instances(
        self,
        client: TenantctlReadClient,
        tenants: dict[str, TenantLocal],
    ) -> list[tuple[InstanciaMoodle, dict[str, str]]]:
        updates: list[tuple[InstanciaMoodle, dict[str, str]]] = []
        for tenant in tenants.values():
            detail = client.get_tenant(tenant.slug)
            if detail is None:
                self.stderr.write(
                    f"Tenant {tenant.slug} omitido para actualización: detalle no disponible."
                )
                continue
            if detail.get("tenant_slug") != tenant.slug:
                raise TenantctlReadError(
                    f"El detalle recibido no corresponde al tenant {tenant.slug}."
                )
            summary_host = _hostname(tenant.summary.get("primary_hostname"))
            detail_host = _hostname(detail.get("primary_hostname"))
            if detail_host and detail_host != summary_host:
                raise TenantctlReadError(
                    f"primary_hostname cambió durante la lectura de {tenant.slug}; "
                    "se cancela la sincronización para evitar una asociación incorrecta."
                )

            defaults: dict[str, str] = {}
            branding = detail.get("branding")
            if isinstance(branding, dict):
                site_name = branding.get("site_name")
                if isinstance(site_name, str) and site_name:
                    defaults["nombre"] = site_name[:255]
            version = detail.get("moodle_version")
            if isinstance(version, str) and version:
                defaults["version"] = version[:255]

            status = _instance_status(detail.get("status", tenant.summary.get("status")))
            if status is not None:
                defaults["estado"] = status
            elif detail.get("status") == "DEPROVISIONING":
                self.stderr.write(
                    f"Tenant {tenant.slug}: DEPROVISIONING no se mapea todavía; "
                    "se conserva el estado local."
                )
            elif detail.get("status") is not None:
                self.stderr.write(
                    f"Tenant {tenant.slug}: estado {detail['status']!r} no representable; "
                    "se conserva el estado local."
                )
            if defaults:
                updates.append((tenant.instance, defaults))
        return updates

    def _prepare_operations(
        self,
        client: TenantctlReadClient,
        tenants: dict[str, TenantLocal],
    ) -> list[tuple[str, dict[str, Any]]]:
        if not tenants:
            return []
        operations = _fetch_all_pages(
            client.list_operations,
            operation_type="PROVISION",
        )
        if operations is None:
            raise CommandError(
                "GET /operations no devolvió datos; no se sincronizaron operaciones."
            )

        updates: list[tuple[str, dict[str, Any]]] = []
        omitted_fields = {field.name for field in SolicitudAprovisionamiento._meta.get_fields()}
        missing_fields = {"intentos", "codigo_error", "detalle_error"} - omitted_fields
        warned_about_fields = False
        for operation in operations:
            if operation.get("operation_type") != "PROVISION":
                continue
            tenant = tenants.get(str(operation.get("tenant_slug", "")))
            operation_id = operation.get("operation_id")
            status = OPERATION_STATES.get(str(operation.get("status", "")))
            if (
                tenant is None
                or not isinstance(operation_id, str)
                or not operation_id
                or status is None
            ):
                continue

            defaults: dict[str, Any] = {"instancia": tenant.instance, "estado": status}
            updates.append((operation_id, defaults))
            if not warned_about_fields and (
                "attempt_count" in operation or operation.get("error") is not None
            ):
                if missing_fields:
                    self.stderr.write(
                        self.style.WARNING(
                            "SolicitudAprovisionamiento no tiene los campos "
                            f"{', '.join(sorted(missing_fields))}; los datos de reintento/error "
                            "no se pueden persistir sin cambiar el esquema."
                        )
                    )
                warned_about_fields = True
        return updates

    def _prepare_usage(
        self,
        client: TenantctlReadClient,
        tenants: dict[str, TenantLocal],
        month: str,
    ) -> list[UsageUpdate]:
        year, month_number = (int(value) for value in month.split("-"))
        updates: list[UsageUpdate] = []
        for tenant in tenants.values():
            usage = client.get_monthly_usage(tenant.slug, month)
            if usage is None:
                self.stderr.write(
                    f"Uso de {tenant.slug} para {month} omitido: no hay evidencia disponible."
                )
                continue
            if not _usage_is_valid(usage, tenant.slug, month):
                self.stderr.write(
                    f"Uso de {tenant.slug} para {month} omitido: agregado incompleto o inválido."
                )
                continue

            courses = self._fetch_usage_courses(client, tenant.slug, month, usage)
            if courses is None:
                self.stderr.write(
                    f"Uso de {tenant.slug} para {month} omitido: no hay páginas de cursos "
                    "disponibles."
                )
                continue
            updates.append(
                UsageUpdate(
                    tenant.instance,
                    year,
                    month_number,
                    usage["billable_users"],
                    len(courses),
                )
            )
        return updates

    def _fetch_usage_courses(
        self,
        client: TenantctlReadClient,
        slug: str,
        month: str,
        usage: JsonObject,
    ) -> list[JsonObject] | None:
        courses: list[JsonObject] = []
        seen_course_refs: set[str] = set()
        cursor: str | None = None
        seen_cursors: set[str] = set()

        while True:
            page = client.list_usage_courses(
                slug,
                month,
                limit=PAGE_SIZE,
                cursor=cursor,
            )
            if page is None:
                return None
            if any(page.get(field) != usage.get(field) for field in USAGE_METADATA_FIELDS):
                raise TenantctlReadError(
                    f"Las páginas de cursos de {slug} no pertenecen al mismo snapshot de /usage."
                )
            items = page.get("items")
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                raise TenantctlReadError(
                    f"La página de cursos de {slug} no contiene una lista items válida."
                )
            if "next_cursor" not in page:
                raise TenantctlReadError(f"La página de cursos de {slug} no contiene next_cursor.")
            for item in items:
                course_ref = item.get("course_ref")
                qualifying_events = item.get("qualifying_event_count")
                if (
                    not isinstance(course_ref, str)
                    or not course_ref
                    or course_ref in seen_course_refs
                    or type(qualifying_events) is not int
                    or qualifying_events < 1
                ):
                    raise TenantctlReadError(
                        f"La página de cursos de {slug} contiene un elemento inválido."
                    )
                seen_course_refs.add(course_ref)
                courses.append(item)

            next_cursor = page["next_cursor"]
            if next_cursor is None:
                return courses
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
                raise TenantctlReadError(
                    f"tenantctl devolvió un cursor de cursos inválido para {slug}."
                )
            seen_cursors.add(next_cursor)
            cursor = next_cursor
