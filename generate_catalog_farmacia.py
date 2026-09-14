"""
generate_catalog_farmacia.py (v2 — con relación padre-hijo)
----------------------------------------------------------------
Same output schema as v1, PLUS three new columns that model the
parent-child relationship between product variants:

    producto_padre_id  -> shared by all variants of the same base product
    tipo_variante       -> what varies between siblings (always "presentacion" here)
    valor_variante       -> the actual variant value (e.g. "600mg 20 comprimidos")

A "parent" is a (generic product type, marca) combination — e.g.
"Farmalia Paracetamol" — and its "children" are the different
dose/format/pack-size presentations of that exact same product, sold
by that exact same brand. Price, stock, and discount are independent
per variant (realistic: different pack sizes have different prices and
stock levels), but marca, descripcion, and category are shared across
all children of the same parent — that's the whole point of modeling
it this way instead of generating 5000 unrelated rows.

This is backward-compatible with build_index.py / search.py: they only
require the "sku" and "nombre" columns, so the extra columns are simply
ignored by the current code. They exist here as the data foundation for
a future "group variants under one product card" feature.

Usage:
    python generate_catalog_farmacia.py --output catalogo_farmacia.csv
"""

import argparse
import csv
import random

random.seed(7)

CATEGORIA_NIVEL1 = "Farmacia"
FILAS_OBJETIVO = 5000

MARCAS = [
    "Farmalia", "Vitaxel", "Bruma Salud", "Norvital", "PuntoFarma",
    "Bienestar Plus", "Farmoderma", "Salutia", "Vitalnova", "Cronos Pharma",
    "Aliviax", "Botica Real", "MediCare Plus", "Herbolar", "Nortfarma",
]

