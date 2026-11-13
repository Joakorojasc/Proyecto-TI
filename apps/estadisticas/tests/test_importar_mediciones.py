"""Comando importar_mediciones.

Una fila mala se omite y se reporta sin frenar las demás. Un archivo que no se
puede interpretar se rechaza completo antes de escribir nada.
"""

import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.clientes.models import Cliente
from apps.estadisticas.models import MedicionUsoMensual
from apps.estadisticas.tests.test_vista import URL, crear_usuario_con_cliente
from apps.instancias.models import EstadoInstancia, InstanciaMoodle

ENCABEZADO = (
    "dominio,anio,mes,usuarios_inscritos,usuarios_activos,"
    "cantidad_cursos,total_matriculas,cantidad_categorias"
)
DOMINIO = "campus.demo.invalid"
FILA = f"{DOMINIO},2026,3,150,120,15,300,4"


class ImportarMedicionesCase(TestCase):
    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(rut="76543210-3", razon_social="Colegio")
        self.instancia = self.crear_instancia(f"https://{DOMINIO}")
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.carpeta = Path(carpeta.name)

    def crear_instancia(self, dominio: str | None) -> InstanciaMoodle:
        return InstanciaMoodle.objects.create(cliente=self.cliente, dominio=dominio)

    def escribir(self, contenido: str | bytes) -> Path:
        ruta = self.carpeta / "mediciones.csv"
        datos = contenido.encode() if isinstance(contenido, str) else contenido
        ruta.write_bytes(datos)
        return ruta

    def importar(self, *filas: str, encabezado: str = ENCABEZADO) -> tuple[str, str]:
        """Corre el comando y devuelve lo que escribió en stdout y stderr."""
        return self.importar_archivo(self.escribir("\n".join([encabezado, *filas]) + "\n"))

    def importar_archivo(self, ruta: Path | str) -> tuple[str, str]:
        salida, errores = StringIO(), StringIO()
        call_command("importar_mediciones", str(ruta), stdout=salida, stderr=errores)
        return salida.getvalue(), errores.getvalue()


