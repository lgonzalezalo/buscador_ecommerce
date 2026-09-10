"""
tests/test_search.py
---------------------
Tests de las funciones "puras" de search.py: las que no necesitan llamar
a Ollama (tokenización, stemming, boost léxico, spellcheck, negación).

Ejecutar con:
    python -m unittest discover -s tests
o, si tienes pytest instalado:
    pytest tests/
"""

import sys
import unittest
from pathlib import Path

# Permite importar search.py desde la carpeta raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import search


# Catálogo pequeño de prueba, independiente del catalogo_dummy.csv real,
# para que los tests sean rápidos y no dependan de datos generados.
CATALOGO_PRUEBA = [
    {
        "sku": "JOY-000001", "nombre": "Pendientes de aro minimalistas",
        "descripcion": "Pendientes ligeros de plata.",
        "categoria_nivel1": "Joyería", "categoria_nivel2": "Pendientes",
        "categoria_nivel3": "Pendientes de plata", "categoria_nivel4": "Pendientes de aro",
        "precio": "25.00", "stock": "Yes", "descuento": "0", "marca": "Aurea Diseño",
    },
    {
        "sku": "JOY-000002", "nombre": "Pendientes de perla blanca",
        "descripcion": "Pendientes elegantes con perla natural.",
        "categoria_nivel1": "Joyería", "categoria_nivel2": "Pendientes",
        "categoria_nivel3": "Pendientes de perla", "categoria_nivel4": "Pendientes de perla",
        "precio": "40.00", "stock": "Yes", "descuento": "0", "marca": "Lumina Joyas",
    },
    {
        "sku": "ROP-000001", "nombre": "Sudadera con capucha negra",
        "descripcion": "Sudadera cómoda con capucha y bolsillo canguro.",
        "categoria_nivel1": "Ropa", "categoria_nivel2": "Mujer",
        "categoria_nivel3": "Sudaderas", "categoria_nivel4": "Sudadera con capucha",
        "precio": "35.00", "stock": "Yes", "descuento": "20", "marca": "SolTejido",
    },
    {
        "sku": "ROP-000002", "nombre": "Sudadera sin capucha básica",
        "descripcion": "Sudadera básica sin capucha, cómoda y versátil.",
        "categoria_nivel1": "Ropa", "categoria_nivel2": "Mujer",
        "categoria_nivel3": "Sudaderas", "categoria_nivel4": "Sudadera sin capucha",
        "precio": "28.00", "stock": "No", "descuento": "0", "marca": "NordVía",
    },
    {
        "sku": "ELE-000001", "nombre": "Robot aspirador wifi",
        "descripcion": "Robot inteligente que limpia de forma autónoma.",
        "categoria_nivel1": "Electrodomésticos", "categoria_nivel2": "Limpieza",
        "categoria_nivel3": "Robots aspiradores", "categoria_nivel4": "Robot aspirador",
        "precio": "250.00", "stock": "Yes", "descuento": "10", "marca": "HogarTech",
    },
]


class TestTokenizar(unittest.TestCase):

    def test_ignora_stopwords(self):
        palabras = search.tokenizar("un collar de la marca")
        self.assertNotIn("de", palabras)
        self.assertNotIn("la", palabras)
        self.assertNotIn("un", palabras)

    def test_conserva_con_y_sin(self):
        # "con" y "sin" deben conservarse: pueden ser parte de un nombre
        # de producto real (ej. "sudadera con capucha").
        palabras = search.tokenizar("sudadera con capucha")
        self.assertIn("con", palabras)

        palabras2 = search.tokenizar("sudadera sin capucha")
        self.assertIn("sin", palabras2)

    def test_palabras_cortas_con_significado_se_conservan(self):
        # "aro" (3 letras) no debe perderse por ser corta.
        palabras = search.tokenizar("pendientes de aro")
        self.assertIn("aro", palabras)


class TestStemming(unittest.TestCase):

    def test_plural_simple(self):
        self.assertIn("aro", search.variantes_stem("aros"))

    def test_plural_con_es(self):
        self.assertIn("reloj", search.variantes_stem("relojes"))

    def test_plural_ces_a_z(self):
        self.assertIn("luz", search.variantes_stem("luces"))

    def test_palabra_corta_no_se_toca(self):
        # Palabras muy cortas no deberían generar variantes agresivas
        variantes = search.variantes_stem("mes")
        self.assertEqual(variantes, {"mes"})


