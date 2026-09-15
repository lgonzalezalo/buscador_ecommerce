"""
tests/test_faq.py
-------------------
Tests for faq.py: retrieval-only RAG over the FAQ dataset. The
embedding calls are replaced with a fake, deterministic function so
these tests don't need Ollama installed or running.

Intent detection tests live separately in tests/test_intencion.py.
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import faq.faq as faq


FAQ_PRUEBA = [
    {"id": "1", "pregunta": "¿Cuánto tarda el envío?",
     "respuesta": "24-48 horas laborables en península."},
    {"id": "2", "pregunta": "¿Puedo devolver un producto?",
     "respuesta": "Tienes 30 días naturales para devolverlo."},
    {"id": "3", "pregunta": "¿Qué métodos de pago aceptáis?",
     "respuesta": "Tarjeta, PayPal, Bizum y transferencia."},
]


class TestRAGRetrieval(unittest.TestCase):
    """
    Validates the retrieval mechanics (embed -> compare -> pick best)
    without depending on Ollama: embed_query is replaced with a fake
    that returns a fixed, known vector per text, so we can assert
    exactly which entry should win.
    """

    def setUp(self):
        self._embed_original = faq.embed_query
        self._vectores_por_texto = {}

        def fake_embed_query(texto):
            return self._vectores_por_texto.get(texto, np.zeros(4, dtype=np.float32))

        faq.embed_query = fake_embed_query

    def tearDown(self):
        faq.embed_query = self._embed_original

    def test_responder_faq_elige_la_entrada_mas_similar(self):
        # Build FAQ vectors deterministically: entry 0 -> [1,0,0,0],
        # entry 1 -> [0,1,0,0], entry 2 -> [0,0,1,0].
        textos_faq = [f"{item['pregunta']} {item['respuesta']}" for item in FAQ_PRUEBA]
        vectores_faq = [
            np.array([1, 0, 0, 0], dtype=np.float32),
            np.array([0, 1, 0, 0], dtype=np.float32),
            np.array([0, 0, 1, 0], dtype=np.float32),
        ]
        for texto, vector in zip(textos_faq, vectores_faq):
            self._vectores_por_texto[texto] = vector
        faq_vectors = np.array(vectores_faq, dtype=np.float32)

        # The query embeds identically to entry 1 ("devoluciones") ->
        # it must win, regardless of catalog order.
        self._vectores_por_texto["quiero devolver algo"] = np.array(
            [0, 1, 0, 0], dtype=np.float32
        )

        mejor, similitud = faq.responder_faq("quiero devolver algo", FAQ_PRUEBA, faq_vectors)
        self.assertEqual(mejor["id"], "2")
        self.assertAlmostEqual(similitud, 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
