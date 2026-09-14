"""
tests/test_build_index.py
---------------------------
Tests for build_index.py's functions: mainly automatic CSV delimiter
detection (",", ";"), which was a real issue found during development.

Run with:
    python -m unittest discover -s tests
"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_index


FILAS_PRUEBA = [
    {
        "sku": "JOY-000001", "nombre": "Anillo de plata",
        "descripcion": "Anillo elegante y minimalista.",
        "categoria_nivel1": "Joyería", "categoria_nivel2": "Anillos",
        "categoria_nivel3": "Anillos de plata", "categoria_nivel4": "Anillo ajustable",
        "precio": "30.00", "stock": "Yes", "descuento": "0", "marca": "Plata del Norte",
    },
]

COLUMNAS = list(FILAS_PRUEBA[0].keys())


def _escribir_csv_temporal(delimiter: str) -> str:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
    )
    writer = csv.DictWriter(tmp, fieldnames=COLUMNAS, delimiter=delimiter)
    writer.writeheader()
    writer.writerows(FILAS_PRUEBA)
    tmp.close()
    return tmp.name


class TestLoadCatalogDelimiter(unittest.TestCase):

    def test_detecta_separador_coma(self):
        path = _escribir_csv_temporal(",")
        try:
            filas = build_index.load_catalog(path)
            self.assertEqual(len(filas), 1)
            self.assertEqual(filas[0]["sku"], "JOY-000001")
        finally:
            Path(path).unlink()

    def test_detecta_separador_punto_y_coma(self):
        # This is the real case that caused problems: a CSV saved from
        # Excel under a Spanish/European locale uses ";".
        path = _escribir_csv_temporal(";")
        try:
            filas = build_index.load_catalog(path)
            self.assertEqual(len(filas), 1)
            self.assertEqual(filas[0]["nombre"], "Anillo de plata")
        finally:
            Path(path).unlink()


class TestBuildText(unittest.TestCase):

    def test_incluye_ruta_completa_de_categoria(self):
        texto = build_index.build_text(FILAS_PRUEBA[0])
        self.assertIn("Joyería", texto)
        self.assertIn("Anillo ajustable", texto)

    def test_incluye_nombre_y_marca(self):
        texto = build_index.build_text(FILAS_PRUEBA[0])
        self.assertIn("Anillo de plata", texto)
        self.assertIn("Plata del Norte", texto)


if __name__ == "__main__":
    unittest.main()
