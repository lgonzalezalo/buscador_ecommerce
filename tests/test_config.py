"""
tests/test_config.py
---------------------
PyYAML (YAML 1.1) parses no/yes/y/n/on/off as booleans. That breaks
config.yaml's word lists if they're left unquoted.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config.config as config


YAML_SIN_COMILLAS = """
tokenizacion:
  stopwords:
    - y
    - de
  negadores:
    - sin
    - no
"""


class TestCargarConfigYaml11(unittest.TestCase):

    def test_config_real_guarda_no_e_y_como_texto(self):
        cargada = config.cargar_config()
        negadores = cargada["tokenizacion"]["negadores"]
        stopwords = cargada["tokenizacion"]["stopwords"]
        self.assertIn("no", negadores)
        self.assertIn("y", stopwords)
        self.assertTrue(all(isinstance(p, str) for p in negadores))
        self.assertTrue(all(isinstance(p, str) for p in stopwords))

    def test_no_e_y_sin_comillas_siguen_siendo_texto(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        tmp.write(YAML_SIN_COMILLAS)
        tmp.close()
        try:
            cargada = config.cargar_config(tmp.name)
            self.assertEqual(cargada["tokenizacion"]["negadores"], ["sin", "no"])
            self.assertIn("y", cargada["tokenizacion"]["stopwords"])
            self.assertNotIn(False, cargada["tokenizacion"]["negadores"])
            self.assertNotIn(True, cargada["tokenizacion"]["stopwords"])
        finally:
            Path(tmp.name).unlink()
