"""
generate_catalog.py
--------------------
Generates the 2000-product dummy catalog following the spec in
prompt_catalogo_dummy_ecommerce.md: 4 main categories, a 4-level
taxonomy, price ranges, stock, discounts, and fictitious brands.

Usage:
    python generate_catalog.py --output catalogo_dummy.csv
"""

import argparse
import csv
import random

random.seed(42)  # for reproducibility

# ---------------------------------------------------------------------------
# Fictitious brands per main category (8-15 per category, reused across products)
# ---------------------------------------------------------------------------
MARCAS = {
    "Alimentación": [
        "Huerta Real", "Sabor Norte", "La Espiga Dorada", "Campo Fresco",
        "Delicia Natural", "Grano de Oro", "Sabores del Sur", "Nutrivida",
        "La Tahona Azul", "Verde Cosecha", "Punto Sabor", "Cesta Rústica",
    ],
    "Ropa": [
        "UrbanCotto", "NordVía", "TrazoBlue", "Alta Fibra", "Costura 21",
        "Modaline", "Vestir Norte", "TelaViva", "Estilo Urbano", "SolTejido",
        "Prenda Libre", "Hilo & Forma",
    ],
    "Joyería": [
        "Orfebre Real", "Lumina Joyas", "Plata del Norte", "Aurea Diseño",
        "Brillo Eterno", "Joyas del Valle", "Metal Noble", "Reflejo Fino",
        "Gema Pura", "Esencia de Oro",
    ],
    "Electrodomésticos": [
        "HogarTech", "NordLine", "Confort Total", "Vitalux", "TecnoCasa",
        "Aire Puro", "CocinaSmart", "Domus Pro", "Electra Norte", "CasaFácil",
        "Impulso Hogar",
    ],
}

