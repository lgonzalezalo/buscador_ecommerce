"""
tests/test_robustez.py
------------------------
Tests for the audit fixes that don't fit cleanly into an existing
test file: custom exceptions instead of sys.exit() in library code,
safe numeric conversion, index integrity checking, concurrent
embedding batching, and the pharmacy generator's target-row warning.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import indexado.indice as indice
import busqueda.buscador as search
from faq.faq import cargar_faq, FaqNoEncontradaError


class TestNumeroSeguro(unittest.TestCase):

    def test_convierte_valores_normales(self):
        self.assertEqual(search._numero_seguro("12.50", float), 12.5)
        self.assertEqual(search._numero_seguro("10", int), 10)

    def test_cadena_vacia_usa_el_defecto(self):
        self.assertEqual(search._numero_seguro("", float), 0)
        self.assertEqual(search._numero_seguro("", int, defecto=-1), -1)

    def test_entero_con_formato_decimal(self):
        # A discount column written as "10.0" instead of a clean "10"
        # shouldn't crash int() — this is the real case from the audit.
        self.assertEqual(search._numero_seguro("10.0", int), 10)

    def test_valor_none_usa_el_defecto(self):
        self.assertEqual(search._numero_seguro(None, float, defecto=5.0), 5.0)


class TestExcepcionesEnVezDeSysExit(unittest.TestCase):
    """
    Regression tests: library functions must raise exceptions, never
    call sys.exit() themselves — otherwise a single bad request kills
    the whole process, not just the operation that failed.
    """

    def test_load_index_lanza_excepcion_si_no_existe(self):
        with self.assertRaises(indice.IndiceNoEncontradoError):
            indice.load_index("/ruta/que/no/existe/idx")

    def test_load_index_lanza_excepcion_si_esta_corrupto(self):
        tmpdir = tempfile.mkdtemp()
        prefix = str(Path(tmpdir) / "idx")
        np.save(f"{prefix}_vectors.npy", np.zeros((3, 4)))
        with open(f"{prefix}_meta.json", "w", encoding="utf-8") as f:
            json.dump([{"sku": "A"}], f)  # only 1 entry, but 3 vectors

        with self.assertRaises(indice.IndiceCorruptoError):
            indice.load_index(prefix)

    def test_cargar_faq_lanza_excepcion_si_no_existe(self):
        with self.assertRaises(FaqNoEncontradaError):
            cargar_faq("/ruta/que/no/existe.csv")


class TestEmbedBatch(unittest.TestCase):
    """
    embed_batch() runs requests concurrently, but must still return
    results in the SAME ORDER as the input texts, regardless of which
    request happens to finish first.
    """

    def setUp(self):
        self._embed_original = indice.embed_query

    def tearDown(self):
        indice.embed_query = self._embed_original

    def test_devuelve_vectores_en_el_orden_de_entrada(self):
        # Simulate requests finishing out of order: "lento" takes
        # longer than "rapido", but must still land in its own
        # original position in the result list.
        import time

        def fake_embed_query(texto):
            if texto == "lento":
                time.sleep(0.05)
                return np.array([1.0, 0.0], dtype=np.float32)
            return np.array([0.0, 1.0], dtype=np.float32)

        indice.embed_query = fake_embed_query

        textos = ["lento", "rapido", "rapido", "lento"]
        resultados = indice.embed_batch(textos, hilos=4)

        self.assertEqual(len(resultados), 4)
        np.testing.assert_array_equal(resultados[0], [1.0, 0.0])  # "lento"
        np.testing.assert_array_equal(resultados[1], [0.0, 1.0])  # "rapido"
        np.testing.assert_array_equal(resultados[2], [0.0, 1.0])  # "rapido"
        np.testing.assert_array_equal(resultados[3], [1.0, 0.0])  # "lento"

    def test_reporta_progreso_por_cada_texto_completado(self):
        indice.embed_query = lambda texto: np.zeros(2, dtype=np.float32)
        progresos = []
        indice.embed_batch(["a", "b", "c"], hilos=2, on_progreso=progresos.append)
        # Called once per completed text, ending at the total count.
        self.assertEqual(len(progresos), 3)
        self.assertEqual(max(progresos), 3)


class TestBuscarConEmbeddingReutilizado(unittest.TestCase):
    """
    Passing a precomputed query_vec to buscar() must give the exact
    same ranking as letting it compute the embedding itself — the
    optimization must be invisible to the result, only to how many
    times Ollama gets called.
    """

    def test_mismo_resultado_con_o_sin_query_vec_precalculado(self):
        vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        meta = [{"nombre": "Producto A"}, {"nombre": "Producto B"}]
        pesos = {"nombre": 1.0, "descripcion": 0.5, "categoria": 0.3}
        query_vec = np.array([0.9, 0.1], dtype=np.float32)

        original = search.embed_query
        try:
            search.embed_query = lambda q: query_vec  # would give the same vector anyway
            ranked_sin, _ = search.buscar("zzz", vectors, meta, pesos)
            ranked_con, _ = search.buscar("zzz", vectors, meta, pesos, query_vec=query_vec)
        finally:
            search.embed_query = original

        skus_sin = [r[2]["nombre"] for r in ranked_sin]
        skus_con = [r[2]["nombre"] for r in ranked_con]
        self.assertEqual(skus_sin, skus_con)


if __name__ == "__main__":
    unittest.main()