class CargaTests(ImportarMedicionesCase):
    def test_crea_la_medicion_con_todas_las_columnas(self) -> None:
        salida, errores = self.importar(FILA)

        medicion = MedicionUsoMensual.objects.get()
        self.assertEqual(medicion.instancia, self.instancia)
        self.assertEqual((medicion.anio, medicion.mes), (2026, 3))
        self.assertEqual(medicion.usuarios_inscritos, 150)
        self.assertEqual(medicion.usuarios_activos, 120)
        self.assertEqual(medicion.cantidad_cursos, 15)
        self.assertEqual(medicion.total_matriculas, 300)
        self.assertEqual(medicion.cantidad_categorias, 4)
        self.assertIn("1 creadas, 0 actualizadas y 0 omitidas", salida)
        self.assertEqual(errores, "")

    def test_el_mismo_mes_se_actualiza_sin_duplicar(self) -> None:
        self.importar(FILA)
        salida, _ = self.importar(f"{DOMINIO},2026,3,200,180,16,320,5")

        medicion = MedicionUsoMensual.objects.get()
        self.assertEqual(medicion.usuarios_inscritos, 200)
        self.assertEqual(medicion.cantidad_categorias, 5)
        self.assertIn("0 creadas, 1 actualizadas", salida)

    def test_otro_mes_crea_otra_medicion(self) -> None:
        self.importar(FILA, f"{DOMINIO},2026,4,150,120,15,300,4")

        self.assertEqual(MedicionUsoMensual.objects.count(), 2)

    def test_el_dominio_se_reconoce_con_o_sin_esquema_y_mayusculas(self) -> None:
        for dominio in (DOMINIO, f"https://{DOMINIO}", f"http://{DOMINIO}/", DOMINIO.upper()):
            with self.subTest(dominio=dominio):
                MedicionUsoMensual.objects.all().delete()
                self.importar(f"{dominio},2026,3,150,120,15,300,4")
                self.assertEqual(MedicionUsoMensual.objects.get().instancia, self.instancia)

    def test_una_instancia_archivada_tambien_recibe_mediciones(self) -> None:
        InstanciaMoodle.objects.filter(pk=self.instancia.pk).update(
            estado=EstadoInstancia.DEPROVISIONED
        )

        self.importar(FILA)

        self.assertEqual(MedicionUsoMensual.objects.count(), 1)

    def test_una_celda_vacia_queda_sin_dato(self) -> None:
        self.importar(f"{DOMINIO},2026,3,,120,15,,4")

        medicion = MedicionUsoMensual.objects.get()
        self.assertIsNone(medicion.usuarios_inscritos)
        self.assertIsNone(medicion.total_matriculas)
        self.assertEqual(medicion.usuarios_activos, 120)

    def test_una_celda_vacia_no_borra_el_dato_que_ya_estaba(self) -> None:
        self.importar(FILA)
        self.importar(f"{DOMINIO},2026,3,,130,,,")

        medicion = MedicionUsoMensual.objects.get()
        self.assertEqual(medicion.usuarios_activos, 130)
        self.assertEqual(medicion.usuarios_inscritos, 150)
        self.assertEqual(medicion.total_matriculas, 300)

    def test_lee_el_formato_que_guarda_excel_en_espanol(self) -> None:
        contenido = f"{ENCABEZADO}\r\n{FILA}\r\n".replace(",", ";")
        self.importar_archivo(self.escribir(b"\xef\xbb\xbf" + contenido.encode()))

        self.assertEqual(MedicionUsoMensual.objects.get().total_matriculas, 300)

    def test_el_encabezado_acepta_espacios_y_mayusculas(self) -> None:
        self.importar(FILA, encabezado=ENCABEZADO.upper().replace(",", " , "))

        self.assertEqual(MedicionUsoMensual.objects.count(), 1)

    def test_lo_importado_se_ve_en_la_pantalla_de_estadisticas(self) -> None:
        usuario, cliente = crear_usuario_con_cliente("pantalla", "77777777-7")
        InstanciaMoodle.objects.create(cliente=cliente, dominio="propio.demo.invalid", nombre="X")

        self.importar("propio.demo.invalid,2026,3,987,654,10,250,3")
        self.client.force_login(usuario)
        respuesta = self.client.get(URL)

        self.assertContains(respuesta, "987")
        self.assertContains(respuesta, "25,0")


