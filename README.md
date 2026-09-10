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
  - **Detección de negación** ("sin X", "no X"), consciente del catálogo: distingue una
    negación genérica ("pendientes *sin aros*" → excluye aros) de un nombre de
    producto real ("*sujetador sin aros*" → se busca tal cual)
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

```
.
├── config.yaml             # Configuración centralizada (pesos, modelo, stopwords...)
├── config.py               # Módulo que carga config.yaml
├── generate_catalog.py    # Genera el catálogo dummy de 2000 productos
├── build_index.py         # Indexa un catálogo generando embeddings
├── search.py              # Busca en el índice generado
├── catalogo_dummy.csv     # Catálogo de ejemplo ya generado
├── requirements.txt       # Dependencias de ejecución
├── tests/
│   ├── test_search.py       # Tests de la lógica de búsqueda
│   └── test_build_index.py  # Tests de carga/indexación de catálogo
└── .gitignore
```

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
- **Coste de operación**: prácticamente $0 corriendo en local con
  Ollama. Si se sustituye por una API de pago (OpenAI, etc.), el coste
  para este volumen de catálogo sigue siendo de céntimos al mes.