# ---------------------------------------------------------------------------
# Taxonomy of 4 levels + name templates and variants per category
# Each entry: (nivel2, nivel3, nivel4, plantilla_nombre, [variantes], plantilla_desc)
# ---------------------------------------------------------------------------
TAXONOMIA = {
    "Alimentación": [
        ("Lácteos", "Quesos", "Queso curado", "Queso curado {v}",
         ["de oveja", "de cabra", "mezcla", "añejo", "semicurado"],
         "Queso elaborado con leche seleccionada, curación tradicional y sabor intenso."),
        ("Bebidas", "Refrescos", "Refresco de cola", "Refresco de cola {v}",
         ["original", "sin azúcar", "sabor lima", "light", "zero cafeína"],
         "Bebida refrescante carbonatada, ideal para acompañar comidas o disfrutar fría."),
        ("Panadería", "Pan de molde", "Pan integral", "Pan integral {v}",
         ["con semillas", "sin corteza", "100% centeno", "multicereales", "bajo en sal"],
         "Pan de miga suave elaborado con harina integral, fuente de fibra."),
        ("Frutas y verduras", "Frutas frescas", "Manzanas", "Manzanas {v}",
         ["Golden", "Fuji", "Royal Gala", "de temporada", "ecológicas"],
         "Fruta fresca de temporada, seleccionada por tamaño y calidad."),
        ("Congelados", "Platos preparados", "Lasaña congelada", "Lasaña congelada {v}",
         ["de carne", "de verduras", "boloñesa", "individual", "familiar"],
         "Plato preparado listo en minutos, ideal para el día a día."),
        ("Bebidas", "Zumos", "Zumo de naranja", "Zumo de naranja {v}",
         ["exprimido", "sin pulpa", "con pulpa", "1L", "pack 6 unidades"],
         "Zumo elaborado a partir de naranjas seleccionadas, sin azúcares añadidos."),
        ("Panadería", "Bollería", "Croissant", "Croissant {v}",
         ["de mantequilla", "relleno de chocolate", "integral", "mini pack", "sin gluten"],
         "Bollería horneada con receta tradicional, textura hojaldrada."),
        ("Lácteos", "Yogures", "Yogur natural", "Yogur natural {v}",
         ["sin azúcar", "griego", "pack 4 unidades", "desnatado", "con bífidus"],
         "Yogur cremoso elaborado con leche fresca y fermentos activos."),
        ("Frutas y verduras", "Verduras frescas", "Tomates", "Tomates {v}",
         ["pera", "rama", "cherry", "ecológicos", "de huerta"],
         "Verdura fresca de cultivo controlado, ideal para ensaladas y cocinar."),
        ("Congelados", "Helados", "Helado de vainilla", "Helado de vainilla {v}",
         ["tarrina 1L", "sin lactosa", "con trozos de chocolate", "artesano", "bajo en azúcar"],
         "Helado cremoso elaborado con vainilla natural, textura suave."),
    ],
    "Ropa": [
        ("Hombre", "Camisetas", "Camiseta manga corta", "Camiseta básica algodón manga corta {v}",
         ["blanca", "negra", "azul marino", "gris jaspeado", "verde oliva"],
         "Camiseta de algodón 100% suave y transpirable, ideal para el día a día."),
        ("Mujer", "Vestidos", "Vestido largo", "Vestido largo {v}",
         ["estampado floral", "liso negro", "de lino", "con cinturón", "fiesta"],
         "Vestido de corte fluido, tejido ligero y caída favorecedora."),
        ("Niños", "Abrigos", "Abrigo de invierno", "Abrigo de invierno infantil {v}",
         ["acolchado", "con capucha", "impermeable", "de lana", "reversible"],
         "Abrigo cálido y resistente pensado para los meses más fríos."),
        ("Calzado", "Zapatillas", "Zapatillas deportivas", "Zapatillas deportivas {v}",
         ["running", "para caminar", "unisex", "con memory foam", "de malla transpirable"],
         "Zapatillas ligeras con buena amortiguación, pensadas para uso diario o deporte."),
        ("Accesorios", "Bufandas", "Bufanda de lana", "Bufanda de lana {v}",
         ["gris", "a cuadros", "de punto grueso", "unisex", "con flecos"],
         "Bufanda cálida tejida en lana suave, ideal para el invierno."),
        ("Hombre", "Pantalones", "Pantalón vaquero", "Pantalón vaquero {v}",
         ["slim fit", "recto", "desgastado", "negro", "regular fit"],
         "Pantalón vaquero de algodón resistente con corte cómodo."),
        ("Mujer", "Camisas", "Blusa manga larga", "Blusa manga larga {v}",
         ["estampada", "lisa blanca", "con lazo", "de seda sintética", "oversize"],
         "Blusa ligera de tacto suave, versátil para looks casuales o de oficina."),
        ("Calzado", "Botas", "Bota de invierno", "Bota de invierno {v}",
         ["impermeable", "con forro polar", "de cordones", "alta", "antideslizante"],
         "Bota resistente al agua con suela antideslizante, pensada para el frío."),
        ("Niños", "Camisetas", "Camiseta estampada", "Camiseta infantil estampada {v}",
         ["dinosaurios", "unicornios", "rayas", "algodón orgánico", "pack 2 unidades"],
         "Camiseta infantil de algodón suave con estampado divertido."),
        ("Accesorios", "Gorros", "Gorro de punto", "Gorro de punto {v}",
         ["con pompón", "unisex", "reversible", "térmico", "de lana merino"],
         "Gorro tejido que abriga sin renunciar al estilo."),
        ("Mujer", "Sudaderas", "Sudadera con capucha", "Sudadera con capucha {v}",
         ["gris jaspeada", "negra", "oversize", "de algodón orgánico", "estampada"],
         "Sudadera cómoda con capucha y bolsillo canguro, ideal para el día a día."),
        ("Mujer", "Sudaderas", "Sudadera sin capucha", "Sudadera sin capucha {v}",
         ["cuello redondo", "básica blanca", "oversize", "de algodón", "con logo bordado"],
         "Sudadera básica sin capucha, cómoda y versátil para combinar con cualquier look."),
        ("Mujer", "Lencería", "Sujetador con aros", "Sujetador con aros {v}",
         ["negro", "blanco", "con encaje", "push up", "de raso"],
         "Sujetador con aros que proporciona sujeción y buen levantamiento."),
        ("Mujer", "Lencería", "Sujetador sin aros", "Sujetador sin aros {v}",
         ["negro", "blanco", "de algodón", "deportivo", "con encaje"],
         "Sujetador sin aros, cómodo y flexible, ideal para el uso diario."),
    ],
    "Joyería": [
        ("Anillos", "Anillos de oro", "Anillo de compromiso", "Anillo de compromiso {v}",
         ["oro 18k con diamante", "oro blanco", "solitario", "clásico", "con circonita"],
         "Anillo elaborado en oro de alta calidad, acabado pulido y elegante."),
        ("Collares", "Collares de plata", "Collar con colgante", "Collar con colgante {v}",
         ["de plata 925", "corazón", "iniciales", "minimalista", "con perla"],
         "Collar de plata con acabado brillante, diseño delicado y atemporal."),
        ("Pulseras", "Pulseras de cuero", "Pulsera trenzada", "Pulsera trenzada {v}",
         ["de cuero marrón", "negra", "con cierre magnético", "unisex", "doble vuelta"],
         "Pulsera artesanal trenzada a mano, resistente y de estilo casual."),
        ("Relojes", "Relojes analógicos", "Reloj de pulsera clásico", "Reloj de pulsera clásico {v}",
         ["correa de piel", "esfera dorada", "acero inoxidable", "resistente al agua", "unisex"],
         "Reloj de diseño clásico con maquinaria de precisión y acabado elegante."),
        ("Pendientes", "Pendientes de plata", "Pendientes de aro", "Pendientes de aro {v}",
         ["pequeños", "grandes", "de plata 925", "con circonitas", "minimalistas"],
         "Pendientes ligeros de plata con acabado brillante, fáciles de combinar."),
        ("Pendientes", "Pendientes de perla", "Pendientes de perla", "Pendientes de perla {v}",
         ["cultivada", "blanca", "gris", "con montura de plata", "clásicos"],
         "Pendientes elegantes con perla natural, acabado delicado y atemporal."),
        ("Pendientes", "Pendientes de diamante", "Pendientes de tachuela", "Pendientes de tachuela {v}",
         ["con circonita", "diminutos", "de oro blanco", "para uso diario", "hipoalergénicos"],
         "Pendientes pequeños y discretos, ideales para el uso diario."),
        ("Pendientes", "Pendientes colgantes", "Pendientes largos", "Pendientes largos {v}",
         ["de cadena", "con borla", "geométricos", "bohemios", "de plata oxidada"],
         "Pendientes de diseño llamativo, perfectos para ocasiones especiales."),
        ("Anillos", "Anillos de plata", "Anillo ajustable", "Anillo ajustable {v}",
         ["con piedra natural", "minimalista", "trenzado", "doble banda", "con inicial"],
         "Anillo de plata de talla ajustable, cómodo para uso diario."),
        ("Collares", "Collares de oro", "Cadena fina", "Cadena fina de oro {v}",
         ["18k", "eslabón cubano", "con cruz", "delicada", "45cm"],
         "Cadena de oro de acabado fino, ideal para uso diario o combinar con colgantes."),
        ("Pulseras", "Pulseras de plata", "Pulsera de eslabones", "Pulsera de eslabones {v}",
         ["plata 925", "gruesa", "con dije", "ajustable", "brillante"],
         "Pulsera de plata con eslabones resistentes y acabado pulido."),
    ],
    "Electrodomésticos": [
        ("Cocina", "Frigoríficos", "Frigorífico combi", "Frigorífico combi {v}",
         ["No Frost", "clase energética A++", "185cm", "acero inoxidable", "con dispensador de agua"],
         "Frigorífico de gran capacidad con tecnología de enfriamiento eficiente."),
        ("Limpieza", "Aspiradoras", "Aspiradora sin cable", "Aspiradora sin cable {v}",
         ["2 en 1", "con batería de larga duración", "ligera", "con filtro HEPA", "recargable"],
         "Aspiradora inalámbrica de fácil manejo, ideal para limpiezas rápidas."),
        ("Climatización", "Aire acondicionado", "Split 1x1", "Aire acondicionado Split 1x1 {v}",
         ["inverter", "bomba de calor", "3000 frigorías", "wifi", "bajo consumo"],
         "Equipo de climatización eficiente con control de temperatura preciso."),
        ("Pequeño electrodoméstico", "Cafeteras", "Cafetera de cápsulas", "Cafetera de cápsulas {v}",
         ["compacta", "con espumador de leche", "multibebida", "programable", "de diseño retro"],
         "Cafetera práctica que prepara café de calidad en segundos."),
        ("Cuidado personal", "Secadores de pelo", "Secador iónico", "Secador iónico {v}",
         ["profesional", "2000W", "con difusor", "silencioso", "ligero"],
         "Secador con tecnología iónica que reduce el encrespamiento del cabello."),
        ("Cocina", "Hornos", "Horno eléctrico", "Horno eléctrico {v}",
         ["multifunción", "con grill", "de sobremesa", "empotrable", "60cm"],
         "Horno con distribución uniforme del calor y múltiples funciones de cocinado."),
        ("Limpieza", "Robots aspiradores", "Robot aspirador", "Robot aspirador {v}",
         ["con mopa", "wifi", "navegación láser", "autovaciado", "compacto"],
         "Robot inteligente que limpia y friega de forma autónoma."),
        ("Pequeño electrodoméstico", "Batidoras", "Batidora de mano", "Batidora de mano {v}",
         ["con accesorios", "600W", "inoxidable", "con vaso medidor", "multivelocidad"],
         "Batidora versátil pensada para triturar, batir y emulsionar."),
        ("Climatización", "Ventiladores", "Ventilador de torre", "Ventilador de torre {v}",
         ["con mando a distancia", "silencioso", "oscilante", "con temporizador", "bajo consumo"],
         "Ventilador de diseño compacto con distintas velocidades de ventilación."),
        ("Cuidado personal", "Depiladoras", "Depiladora eléctrica", "Depiladora eléctrica {v}",
         ["recargable", "resistente al agua", "con cabezales intercambiables", "compacta", "silenciosa"],
         "Depiladora eficaz de uso doméstico, ligera y fácil de manejar."),
    ],
}

