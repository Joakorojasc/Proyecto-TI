from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from ..models import Cliente
from ..validators import calcular_digito_verificador, formatear_rut, normalizar_rut, validar_rut


class DigitoVerificadorTests(TestCase):
    def test_calcula_el_digito_de_ruts_conocidos(self) -> None:
        self.assertEqual(calcular_digito_verificador("76543210"), "3")
        self.assertEqual(calcular_digito_verificador("77777777"), "7")
        self.assertEqual(calcular_digito_verificador("12345678"), "5")

    def test_devuelve_cero_cuando_el_resto_es_cero(self) -> None:
        self.assertEqual(calcular_digito_verificador("76123456"), "0")

    def test_devuelve_k_cuando_el_resto_es_uno(self) -> None:
        self.assertEqual(calcular_digito_verificador("76055555"), "K")


class NormalizacionTests(TestCase):
    def test_saca_puntos_y_espacios(self) -> None:
        self.assertEqual(normalizar_rut(" 76.543.210-3 "), "76543210-3")

    def test_agrega_el_guion_si_falta(self) -> None:
        self.assertEqual(normalizar_rut("765432103"), "76543210-3")

    def test_pone_la_k_en_mayuscula(self) -> None:
        self.assertEqual(normalizar_rut("76.055.555-k"), "76055555-K")

    def test_conserva_entrada_con_espacios_que_aceptaba_dev(self) -> None:
        self.assertEqual(normalizar_rut("76 543 210 3"), "76543210-3")

    def test_formatea_con_puntos_para_mostrar(self) -> None:
        self.assertEqual(formatear_rut("76543210-3"), "76.543.210-3")

    def test_formateo_no_oculta_un_valor_invalido(self) -> None:
        self.assertEqual(formatear_rut("dato antiguo"), "dato antiguo")


class ValidacionTests(TestCase):
    def test_acepta_rut_valido_con_y_sin_puntos(self) -> None:
        validar_rut("76.543.210-3")
        validar_rut("76543210-3")

    def test_acepta_rut_terminado_en_k(self) -> None:
        validar_rut("76.055.555-K")

    def test_acepta_rut_de_persona_natural(self) -> None:
        # Un profesor independiente puede ser cliente, así que no exigimos
        # que el número sea del rango de las empresas.
        validar_rut("12.345.678-5")

    def test_rechaza_digito_verificador_incorrecto(self) -> None:
        with self.assertRaises(ValidationError) as caso:
            validar_rut("76.543.210-9")
        self.assertEqual(caso.exception.code, "rut_digito")

    def test_rechaza_texto_que_no_es_rut(self) -> None:
        with self.assertRaises(ValidationError) as caso:
            validar_rut("DEMO-PEQUENO-001")
        self.assertEqual(caso.exception.code, "rut_formato")

    def test_rechaza_vacio(self) -> None:
        with self.assertRaises(ValidationError):
            validar_rut("")


class ClienteRutTests(TestCase):
    def test_guarda_el_rut_normalizado(self) -> None:
        cliente = Cliente.objects.create(rut="76.543.210-3", razon_social="Colegio Demo")
        cliente.refresh_from_db()
        self.assertEqual(cliente.rut, "76543210-3")

    def test_los_dos_formatos_son_el_mismo_rut(self) -> None:
        Cliente.objects.create(rut="76.543.210-3", razon_social="Colegio Uno")
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(rut="76543210-3", razon_social="Colegio Dos")

    def test_no_permite_dos_clientes_con_el_mismo_rut(self) -> None:
        Cliente.objects.create(rut="77777777-7", razon_social="Colegio Uno")
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(rut="77777777-7", razon_social="Colegio Dos")

    def test_el_modelo_rechaza_un_rut_invalido_al_validarse(self) -> None:
        cliente = Cliente(rut="76.543.210-9", razon_social="Colegio Demo")
        with self.assertRaises(ValidationError):
            cliente.full_clean()
