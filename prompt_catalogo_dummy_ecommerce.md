# Prompt: Catálogo dummy de ecommerce (2000 productos)

Copia y pega el bloque de abajo ("PROMPT") en un chat de IA (ChatGPT, Claude, Gemini...) para que genere el catálogo, o úsalo como especificación técnica si prefieres generarlo con un script (Python + Faker, etc.).

---

## PROMPT

Actúa como generador de datos dummy para un ecommerce. Genera un catálogo de **2000 productos** en formato **CSV**, siguiendo exactamente estas reglas:

### 1. Columnas (en este orden exacto)

```
sku,nombre,descripcion,categoria_nivel1,categoria_nivel2,categoria_nivel3,categoria_nivel4,precio,stock,descuento,marca
```

### 2. Descripción de cada campo

- **sku**: identificador único del producto, formado por un prefijo de 3 letras según la categoría principal + número secuencial de 6 dígitos: `ALI-000001` (Alimentación), `ROP-000001` (Ropa), `JOY-000001` (Joyería), `ELE-000001` (Electrodomésticos). No debe haber SKUs repetidos.
- **nombre**: nombre comercial del producto, corto y realista (ej. "Camiseta básica algodón manga corta").
- **descripcion**: 1-2 frases describiendo el producto (materiales, uso, características), en español, sin repetir literalmente el nombre.
- **categoria_nivel1 / nivel2 / nivel3 / nivel4**: taxonomía jerárquica de 4 niveles (ver sección 4). Cada nivel debe ser coherente con el anterior (el nivel 4 es el más específico).
- **precio**: número decimal en euros, con punto como separador decimal (ej. `12.99`), dentro del rango de la categoría (ver sección 5).
- **stock**: `Yes` si hay existencias, `No` si está agotado. Aproximadamente el 85% de los productos deben tener `Yes` y el 15% `No`.
- **descuento**: `0` si el producto no tiene descuento, o un número entero entre `5` y `70` representando el **porcentaje** de descuento. Aproximadamente el 65-70% de los productos deben tener `0` (sin descuento) y el resto un descuento aleatorio dentro del rango.
- **marca**: marca **ficticia inventada** (no usar marcas reales existentes). Usa un conjunto reducido de marcas ficticias por categoría (8-15 marcas distintas por categoría principal) y reutilízalas entre productos, en vez de inventar una marca distinta para cada fila — así el catálogo resulta realista.

### 3. Distribución de las 2000 entradas por categoría principal

Reparto proporcional/realista (no equitativo):

| Categoría principal | % | Nº de productos |
|---|---|---|
| Alimentación | 35% | 700 |
| Ropa | 35% | 700 |
| Electrodomésticos | 20% | 400 |
| Joyería | 10% | 200 |

### 4. Taxonomía de 4 niveles — ejemplos orientativos (amplía y varía sub-niveles para cubrir todos los productos, no repitas siempre las mismas rutas)

**Alimentación**
- Alimentación > Lácteos > Quesos > Queso curado
- Alimentación > Bebidas > Refrescos > Refresco de cola
- Alimentación > Panadería > Pan de molde > Pan integral
- Alimentación > Frutas y verduras > Frutas frescas > Manzanas
- Alimentación > Congelados > Platos preparados > Lasaña congelada

**Ropa**
- Ropa > Hombre > Camisetas > Camiseta manga corta
- Ropa > Mujer > Vestidos > Vestido largo
- Ropa > Niños > Abrigos > Abrigo de invierno
- Ropa > Calzado > Zapatillas > Zapatillas deportivas
- Ropa > Accesorios > Bufandas > Bufanda de lana

**Joyería**
- Joyería > Anillos > Anillos de oro > Anillo de compromiso
- Joyería > Collares > Collares de plata > Collar con colgante
- Joyería > Pulseras > Pulseras de cuero > Pulsera trenzada
- Joyería > Relojes > Relojes analógicos > Reloj de pulsera clásico
- Joyería > Pendientes > Pendientes de plata > Pendientes de aro

**Electrodomésticos**
- Electrodomésticos > Cocina > Frigoríficos > Frigorífico combi
- Electrodomésticos > Limpieza > Aspiradoras > Aspiradora sin cable
- Electrodomésticos > Climatización > Aire acondicionado > Split 1x1
- Electrodomésticos > Pequeño electrodoméstico > Cafeteras > Cafetera de cápsulas
- Electrodomésticos > Cuidado personal > Secadores de pelo > Secador iónico

### 5. Rangos de precio orientativos por categoría

- Alimentación: 0,50€ – 30€
- Ropa: 5€ – 200€
- Joyería: 10€ – 2000€
- Electrodomésticos: 20€ – 1500€

### 6. Reglas generales

- No repitas exactamente el mismo `nombre` + misma combinación de categorías dos veces (varía tallas, sabores, colores, modelos, capacidades, etc., para dar variedad realista).
- El CSV debe tener cabecera en la primera fila con los nombres de columna exactos indicados en el punto 1.
- Usa comillas dobles para encerrar cualquier campo de texto que contenga comas.
- Codificación UTF-8.
- Genera las 2000 filas completas (no resumas ni trunques la salida); si el canal de salida tiene límite de longitud, genera el CSV en bloques sucesivos hasta completar las 2000 filas, sin repetir la cabecera en los bloques intermedios.

### 7. Ejemplo de fila válida

```
ROP-000001,"Camiseta básica algodón manga corta","Camiseta de algodón 100% suave y transpirable, ideal para el día a día.",Ropa,Hombre,Camisetas,Camiseta manga corta,9.99,Yes,20,UrbanCotto
```

---

*Nota: todas las marcas, nombres y descripciones son ficticios y están pensados únicamente para pruebas/desarrollo (datos dummy), no representan productos ni marcas reales.*