# ---------------------------------------------------------------------------
# Taxonomy: nivel2 -> list of nivel3 entries. Each entry now has a list of
# "conceptos" (generic product types, e.g. active-ingredient-style names or
# fictitious product-line names) INSTEAD OF a single brand-like name. Each
# (concepto, marca) combination becomes one PARENT product; each string in
# "variantes" becomes one CHILD (a specific presentation) of that parent.
# ---------------------------------------------------------------------------
TAXONOMIA = {
    "Medicamentos sin receta": [
        ("Analgésicos", "Analgésico oral",
         ["Paracetamol", "Ibuprofeno", "Ácido acetilsalicílico", "Naproxeno", "Metamizol"],
         ["600mg 20 comprimidos", "1g 12 comprimidos efervescentes",
          "400mg 30 cápsulas", "500mg 16 comprimidos recubiertos", "650mg 10 sobres"],
         "Alivia el dolor leve a moderado y reduce la fiebre."),
        ("Antitusivos", "Jarabe para la tos",
         ["Jarabe balsámico", "Jarabe expectorante", "Jarabe seco", "Jarabe pectoral"],
         ["120ml", "200ml", "infantil 100ml", "sin azúcar 150ml"],
         "Calma la tos seca e irritativa."),
        ("Antiácidos", "Antiácido oral",
         ["Almagato", "Magaldrato", "Bicarbonato", "Omeprazol"],
         ["20 comprimidos masticables", "30 comprimidos masticables",
          "sobres 250ml", "suspensión oral 200ml"],
         "Neutraliza el exceso de ácido estomacal."),
        ("Antihistamínicos", "Antihistamínico oral",
         ["Loratadina", "Cetirizina", "Difenhidramina", "Ebastina"],
         ["10mg 20 comprimidos", "10mg 10 comprimidos", "jarabe 150ml", "gotas 20ml"],
         "Alivia los síntomas de alergia como estornudos y picor."),
        ("Descongestionantes", "Spray nasal",
         ["Suero fisiológico", "Xilometazolina", "Agua de mar", "Oximetazolina"],
         ["spray 15ml", "spray 20ml", "infantil spray 15ml", "solución salina 100ml"],
         "Descongestiona la nariz y facilita la respiración."),
    ],
    "Vitaminas y suplementos": [
        ("Vitamina C", "Vitamina C efervescente",
         ["Vitamina C", "Vitamina C con zinc", "Vitamina C liposomal", "Vitamina C forte"],
         ["1000mg 20 comprimidos efervescentes", "500mg 30 comprimidos",
          "1000mg 10 sobres", "goma de mascar 60 unidades"],
         "Refuerza las defensas y contribuye al sistema inmunitario."),
        ("Multivitamínicos", "Complejo multivitamínico",
         ["Multivitamínico adultos", "Multivitamínico senior", "Multivitamínico mujer",
          "Multivitamínico deportistas"],
         ["30 comprimidos", "60 cápsulas", "24 comprimidos masticables", "gotas 30ml"],
         "Complemento alimenticio con vitaminas y minerales esenciales."),
        ("Magnesio", "Magnesio en comprimidos",
         ["Magnesio", "Magnesio con vitamina B6", "Magnesio marino", "Magnesio bisglicinato"],
         ["500mg 60 comprimidos", "300mg 30 comprimidos", "sobres 20 unidades"],
         "Contribuye al funcionamiento normal muscular y nervioso."),
        ("Vitamina D", "Vitamina D en gotas",
         ["Vitamina D3", "Vitamina D3 + K2", "Vitamina D infantil"],
         ["25mcg 30 cápsulas", "2000ui gotas 15ml", "400ui gotas infantil 10ml", "1000ui 30 comprimidos"],
         "Contribuye a la absorción normal de calcio y al sistema inmunitario."),
    ],
    "Cuidado personal": [
        ("Cremas hidratantes", "Crema corporal",
         ["Hidratante clásica", "Hidratante intensiva", "Hidratante piel atópica",
          "Hidratante urea"],
         ["crema 200ml", "crema 400ml", "loción 250ml", "crema intensiva 100ml"],
         "Hidrata y nutre la piel seca en profundidad."),
        ("Protección solar", "Protector solar",
         ["Solar corporal", "Solar facial", "Solar infantil", "Solar deportistas"],
         ["SPF50 200ml", "SPF30 200ml", "spray SPF50 150ml", "SPF50 crema facial 50ml"],
         "Protege la piel frente a la radiación UVA/UVB."),
        ("Cuidado capilar", "Champú",
         ["Champú anticaspa", "Champú fortalecedor", "Champú suave", "Champú anticaída"],
         ["300ml", "400ml", "250ml", "500ml"],
         "Limpia el cabello y cuida el cuero cabelludo."),
    ],
    "Primeros auxilios": [
        ("Antisépticos", "Antiséptico tópico",
         ["Clorhexidina", "Povidona yodada", "Agua oxigenada", "Alcohol 70%"],
         ["spray 100ml", "solución 250ml", "toallitas 20 unidades", "spray 60ml"],
         "Desinfecta heridas superficiales y previene infecciones."),
        ("Vendajes", "Apósito adhesivo",
         ["Apósito estándar", "Apósito resistente al agua", "Apósito transpirable",
          "Apósito infantil"],
         ["caja 20 unidades", "caja 40 unidades", "tiras surtidas 30 unidades",
          "resistente al agua 15 unidades"],
         "Protege heridas leves y favorece la cicatrización."),
        ("Termómetros", "Termómetro digital",
         ["Termómetro digital", "Termómetro frontal", "Termómetro infantil"],
         ["1 unidad", "infantil 1 unidad", "frontal 1 unidad", "flexible 1 unidad"],
         "Mide la temperatura corporal de forma rápida y precisa."),
    ],
    "Higiene bucal": [
        ("Pasta dental", "Pasta dentífrica",
         ["Pasta blanqueante", "Pasta sensitive", "Pasta encías", "Pasta infantil"],
         ["75ml", "125ml", "blanqueante 100ml", "sensitive 75ml"],
         "Limpieza diaria y protección frente a la caries."),
        ("Enjuague bucal", "Colutorio",
         ["Colutorio clásico", "Colutorio sin alcohol", "Colutorio encías",
          "Colutorio blanqueante"],
         ["250ml", "500ml", "sin alcohol 500ml", "encías sensibles 250ml"],
         "Refresca el aliento y complementa el cepillado diario."),
    ],
    "Cuidado del bebé": [
        ("Pañales", "Pañal infantil",
         ["Pañal sensitive", "Pañal active dry", "Pañal aqua pure"],
         ["talla 3, 42 unidades", "talla 4, 38 unidades", "talla 2, 44 unidades",
          "talla 5, 34 unidades"],
         "Máxima absorción y suavidad para la piel del bebé."),
        ("Toallitas", "Toallitas húmedas",
         ["Toallitas sensitive", "Toallitas aqua", "Toallitas dermo"],
         ["72 unidades", "84 unidades", "sensitive 60 unidades", "pack 3x72 unidades", "eco 60 unidades"],
         "Limpieza suave y respetuosa con la piel del bebé."),
    ],
    "Dermocosmética": [
        ("Antiacné", "Gel facial",
         ["Gel purificante", "Gel seborregulador", "Espuma limpiadora", "Loción antiimperfecciones"],
         ["gel 150ml", "gel 200ml", "espuma limpiadora 150ml", "loción 100ml", "crema noche 50ml"],
         "Ayuda a controlar el exceso de grasa y las imperfecciones."),
    ],
    "Ortopedia": [
        ("Vendajes elásticos", "Venda elástica",
         ["Venda elástica", "Tobillera de compresión", "Muñequera de compresión",
          "Rodillera de compresión"],
         ["8cm x 4m", "10cm x 4m", "tobillera talla M", "muñequera talla L", "coderas talla M"],
         "Proporciona sujeción y compresión en esguinces y molestias musculares."),
    ],
}