# SKU prefixes per category
PREFIJOS = {
    "Alimentación": "ALI",
    "Ropa": "ROP",
    "Joyería": "JOY",
    "Electrodomésticos": "ELE",
}

# Price range per category (min, max)
RANGOS_PRECIO = {
    "Alimentación": (0.50, 30.0),
    "Ropa": (5.0, 200.0),
    "Joyería": (10.0, 2000.0),
    "Electrodomésticos": (20.0, 1500.0),
}

# Distribution of the 2000 rows across main categories
DISTRIBUCION = {
    "Alimentación": 700,
    "Ropa": 700,
    "Electrodomésticos": 400,
    "Joyería": 200,
}

DESCUENTOS_POSIBLES = [5, 10, 15, 20, 25, 30, 40, 50, 60, 70]


def generar_precio(categoria: str) -> float:
    lo, hi = RANGOS_PRECIO[categoria]
    return round(random.uniform(lo, hi), 2)


def generar_fila(categoria: str, contador: int) -> dict:
    nivel2, nivel3, nivel4, plantilla, variantes, desc_base = random.choice(TAXONOMIA[categoria])
    variante = random.choice(variantes)
    nombre = plantilla.format(v=variante)
    marca = random.choice(MARCAS[categoria])
    sku = f"{PREFIJOS[categoria]}-{contador:06d}"
    precio = generar_precio(categoria)
    stock = "Yes" if random.random() < 0.85 else "No"
    descuento = 0 if random.random() < 0.675 else random.choice(DESCUENTOS_POSIBLES)

    return {
        "sku": sku,
        "nombre": nombre,
        "descripcion": desc_base,
        "categoria_nivel1": categoria,
        "categoria_nivel2": nivel2,
        "categoria_nivel3": nivel3,
        "categoria_nivel4": nivel4,
        "precio": f"{precio:.2f}",
        "stock": stock,
        "descuento": str(descuento),
        "marca": marca,
    }


def main():
    parser = argparse.ArgumentParser(description="Genera el catálogo dummy de ecommerce")
    parser.add_argument("--output", default="catalogo_dummy.csv")
    args = parser.parse_args()

    columnas = [
        "sku", "nombre", "descripcion", "categoria_nivel1", "categoria_nivel2",
        "categoria_nivel3", "categoria_nivel4", "precio", "stock", "descuento", "marca",
    ]

    filas = []
    for categoria, cantidad in DISTRIBUCION.items():
        for i in range(1, cantidad + 1):
            filas.append(generar_fila(categoria, i))

    random.shuffle(filas)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columnas, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(filas)

    print(f"Generadas {len(filas)} filas en {args.output}")


if __name__ == "__main__":
    main()
