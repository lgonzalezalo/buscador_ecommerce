# Buscador semántico de ecommerce (PoC)

Prueba de concepto de un buscador basado en embeddings para catálogos
pequeños (~2.000 productos), corriendo 100% en local con
[Ollama](https://ollama.com) — sin coste de API, sin enviar datos a
terceros.

## Qué incluye

- Generador de catálogo dummy (`generate_catalog.py`) — 2.000 productos
  de ejemplo en 4 categorías (Alimentación, Ropa, Joyería, Electrodomésticos)
- Indexación de catálogo con embeddings (`build_index.py`)
- Búsqueda (`search.py`) con:
  - **Boost léxico por campo**, configurable (nombre > descripción > categoría)
  - **Spellcheck** contra el vocabulario real del catálogo (no un diccionario genérico)
  - **Ranking en dos niveles**: coincidencia léxica siempre antes que similitud semántica pura
  - **Stemming básico** de plurales/singulares en español (aro/aros, reloj/relojes...)
  - **Normalización de acentos** (joyeria = Joyería, sin confundir "ñ" con vocal acentuada)
  - **Normalización de unidades** (250gr = 250g = 250 gramos; 600mg = 600 mg)
  - **Detección de negación** ("sin X", "no X"), consciente del catálogo: distingue una
    negación genérica ("pendientes *sin aros*" → excluye aros) de un nombre de
    producto real ("*sujetador sin aros*" → se busca tal cual)
  - **Agrupación de variantes por producto padre**: si el catálogo modela
    relación padre-hijo (`producto_padre_id`), el "top N" cuenta productos
    distintos, no filas sueltas, y cada resultado muestra sus otras
    presentaciones disponibles (ver `catalogo_farmacia.csv` como ejemplo)
  - **Detección de intención + RAG de FAQ** (`intencion.py` + `faq.py`):
    distingue una búsqueda de producto de una pregunta general (envío,
    devoluciones, pago, garantía...) mediante **clasificación semántica**
    (un puñado de ejemplos por intención, comparados por embeddings — sin
    LLM generativo), y responde con la entrada más relevante de `faq.csv`,
    reutilizando el mismo mecanismo de embeddings ya construido para
    productos
- Suite de tests (`tests/`) que cubre toda la lógica anterior sin necesitar Ollama corriendo

## Requisitos

- Python 3.9 o superior (se usan anotaciones de tipo tipo `list[dict]`)
- [Ollama](https://ollama.com) instalado, con el modelo de embeddings descargado:
  ```bash
  ollama pull bge-m3
  ```

## Instalación

```bash
python -m venv venv
source venv/bin/activate       # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración

Todos los parámetros ajustables viven en **`config.yaml`**, no en el código:

```yaml
ollama:
  url: "http://localhost:11434/api/embeddings"
  model: "bge-m3"

pesos:
  nombre: 1.0
  descripcion: 0.5
  categoria: 0.3

spellcheck:
  cutoff: 0.87

tokenizacion:
  longitud_minima_palabra: 2
  stopwords: [de, del, la, el, ...]
  negadores: [sin, no]
```

`build_index.py` y `search.py` leen el mismo fichero — esto es importante:
si usaran modelos distintos, los embeddings generados al indexar dejarían
de ser comparables con los generados al buscar. Si `config.yaml` no existe
o falta alguna clave, se usan valores por defecto sensatos (no rompe nada).

Los pesos y el umbral de spellcheck también se pueden sobrescribir
puntualmente por línea de comandos (ver tabla más abajo) sin tocar el
fichero — útil para experimentar sin cambiar la configuración base.

## Uso

### 1. Generar el catálogo de ejemplo (opcional, ya viene incluido `catalogo_dummy.csv`)

```bash
python generate_catalog.py --output catalogo_dummy.csv
```

### 2. Indexar el catálogo

```bash
python build_index.py --input catalogo_dummy.csv --output index
```

Esto genera `index_vectors.npy` (los embeddings) e `index_meta.json`
(la información de cada producto). Ambos ficheros son regenerables y
están excluidos del control de versiones (ver `.gitignore`).

### 3. Buscar

```bash
python search.py --query "sudadera sin capucha"
python search.py --query "pendientes sin aros" --top 3
python search.py --query "collar de oro" --solo-stock
```

### Parámetros disponibles en `search.py`

| Parámetro | Por defecto | Qué controla |
|---|---|---|
| `--query` | *(obligatorio)* | Texto de búsqueda |
| `--index` | `index` | Prefijo de los ficheros de índice |
| `--top` | `5` | Número de resultados a mostrar |
| `--solo-stock` | desactivado | Filtra solo productos con stock disponible |
| `--peso-nombre` | `1.0` | Peso del boost léxico en el campo nombre |
| `--peso-descripcion` | `0.5` | Peso del boost léxico en descripción |
| `--peso-categoria` | `0.3` | Peso del boost léxico en categoría |
| `--spellcheck-cutoff` | `0.87` | Umbral de similitud (0-1) para aceptar una corrección ortográfica |
| `--faq` | `faq.csv` | CSV de preguntas frecuentes para el RAG |
| `--intencion` | `auto` | Forzar `producto` o `faq` en vez de detectarlo automáticamente (útil para demos) |

## Detección de intención + RAG de FAQ

Antes de tocar nada de lógica de producto, `search.py` decide si la
consulta es una **búsqueda de producto** o una **pregunta general**
(envío, devoluciones, pago, garantía, horario...) mediante
**clasificación semántica** (`intencion.py`): un puñado de frases de
ejemplo por cada intención (~10 de producto, ~12 de FAQ) se embeben una
vez por ejecución, y la query se clasifica según a qué ejemplo se
parece más por similitud coseno — el mismo mecanismo que ya usas para
productos y para el RAG de FAQ, sin necesidad de un LLM generativo.

Este enfoque sustituyó a una primera versión basada en una lista fija
de palabras clave. El problema de esa versión: solo reconocía la forma
exacta de cada palabra ("envío"), no sus conjugaciones ("enviáis",
"enviamos") ni sinónimos, así que había que enumerar cada variante a
mano. La clasificación semántica no necesita eso — el modelo de
embeddings ya entiende que "enviáis" y "envío" hablan de lo mismo.

Si detecta una pregunta general, busca la entrada más parecida en
`faq.csv` usando el mismo mecanismo de embeddings (`faq.py`), y
devuelve esa respuesta directamente — **es recuperación pura, no
generación**: no hay ningún LLM redactando una respuesta nueva, solo se
enseña la respuesta ya escrita más relevante.

```bash
python search.py --query "¿cuánto tarda el envío?"
python search.py --query "¿enviáis gratis?"
python search.py --query "quiero hacer una devolución"
python search.py --query "¿necesito receta para comprar esto?"
```

**Coste de este enfoque**: cada ejecución añade ~22 llamadas de
embedding extra (los ejemplos de producto + FAQ), además de la propia
query — un coste constante y pequeño con Ollama en local, no algo que
crezca con el tamaño del catálogo.

**Limitación conocida**: la calidad de la clasificación depende de qué
tan bien los ~22 ejemplos representen los temas reales de tu tienda.
Si aparece un tema nuevo sin ningún ejemplo parecido en ninguna de las
dos listas (`EJEMPLOS_PRODUCTO`/`EJEMPLOS_FAQ` en `intencion.py`), el
resultado es forzosamente el "menos malo" de los dos grupos, no una
tercera opción — ampliar los ejemplos con casos reales que falle según
se use es la forma de mejorarlo con el tiempo.

## Catálogo de farmacia (con variantes padre-hijo)

Además del catálogo general, el proyecto incluye `catalogo_farmacia.csv`
(5.000 productos) y su generador (`generate_catalog_farmacia.py`), pensado
como banco de pruebas para dos cosas que el catálogo general no ejercita:
normalización de unidades tipo `mg`/`mcg` (dosis de medicamentos) y la
**relación padre-hijo entre variantes de producto**.

### Esquema adicional

Mismo esquema que el catálogo general, más tres columnas:

| Columna | Qué guarda |
|---|---|
| `producto_padre_id` | Compartido por todas las variantes de un mismo producto base (ej. todas las dosis de "Farmalia Paracetamol") |
| `tipo_variante` | Qué distingue a las variantes entre sí (aquí siempre `"presentacion"`) |
| `valor_variante` | El valor concreto de esa variante (ej. `"600mg 20 comprimidos"`) |

Un "padre" es una combinación (concepto genérico + marca) — ej.
"Farmalia Paracetamol" — y sus "hijos" son las distintas dosis/formatos/
cantidades de ese mismo producto. Marca, descripción y categoría se
comparten entre hermanos; precio, stock y descuento son independientes
por variante. El catálogo tiene 1.206 productos padre distintos.

### Regenerar, indexar y buscar

```bash
python generate_catalog_farmacia.py --output catalogo_farmacia.csv
python build_index.py --input catalogo_farmacia.csv --output index_farmacia
python search.py --index index_farmacia --query "paracetamol" --top 3
python search.py --index index_farmacia --query "vitamina d 25mcg"
python search.py --index index_farmacia --query "jarabe sin azúcar"
```

Con este catálogo, el "top N" de `search.py` cuenta **productos padre
distintos**, no filas sueltas — cada resultado incluye un bloque "Otras
presentaciones" con el resto de dosis/formatos de esa misma marca,
mostrando su propio precio, descuento y stock (ver `variantes.py`).

## Tests

```bash
python -m unittest discover -s tests -v
```

Los tests no requieren que Ollama esté instalado ni corriendo: las
funciones que llaman a Ollama (`embed_query`) se sustituyen por una
versión falsa y determinista durante los tests.

Si prefieres `pytest` (opcional, requiere instalarlo aparte):
```bash
pip install pytest
pytest tests/ -v
```

## Estructura del proyecto

El código está organizado en carpetas por dominio. Los 4 comandos que se
usan a diario (`search.py`, `build_index.py`, `generate_catalog.py`,
`generate_catalog_farmacia.py`) siguen ejecutándose igual desde la raíz
— son "envoltorios" finos que delegan en la implementación real dentro
de cada carpeta, para no tener que recordar rutas nuevas.

```
.
├── search.py                     # Envoltorio: delega en busqueda/search.py
├── build_index.py                # Envoltorio: delega en indexado/build_index.py
├── generate_catalog.py           # Envoltorio: delega en catalogos/generate_catalog.py
├── generate_catalog_farmacia.py  # Envoltorio: delega en catalogos/generate_catalog_farmacia.py
│
├── config.yaml                   # Configuración centralizada (pesos, modelo, stopwords...)
├── catalogo_dummy.csv            # Catálogo de ejemplo ya generado
├── catalogo_farmacia.csv         # Catálogo de farmacia con relación padre-hijo
├── faq.csv                       # Dataset de preguntas frecuentes
├── requirements.txt
│
├── config/
│   ├── __init__.py
│   └── config.py                 # Carga config.yaml
│
├── indexado/
│   ├── __init__.py
│   ├── indice.py                 # Carga de índice, embeddings, formato de categoría
│   └── build_index.py            # Implementación real de la indexación
│
├── busqueda/
│   ├── __init__.py
│   ├── normalizacion.py          # Acentos, unidades, plurales, tokenización
│   ├── negacion.py               # Detección de negación consciente del catálogo
│   ├── spellcheck.py             # Corrección ortográfica contra el vocabulario propio
│   ├── variantes.py              # Agrupación de resultados por producto padre
│   └── search.py                 # Orquesta boost léxico, ranking y CLI (implementación real)
│
├── faq/
│   ├── __init__.py
│   ├── intencion.py              # Clasificación semántica de intención (producto vs. pregunta general)
│   └── faq.py                    # RAG de recuperación sobre FAQ
│
├── catalogos/
│   ├── __init__.py
│   ├── generate_catalog.py       # Implementación real: catálogo dummy de 2000 productos
│   └── generate_catalog_farmacia.py  # Implementación real: catálogo de farmacia (5000, con variantes)
│
├── tests/
│   ├── test_search.py            # Tests de la lógica de búsqueda
│   ├── test_config.py            # Tests del parseo de config.yaml (bug de PyYAML)
│   ├── test_variantes.py         # Tests de agrupación por producto padre
│   ├── test_intencion.py         # Tests del router de intención
│   ├── test_faq.py               # Tests del RAG de recuperación
│   └── test_build_index.py       # Tests de carga/indexación de catálogo
│
└── .gitignore
```

**Nota técnica**: cada carpeta de código es un paquete Python (tiene su
`__init__.py`, vacío). Los datos (`config.yaml`, los `.csv`) se quedan
en la raíz a propósito, para que ninguna ruta relativa se rompa al
reorganizar solo el código.


## Limitaciones conocidas (es una PoC, no producción)

- **Sin base de datos vectorial dedicada**: los vectores se guardan en un
  `.npy` y se comparan en memoria. Válido hasta ~50.000-100.000 SKUs;
  por encima de eso conviene migrar a Qdrant, pgvector o ClickHouse.
- **Sin backend ni API**: es un script de línea de comandos, no un
  servicio. Para integrarlo en una tienda real haría falta envolverlo
  en un endpoint (FastAPI) y un widget/plugin de integración.
- **Stemming heurístico, no un lematizador real**: cubre los casos
  comunes de plural en español, pero no maneja irregularidades complejas.
- **Negación básica**: solo entiende el patrón "negador + palabra
  siguiente" ("sin X"), no negaciones compuestas ("ni X ni Y").
- **Variantes solo modeladas en el catálogo de farmacia**: el catálogo
  general (`catalogo_dummy.csv`) no tiene relación padre-hijo — cada
  fila es un producto independiente. `variantes.py` funciona con
  cualquier catálogo (cae a "un grupo por fila" si no hay
  `producto_padre_id`), pero para verlo en acción de verdad hace falta
  un catálogo que sí modele variantes, como `catalogo_farmacia.csv`.
- **RAG de solo recuperación, no de generación**: `faq.py` devuelve la
  respuesta ya escrita más parecida, no redacta una respuesta nueva con
  un LLM. Conectar una API barata (Claude Haiku, GPT-4o-mini) para
  generar una respuesta más natural a partir del contexto recuperado
  es la mejora natural siguiente, no algo que haga falta para que esto
  ya sea útil.
- **Clasificación de intención limitada por los ejemplos, no por
  reglas exhaustivas**: una pregunta sobre un tema sin ningún ejemplo
  parecido en `EJEMPLOS_PRODUCTO`/`EJEMPLOS_FAQ` (`intencion.py`) se
  clasifica igualmente como uno de los dos grupos — el más parecido de
  los dos, no una tercera opción de "no lo sé". Ampliar los ejemplos
  con casos reales es la forma de mejorar esto con el tiempo.
- **Coste de operación**: prácticamente $0 corriendo en local con
  Ollama. Si se sustituye por una API de pago (OpenAI, etc.), el coste
  para este volumen de catálogo sigue siendo de céntimos al mes.
