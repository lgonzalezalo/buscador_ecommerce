"""
tests/test_variantes.py
-------------------------
Tests for variantes.py: grouping ranked results by parent product, and
attaching sibling variants pulled from the full catalog.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import busqueda.variantes as variantes


CATALOGO_CON_PADRES = [
    {"sku": "FAR-001", "nombre": "Farmalia Paracetamol 600mg 20 comprimidos",
     "producto_padre_id": "PADRE-01", "valor_variante": "600mg 20 comprimidos",
     "precio": "5.00", "stock": "Yes", "descuento": "0"},
    {"sku": "FAR-002", "nombre": "Farmalia Paracetamol 1g 12 comprimidos efervescentes",
     "producto_padre_id": "PADRE-01", "valor_variante": "1g 12 comprimidos efervescentes",
     "precio": "6.50", "stock": "No", "descuento": "0"},
    {"sku": "FAR-003", "nombre": "Farmalia Paracetamol 400mg 30 cápsulas",
     "producto_padre_id": "PADRE-01", "valor_variante": "400mg 30 cápsulas",
     "precio": "4.20", "stock": "Yes", "descuento": "10"},
    {"sku": "FAR-004", "nombre": "Vitaxel Ibuprofeno 400mg 30 cápsulas",
     "producto_padre_id": "PADRE-02", "valor_variante": "400mg 30 cápsulas",
     "precio": "7.00", "stock": "Yes", "descuento": "0"},
]

CATALOGO_SIN_PADRES = [
    {"sku": "ROP-001", "nombre": "Sudadera con capucha negra", "precio": "30.00", "stock": "Yes"},
    {"sku": "ROP-002", "nombre": "Sudadera sin capucha blanca", "precio": "25.00", "stock": "Yes"},
]


class TestObtenerPadreId(unittest.TestCase):

    def test_usa_producto_padre_id_si_existe(self):
        row = {"sku": "FAR-001", "producto_padre_id": "PADRE-01"}
        self.assertEqual(variantes.obtener_padre_id(row), "PADRE-01")

    def test_usa_sku_como_fallback_si_no_hay_padre_id(self):
        row = {"sku": "ROP-001"}
        self.assertEqual(variantes.obtener_padre_id(row), "ROP-001")


class TestAgruparPorPadre(unittest.TestCase):

    def test_colapsa_variantes_del_mismo_padre_en_un_grupo(self):
        ranked = [(1.0, 0.5, row) for row in CATALOGO_CON_PADRES]
        agrupado = variantes.agrupar_por_padre(ranked, CATALOGO_CON_PADRES)
        # 4 rows, 2 distinct parents -> 2 groups
        self.assertEqual(len(agrupado), 2)

    def test_mantiene_el_representante_de_mayor_ranking(self):
        # FAR-001 (PADRE-01) ranks first in 'ranked'; it must be the
        # representative for that group, not any of its siblings.
        ranked = [
            (2.0, 0.9, CATALOGO_CON_PADRES[0]),  # FAR-001, top-ranked
            (1.0, 0.5, CATALOGO_CON_PADRES[1]),  # FAR-002, sibling
            (1.0, 0.4, CATALOGO_CON_PADRES[2]),  # FAR-003, sibling
            (1.0, 0.3, CATALOGO_CON_PADRES[3]),  # FAR-004, other parent
        ]
        agrupado = variantes.agrupar_por_padre(ranked, CATALOGO_CON_PADRES)
        representante_grupo_1, hermanas_grupo_1 = agrupado[0][2], agrupado[0][3]
        self.assertEqual(representante_grupo_1["sku"], "FAR-001")
        self.assertEqual(len(hermanas_grupo_1), 2)

    def test_hermanas_incluyen_variantes_que_no_aparecieron_en_ranked(self):
        # Only FAR-001 matched the query (appears in 'ranked'), but its
        # siblings FAR-002/FAR-003 must still show up as "other
        # presentations", pulled from the full catalog.
        ranked = [(1.0, 0.5, CATALOGO_CON_PADRES[0])]
        agrupado = variantes.agrupar_por_padre(ranked, CATALOGO_CON_PADRES)
        _, _, _, hermanas = agrupado[0]
        skus_hermanas = {h["sku"] for h in hermanas}
        self.assertEqual(skus_hermanas, {"FAR-002", "FAR-003"})

    def test_hermanas_no_incluyen_al_propio_representante(self):
        ranked = [(1.0, 0.5, CATALOGO_CON_PADRES[0])]
        agrupado = variantes.agrupar_por_padre(ranked, CATALOGO_CON_PADRES)
        _, _, _, hermanas = agrupado[0]
        self.assertNotIn("FAR-001", {h["sku"] for h in hermanas})

    def test_catalogo_sin_padre_hijo_no_agrupa_nada(self):
        # Backward compatibility: a catalog without producto_padre_id
        # (like the general dummy catalog) must yield one group per row.
        ranked = [(1.0, 0.5, row) for row in CATALOGO_SIN_PADRES]
        agrupado = variantes.agrupar_por_padre(ranked, CATALOGO_SIN_PADRES)
        self.assertEqual(len(agrupado), len(CATALOGO_SIN_PADRES))
        for _, _, _, hermanas in agrupado:
            self.assertEqual(hermanas, [])


if __name__ == "__main__":
    unittest.main()