RANGOS_PRECIO = {
    "Medicamentos sin receta": (2.00, 18.00),
    "Vitaminas y suplementos": (5.00, 35.00),
    "Cuidado personal": (3.00, 25.00),
    "Primeros auxilios": (1.50, 15.00),
    "Higiene bucal": (2.00, 12.00),
    "Cuidado del bebé": (4.00, 22.00),
    "Dermocosmética": (6.00, 30.00),
    "Ortopedia": (3.00, 20.00),
}

# How many brands manufacture each (nivel3, concepto) generic product —
# this is what multiplies the number of PARENT products.
MARCAS_POR_CONCEPTO = 15

DESCUENTOS_POSIBLES = [5, 10, 15, 20, 25, 30, 40, 50]


def generar_precio(nivel2: str) -> float:
    lo, hi = RANGOS_PRECIO[nivel2]
    return round(random.uniform(lo, hi), 2)


def construir_padres() -> list:
    """
    Builds the full list of PARENT products: one entry per
    (nivel2, nivel3, nivel4, concepto, marca, variantes, desc_base)
    combination. Each parent carries its own list of possible variants
    (children) to be generated later.
    """
    padres = []
    contador_padre = 1
    for nivel2, entradas in TAXONOMIA.items():
        for nivel3, nivel4, conceptos, variantes, desc_base in entradas:
            for concepto in conceptos:
                marcas_asignadas = random.sample(
                    MARCAS, k=min(MARCAS_POR_CONCEPTO, len(MARCAS))
                )
                for marca in marcas_asignadas:
                    padres.append({
                        "padre_id": f"PADRE-{contador_padre:05d}",
                        "nivel2": nivel2,
                        "nivel3": nivel3,
                        "nivel4": nivel4,
                        "concepto": concepto,
                        "marca": marca,
                        "variantes": variantes,
                        "desc_base": desc_base,
                    })
                    contador_padre += 1
    return padres


def main():
    parser = argparse.ArgumentParser(description="Generates the pharmacy dummy catalog (with parent-child variants)")
    parser.add_argument("--output", default="catalogo_farmacia.csv")
    args = parser.parse_args()

    columnas = [
        "sku", "nombre", "descripcion", "categoria_nivel1", "categoria_nivel2",
        "categoria_nivel3", "categoria_nivel4", "precio", "stock", "descuento", "marca",
        "producto_padre_id", "tipo_variante", "valor_variante",
    ]

    padres = construir_padres()
    random.shuffle(padres)
    print(f"Productos padre generados: {len(padres)}")

    filas = []
    sku_contador = 1

    # Walk through parents, generating child rows (one per variant) until
    # we hit the target row count. Most parents contribute ALL of their
    # variants; the very last parent may be cut short to land exactly on
    # FILAS_OBJETIVO.
    for padre in padres:
        if len(filas) >= FILAS_OBJETIVO:
            break
        variantes_disponibles = list(padre["variantes"])
        random.shuffle(variantes_disponibles)

        for valor_variante in variantes_disponibles:
            if len(filas) >= FILAS_OBJETIVO:
                break
            nombre = f"{padre['marca']} {padre['concepto']} {valor_variante}"
            precio = generar_precio(padre["nivel2"])
            stock = "Yes" if random.random() < 0.85 else "No"
            descuento = 0 if random.random() < 0.675 else random.choice(DESCUENTOS_POSIBLES)

            filas.append({
                "sku": f"FAR-{sku_contador:06d}",
                "nombre": nombre,
                "descripcion": padre["desc_base"],
                "categoria_nivel1": CATEGORIA_NIVEL1,
                "categoria_nivel2": padre["nivel2"],
                "categoria_nivel3": padre["nivel3"],
                "categoria_nivel4": padre["nivel4"],
                "precio": f"{precio:.2f}",
                "stock": stock,
                "descuento": str(descuento),
                "marca": padre["marca"],
                "producto_padre_id": padre["padre_id"],
                "tipo_variante": "presentacion",
                "valor_variante": valor_variante,
            })
            sku_contador += 1

    random.shuffle(filas)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columnas, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(filas)

    padres_usados = len(set(r["producto_padre_id"] for r in filas))
    print(f"Generadas {len(filas)} filas ({padres_usados} productos padre distintos) en {args.output}")


if __name__ == "__main__":
    main()
