"""
tests/test_search.py
---------------------
Tests for the "pure" functions of search.py: the ones that don't need
to call Ollama (tokenization, stemming, lexical boost, spellcheck,
negation).

Run with:
    python -m unittest discover -s tests
or, if you have pytest installed:
    pytest tests/
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

# Allows importing search.py from the project's root folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import busqueda.buscador as search


# Small test catalog, independent of the real catalogo_dummy.csv, so
# tests run fast and don't depend on generated data.
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
    {
        "sku": "ROP-000003", "nombre": "Camiseta básica algodón manga corta verde oliva",
        "descripcion": "Camiseta de algodón 100% suave y transpirable.",
        "categoria_nivel1": "Ropa", "categoria_nivel2": "Hombre",
        "categoria_nivel3": "Camisetas", "categoria_nivel4": "Camiseta manga corta",
        "precio": "5.83", "stock": "Yes", "descuento": "0", "marca": "TelaViva",
    },
    {
        "sku": "ROP-000004", "nombre": "Camiseta básica algodón manga corta blanca",
        "descripcion": "Camiseta de algodón 100% suave y transpirable.",
        "categoria_nivel1": "Ropa", "categoria_nivel2": "Hombre",
        "categoria_nivel3": "Camisetas", "categoria_nivel4": "Camiseta manga corta",
        "precio": "9.99", "stock": "Yes", "descuento": "0", "marca": "UrbanCotto",
    },
]


class TestTokenizar(unittest.TestCase):

    def test_ignora_stopwords(self):
        palabras = search.tokenizar("un collar de la marca")
        self.assertNotIn("de", palabras)
        self.assertNotIn("la", palabras)
        self.assertNotIn("un", palabras)

    def test_conserva_con_y_sin(self):
        # "con" and "sin" must be kept: they can be part of a real
        # product name (e.g. "sudadera con capucha").
        palabras = search.tokenizar("sudadera con capucha")
        self.assertIn("con", palabras)

        palabras2 = search.tokenizar("sudadera sin capucha")
        self.assertIn("sin", palabras2)

    def test_palabras_cortas_con_significado_se_conservan(self):
        # "aro" (3 letters) must not be dropped just for being short.
        palabras = search.tokenizar("pendientes de aro")
        self.assertIn("aro", palabras)

    def test_ignora_tildes(self):
        # "joyeria" (no accent) must match "Joyería" (with accent).
        self.assertEqual(search.tokenizar("joyeria"), search.tokenizar("Joyería"))

    def test_no_confunde_enie_con_vocal_acentuada(self):
        # "ñ" is a letter in its own right in Spanish, not an accented
        # vowel: "año" and "ano" must remain different words.
        self.assertNotEqual(search.tokenizar("año"), search.tokenizar("ano"))


class TestNormalizarUnidades(unittest.TestCase):

    def test_variantes_de_gramos_coinciden(self):
        self.assertEqual(search.tokenizar("250gr"), search.tokenizar("250g"))
        self.assertEqual(search.tokenizar("250gr"), search.tokenizar("250 gr"))
        self.assertEqual(search.tokenizar("250gr"), search.tokenizar("250 gramos"))

    def test_variantes_de_litros_coinciden(self):
        self.assertEqual(search.tokenizar("10l"), search.tokenizar("10L"))
        self.assertEqual(search.tokenizar("10l"), search.tokenizar("10 litros"))

    def test_variantes_de_miligramos_coinciden(self):
        self.assertEqual(search.tokenizar("600mg"), search.tokenizar("600 mg"))
        self.assertEqual(search.tokenizar("600mg"), search.tokenizar("600 miligramos"))

    def test_variantes_de_microgramos_coinciden(self):
        self.assertEqual(search.tokenizar("25mcg"), search.tokenizar("25 mcg"))
        self.assertEqual(search.tokenizar("25mcg"), search.tokenizar("25 microgramos"))

    def test_decimales_con_coma_o_punto_coinciden(self):
        self.assertEqual(search.tokenizar("0.25kg"), search.tokenizar("0,25kg"))

    def test_cantidades_distintas_no_coinciden(self):
        self.assertNotEqual(search.tokenizar("250g"), search.tokenizar("500g"))
        self.assertNotEqual(search.tokenizar("250g"), search.tokenizar("250kg"))


class TestStemming(unittest.TestCase):

    def test_plural_simple(self):
        self.assertIn("aro", search.variantes_stem("aros"))

    def test_plural_con_es(self):
        self.assertIn("reloj", search.variantes_stem("relojes"))

    def test_plural_ces_a_z(self):
        self.assertIn("luz", search.variantes_stem("luces"))

    def test_palabra_corta_no_se_toca(self):
        # Very short words shouldn't produce aggressive variants
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
        # "cena" is a valid Spanish word that has nothing to do with
        # the catalog: it shouldn't be "corrected" into something else.
        corregida, cambio = search.corregir_query("cena mejicana", self.vocabulario)
        self.assertFalse(cambio)
        self.assertEqual(corregida, "cena mejicana")

    def test_vocabulario_no_incluye_artefactos_del_stemmer(self):
        # Regression test for a real bug: tokenizar("relojes") expands
        # to {"relojes", "reloje", "reloj"} for MATCHING purposes, but
        # "reloje" isn't a real word — it's just an intermediate stem
        # candidate. The spellcheck vocabulary must never include it,
        # or it could end up "correcting" a query into a non-word.
        vocab = search.build_vocabulary([{"nombre": "Reloj de pulsera clásico"}])
        self.assertIn("reloj", vocab)
        self.assertNotIn("reloje", vocab)

    def test_no_corrige_hacia_una_palabra_que_no_existe(self):
        # Regression test: before the fix, "relojs de pulsera" was
        # "corrected" to "reloje de pulsera" — a synthetic stem that
        # doesn't match "Reloj de pulsera clásico" at all, making the
        # search WORSE than not correcting anything.
        vocab = search.build_vocabulary([{"nombre": "Reloj de pulsera clásico"}])
        corregida, cambio = search.corregir_query("relojs de pulsera", vocab)
        self.assertNotIn("reloje", corregida)


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
        self.assertTrue(search.producto_excluido(CATALOGO_PRUEBA[0], excluir))  # hoop earrings
        self.assertFalse(search.producto_excluido(CATALOGO_PRUEBA[1], excluir))  # pearl earrings

    def test_negacion_con_no_excluye_color(self):
        # "no" is the case PyYAML 1.1 turns into False when unquoted in
        # config.yaml: the query must exclude green, not search for it.
        query_positiva, excluir = search.extraer_exclusiones(
            "camiseta no verde", CATALOGO_PRUEBA
        )
        self.assertEqual(query_positiva, "camiseta")
        self.assertIn("verde", excluir)
        camiseta_verde = next(p for p in CATALOGO_PRUEBA if p["sku"] == "ROP-000003")
        camiseta_blanca = next(p for p in CATALOGO_PRUEBA if p["sku"] == "ROP-000004")
        self.assertTrue(search.producto_excluido(camiseta_verde, excluir))
        self.assertFalse(search.producto_excluido(camiseta_blanca, excluir))

    def test_frase_establecida_reconoce_acentos(self):
        # Regression test for a real bug: frase_establecida() compared
        # the query (accent-stripped) against the raw catalog name
        # (never accent-stripped). "café sin cafeína" (an accented
        # product name) failed to be recognized as an established
        # phrase, so "cafeina" was wrongly treated as a term to
        # exclude — the opposite of what the user meant.
        catalogo_con_acento = [{"nombre": "Café sin cafeína natural"}]
        query_positiva, excluir = search.extraer_exclusiones(
            "cafe sin cafeina", catalogo_con_acento
        )
        self.assertEqual(query_positiva, "cafe sin cafeina")
        self.assertEqual(excluir, set())


class TestBuscarRankingDosNiveles(unittest.TestCase):
    """
    Verifies that a lexical match always ranks before a purely semantic
    one, without needing to actually call Ollama.
    """

    def setUp(self):
        import numpy as np
        self.np = np
        # Replace embed_query with a fake, deterministic version, so we
        # don't depend on Ollama being installed and running.
        self._embed_original = search.embed_query
        search.embed_query = lambda query: np.ones(4, dtype=np.float32)

    def tearDown(self):
        search.embed_query = self._embed_original

    def test_lexico_siempre_antes_que_semantico(self):
        np = self.np
        vectors = np.array([
            [1.0, 0.0, 0.0, 0.0],  # product 0: no semantic relation at all
            [1.0, 1.0, 1.0, 1.0],  # product 1: very similar semantically
        ], dtype=np.float32)
        meta = [
            CATALOGO_PRUEBA[4],  # "Robot aspirador wifi" (no lexical relation to "aro")
            CATALOGO_PRUEBA[0],  # "Pendientes de aro minimalistas" (lexical match)
        ]

        ranked, hay_match = search.buscar("aro", vectors, meta, search.PESOS_DEFECTO)

        self.assertTrue(hay_match)
        # The first result must be the one with a lexical match, even
        # though the other one has higher raw semantic similarity.
        primer_resultado = ranked[0]
        self.assertEqual(primer_resultado[2]["sku"], "JOY-000001")


class TestAvisoBajaConfianza(unittest.TestCase):
    """
    End-to-end tests (via main()) for the "no clear match" disclaimer:
    when there's no lexical match at all AND the best semantic score
    is weak, search.py should say so explicitly instead of presenting
    mediocre results as if they were confident matches.
    """

    def setUp(self):
        self._embed_original = search.embed_query
        self._tmpdir = tempfile.mkdtemp()
        self._prefix = str(Path(self._tmpdir) / "idx")

        catalogo = [{
            "sku": "ROP-000001", "nombre": "Camiseta básica",
            "descripcion": "Camiseta de algodón suave.", "categoria_nivel1": "Ropa",
            "categoria_nivel2": "", "categoria_nivel3": "", "categoria_nivel4": "",
            "precio": "10.00", "stock": "Yes", "descuento": "0", "marca": "TelaViva",
        }]
        vectors = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        np.save(f"{self._prefix}_vectors.npy", vectors)
        with open(f"{self._prefix}_meta.json", "w", encoding="utf-8") as f:
            json.dump(catalogo, f)

    def tearDown(self):
        search.embed_query = self._embed_original
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _ejecutar_main(self, query, vector_query):
        # "zapatillas deportivas" shares no word at all with "Camiseta
        # básica de algodón" (no lexical match either way) — only the
        # mocked embedding vector controls the semantic similarity,
        # isolating exactly what we want to test.
        search.embed_query = lambda q: np.array(vector_query, dtype=np.float32)
        argv_original = sys.argv
        sys.argv = [
            "search.py", "--index", self._prefix, "--query", query,
            "--intencion", "producto",
        ]
        salida = io.StringIO()
        try:
            with redirect_stdout(salida):
                search.main()
        finally:
            sys.argv = argv_original
        return salida.getvalue()

    def test_muestra_aviso_si_la_similitud_es_baja(self):
        salida = self._ejecutar_main("zapatillas deportivas", [0.0, 1.0, 0.0, 0.0])
        self.assertIn("No encontramos ninguna coincidencia clara", salida)

    def test_no_muestra_aviso_si_la_similitud_es_alta(self):
        salida = self._ejecutar_main("zapatillas deportivas", [0.99, 0.01, 0.0, 0.0])
        self.assertNotIn("No encontramos ninguna coincidencia clara", salida)
        self.assertIn("Resultados para", salida)


if __name__ == "__main__":
    unittest.main()
