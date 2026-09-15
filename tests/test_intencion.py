"""
tests/test_intencion.py
--------------------------
Tests for intencion.py: semantic (few-shot, nearest-neighbor) intent
classification. embed_query is replaced with a fake, deterministic
function so these tests don't need Ollama installed or running — they
validate the classification MECHANISM (pick the label of the closest
example), not the real-world semantic quality of bge-m3 itself, which
can only be confirmed by actually running it.
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import faq.intencion as intencion


class TestDetectarIntencionSemantica(unittest.TestCase):

    def setUp(self):
        self._embed_original = intencion.embed_query
        self._vectores_por_texto = {}

        def fake_embed_query(texto):
            return self._vectores_por_texto.get(texto, np.zeros(4, dtype=np.float32))

        intencion.embed_query = fake_embed_query

    def tearDown(self):
        intencion.embed_query = self._embed_original

    def _ejemplos_de_prueba(self):
        """
        A small, controlled example set with known vectors, independent
        of the module's real curated EJEMPLOS_PRODUCTO/EJEMPLOS_FAQ —
        this tests the classification mechanism itself, not the
        specific example wording.
        """
        ejemplos_producto = ["sudadera con capucha", "zapatillas running"]
        ejemplos_faq = ["cuanto tarda el envio", "quiero una devolucion"]

        self._vectores_por_texto["sudadera con capucha"] = np.array([1, 0, 0, 0], dtype=np.float32)
        self._vectores_por_texto["zapatillas running"] = np.array([0.9, 0.1, 0, 0], dtype=np.float32)
        self._vectores_por_texto["cuanto tarda el envio"] = np.array([0, 0, 1, 0], dtype=np.float32)
        self._vectores_por_texto["quiero una devolucion"] = np.array([0, 0, 0.9, 0.1], dtype=np.float32)

        textos = ejemplos_producto + ejemplos_faq
        etiquetas = (["producto"] * len(ejemplos_producto)) + (["faq"] * len(ejemplos_faq))
        vectores = np.array([self._vectores_por_texto[t] for t in textos], dtype=np.float32)
        return vectores, etiquetas

    def test_query_cercana_a_ejemplos_de_producto_gana_producto(self):
        vectores, etiquetas = self._ejemplos_de_prueba()
        self._vectores_por_texto["query de prueba"] = np.array([0.95, 0.05, 0, 0], dtype=np.float32)
        resultado = intencion.detectar_intencion("query de prueba", vectores, etiquetas)
        self.assertEqual(resultado, "producto")

    def test_query_cercana_a_ejemplos_de_faq_gana_faq(self):
        vectores, etiquetas = self._ejemplos_de_prueba()
        self._vectores_por_texto["query de prueba"] = np.array([0, 0, 0.95, 0.05], dtype=np.float32)
        resultado = intencion.detectar_intencion("query de prueba", vectores, etiquetas)
        self.assertEqual(resultado, "faq")

    def test_desempate_por_vecino_mas_cercano_no_por_grupo_completo(self):
        # Even if a query is only "reasonably" close to one FAQ example
        # but there are more product examples overall, the nearest
        # SINGLE example wins — this isn't majority voting.
        vectores, etiquetas = self._ejemplos_de_prueba()
        self._vectores_por_texto["query de prueba"] = np.array([0, 0, 0.99, 0.01], dtype=np.float32)
        resultado = intencion.detectar_intencion("query de prueba", vectores, etiquetas)
        self.assertEqual(resultado, "faq")


class TestConstruirEjemplosIntencion(unittest.TestCase):

    def setUp(self):
        self._embed_original = intencion.embed_query
        intencion.embed_query = lambda texto: np.ones(4, dtype=np.float32)

    def tearDown(self):
        intencion.embed_query = self._embed_original

    def test_devuelve_un_vector_y_una_etiqueta_por_ejemplo(self):
        vectores, etiquetas = intencion.construir_ejemplos_intencion()
        total_esperado = len(intencion.EJEMPLOS_PRODUCTO) + len(intencion.EJEMPLOS_FAQ)
        self.assertEqual(vectores.shape[0], total_esperado)
        self.assertEqual(len(etiquetas), total_esperado)

    def test_incluye_ambas_etiquetas(self):
        _, etiquetas = intencion.construir_ejemplos_intencion()
        self.assertIn("producto", etiquetas)
        self.assertIn("faq", etiquetas)


if __name__ == "__main__":
    unittest.main()