class FilaInvalidaTests(ImportarMedicionesCase):
    def test_se_omiten_las_filas_invalidas(self) -> None:
        casos = {
            "mes 13": (f"{DOMINIO},2026,13,1,1,1,1,1", "mes debe estar entre 1 y 12"),
            "mes 0": (f"{DOMINIO},2026,0,1,1,1,1,1", "mes debe estar entre 1 y 12"),
            "sin mes": (f"{DOMINIO},2026,,1,1,1,1,1", "faltan anio o mes"),
            "sin anio": (f"{DOMINIO},,3,1,1,1,1,1", "faltan anio o mes"),
            "anio de dos cifras": (f"{DOMINIO},26,3,1,1,1,1,1", "anio no parece válido"),
            "período futuro": (f"{DOMINIO},2999,1,1,1,1,1,1", "todavía no ocurre"),
            "negativo": (f"{DOMINIO},2026,3,-1,1,1,1,1", "usuarios_inscritos está fuera de rango"),
            "no cabe": (f"{DOMINIO},2026,3,1,99999999999,1,1,1", "usuarios_activos está fuera"),
            "texto": (f"{DOMINIO},2026,3,1,1,muchos,1,1", "cantidad_cursos debe ser un número"),
            "decimal": (f"{DOMINIO},2026,3,1,1,1,1.5,1", "total_matriculas debe ser un número"),
            "sin métricas": (f"{DOMINIO},2026,3,,,,,", "no trae ninguna métrica"),
            "sin dominio": (",2026,3,1,1,1,1,1", "falta el dominio"),
            "dominio ajeno": ("otro.demo.invalid,2026,3,1,1,1,1,1", "no hay una instancia"),
            "columnas de más": (
                f"{DOMINIO},2026,3,1,950,1,1,1,1",
                "más columnas que el encabezado",
            ),
            "columnas de menos": (DOMINIO, "faltan anio o mes"),
        }
        for nombre, (fila, motivo) in casos.items():
            with self.subTest(nombre):
                salida, errores = self.importar(fila)
                self.assertIn(motivo, errores)
                self.assertIn("Línea 2:", errores)
                self.assertIn("0 creadas, 0 actualizadas y 1 omitidas", salida)
                self.assertFalse(MedicionUsoMensual.objects.exists())

    def test_una_fila_invalida_no_frena_las_demas(self) -> None:
        salida, errores = self.importar(
            f"{DOMINIO},2026,1,1,1,1,1,1",
            f"{DOMINIO},2026,13,1,1,1,1,1",
            f"{DOMINIO},2026,2,1,1,1,1,1",
        )

        self.assertEqual(MedicionUsoMensual.objects.count(), 2)
        self.assertIn("2 creadas, 0 actualizadas y 1 omitidas", salida)
        self.assertIn("Línea 3:", errores)

    def test_un_dominio_de_dos_instancias_se_omite(self) -> None:
        self.crear_instancia(DOMINIO)

        _, errores = self.importar(FILA)

        self.assertIn("coincide con 2 instancias", errores)
        self.assertFalse(MedicionUsoMensual.objects.exists())

    def test_un_dominio_ilegible_no_calza_con_instancias_sin_dominio(self) -> None:
        self.crear_instancia(None)

        _, errores = self.importar("http://[roto,2026,3,1,1,1,1,1")

        self.assertIn("no hay una instancia", errores)
        self.assertFalse(MedicionUsoMensual.objects.exists())

    def test_un_periodo_repetido_en_el_archivo_conserva_la_primera_fila(self) -> None:
        _, errores = self.importar(FILA, f"{DOMINIO},2026,3,999,999,999,999,999")

        self.assertIn("Línea 3:", errores)
        self.assertIn("ya venía en el archivo", errores)
        self.assertEqual(MedicionUsoMensual.objects.get().usuarios_inscritos, 150)

    def test_dos_mediciones_previas_del_mismo_mes_no_se_tocan(self) -> None:
        for activos in (1, 2):
            MedicionUsoMensual.objects.create(
                instancia=self.instancia, anio=2026, mes=3, usuarios_activos=activos
            )

        salida, errores = self.importar(FILA)

        self.assertIn("ya hay varias mediciones", errores)
        self.assertIn("1 omitidas", salida)
        self.assertEqual(
            sorted(MedicionUsoMensual.objects.values_list("usuarios_activos", flat=True)), [1, 2]
        )


class ArchivoInvalidoTests(ImportarMedicionesCase):
    def test_sin_una_columna_se_rechaza_el_archivo_completo(self) -> None:
        encabezado = ENCABEZADO.replace(",total_matriculas", "")

        with self.assertRaisesRegex(CommandError, "faltan columnas: total_matriculas"):
            self.importar(f"{DOMINIO},2026,3,150,120,15,4", encabezado=encabezado)

        self.assertFalse(MedicionUsoMensual.objects.exists())

    def test_un_archivo_vacio_se_rechaza(self) -> None:
        with self.assertRaisesRegex(CommandError, "faltan columnas"):
            self.importar_archivo(self.escribir(""))

    def test_un_archivo_que_no_existe_se_rechaza(self) -> None:
        with self.assertRaisesRegex(CommandError, "No se pudo abrir"):
            self.importar_archivo(self.carpeta / "no-existe.csv")

    def test_un_archivo_que_no_esta_en_utf8_se_rechaza_sin_cargar_nada(self) -> None:
        contenido = f"{ENCABEZADO}\n{FILA}\n{DOMINIO},2026,4,1,1,1,1,1 ñ\n".encode("latin-1")

        with self.assertRaisesRegex(CommandError, "UTF-8"):
            self.importar_archivo(self.escribir(contenido))

        self.assertFalse(MedicionUsoMensual.objects.exists())

    def test_un_csv_ilegible_se_rechaza_sin_cargar_nada(self) -> None:
        # Una celda más grande que el límite del módulo csv.
        contenido = f"{ENCABEZADO}\n{FILA}\n{'x' * 200_000},2026,4,1,1,1,1,1\n"

        with self.assertRaisesRegex(CommandError, "No se pudo leer"):
            self.importar_archivo(self.escribir(contenido))

        self.assertFalse(MedicionUsoMensual.objects.exists())