class TestLexicalScore(unittest.TestCase):

    def test_coincidencia_en_nombre_pesa_mas_que_categoria(self):
        pesos = {"nombre": 1.0, "descripcion": 0.5, "categoria": 0.3}
        producto = CATALOGO_PRUEBA[0]  # "Pendientes de aro minimalistas"

        score_nombre = search.lexical_score({"minimalistas"}, producto, pesos)
        score_categoria_only = search.lexical_score({"joyeria"}, producto, pesos)

        self.assertGreater(score_nombre, score_categoria_only)

    def test_sin_coincidencia_da_cero(self):
        pesos = search.PESOS_DEFECTO
        producto = CATALOGO_PRUEBA[0]
        score = search.lexical_score({"nevera"}, producto, pesos)
        self.assertEqual(score, 0.0)

    def test_distingue_con_capucha_de_sin_capucha(self):
        pesos = search.PESOS_DEFECTO
        con_capucha = CATALOGO_PRUEBA[2]
        sin_capucha = CATALOGO_PRUEBA[3]

        query_con = search.tokenizar("sudadera con capucha")
        score_en_con = search.lexical_score(query_con, con_capucha, pesos)
        score_en_sin = search.lexical_score(query_con, sin_capucha, pesos)

        self.assertGreater(score_en_con, score_en_sin)


class TestVocabularioYSpellcheck(unittest.TestCase):

    def setUp(self):
        self.vocabulario = search.build_vocabulary(CATALOGO_PRUEBA)

    def test_palabra_real_del_catalogo_esta_en_vocabulario(self):
        self.assertIn("pendientes", self.vocabulario)
        self.assertIn("aro", self.vocabulario)

    def test_corrige_typo_real(self):
        corregida, cambio = search.corregir_query("sudadera con capuha", self.vocabulario)
        self.assertTrue(cambio)
        self.assertIn("capucha", corregida)

    def test_no_corrige_palabra_valida_fuera_de_catalogo(self):
        # "cena" es una palabra española válida que no tiene nada que ver
        # con el catálogo: no debería "corregirse" a otra cosa.
        corregida, cambio = search.corregir_query("cena mejicana", self.vocabulario)
        self.assertFalse(cambio)
        self.assertEqual(corregida, "cena mejicana")


class TestNegacion(unittest.TestCase):

    def test_frase_establecida_se_mantiene_positiva(self):
        query_positiva, excluir = search.extraer_exclusiones(
            "sudadera sin capucha", CATALOGO_PRUEBA
        )
        self.assertEqual(query_positiva, "sudadera sin capucha")
        self.assertEqual(excluir, set())

    def test_negacion_generica_excluye(self):
        query_positiva, excluir = search.extraer_exclusiones(
            "pendientes sin aros", CATALOGO_PRUEBA
        )
        self.assertEqual(query_positiva, "pendientes")
        self.assertIn("aro", excluir)

    def test_producto_excluido_correctamente(self):
        _, excluir = search.extraer_exclusiones("pendientes sin aros", CATALOGO_PRUEBA)
        self.assertTrue(search.producto_excluido(CATALOGO_PRUEBA[0], excluir))  # pendientes de aro
        self.assertFalse(search.producto_excluido(CATALOGO_PRUEBA[1], excluir))  # pendientes de perla


class TestBuscarRankingDosNiveles(unittest.TestCase):
    """
    Valida que un match léxico siempre sale antes que uno puramente
    semántico, sin necesidad de llamar a Ollama de verdad.
    """

    def setUp(self):
        import numpy as np
        self.np = np
        # Sustituimos embed_query por una versión falsa y determinista,
        # para no depender de que Ollama esté instalado y corriendo.
        self._embed_original = search.embed_query
        search.embed_query = lambda query: np.ones(4, dtype=np.float32)

    def tearDown(self):
        search.embed_query = self._embed_original

    def test_lexico_siempre_antes_que_semantico(self):
        np = self.np
        vectors = np.array([
            [1.0, 0.0, 0.0, 0.0],  # producto 0: nada que ver semánticamente
            [1.0, 1.0, 1.0, 1.0],  # producto 1: muy parecido semánticamente
        ], dtype=np.float32)
        meta = [
            CATALOGO_PRUEBA[4],  # "Robot aspirador wifi" (sin relación léxica con "aro")
            CATALOGO_PRUEBA[0],  # "Pendientes de aro minimalistas" (coincide léxicamente)
        ]

        ranked, hay_match = search.buscar("aro", vectors, meta, search.PESOS_DEFECTO)

        self.assertTrue(hay_match)
        # El primer resultado debe ser el que tiene coincidencia léxica,
        # aunque el otro tenga mayor similitud semántica bruta.
        primer_resultado = ranked[0]
        self.assertEqual(primer_resultado[2]["sku"], "JOY-000001")


if __name__ == "__main__":
    unittest.main()
