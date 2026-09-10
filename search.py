"""
search.py (con boost por campo, spellcheck y ranking en dos niveles)
------------------------------------------------------------------------
Cambios respecto a la versión anterior:

1. Boost por campo configurable: nombre, descripcion y categoria tienen
   pesos distintos (nombre > descripcion > categoria), ajustables por
   constante o por línea de comandos.
2. Spellcheck contra el vocabulario real del catálogo: si una búsqueda
   no tiene ninguna coincidencia léxica, se comprueba si alguna palabra
   se parece mucho a una palabra del catálogo y, si es así, se corrige
   y se repite la búsqueda automáticamente.
3. Ranking en dos niveles: primero se muestran los productos con
   coincidencia léxica real (ordenados entre ellos por similitud
   semántica), y después el resto, ordenados solo por similitud
   semántica. La búsqueda semántica pura nunca "adelanta" a un match
   léxico exacto.

Uso:
    python search.py --query "colar de plata" --top 5
    python search.py --query "algo para el frio" --top 5 --peso-nombre 1.5
"""

import argparse
import json
import os
import re
import sys
from difflib import get_close_matches

import numpy as np
import requests

from config import cargar_config

CONFIG = cargar_config()

OLLAMA_URL = CONFIG["ollama"]["url"]
EMBEDDING_MODEL = CONFIG["ollama"]["model"]

# Pesos por defecto del boost léxico. Cuanto más alto, más "premia" una
# coincidencia en ese campo. Vienen de config.yaml; se pueden sobrescribir
# puntualmente por línea de comandos sin tocar el fichero.
PESOS_DEFECTO = CONFIG["pesos"]

SPELLCHECK_CUTOFF_DEFECTO = CONFIG["spellcheck"]["cutoff"]

# Palabras funcionales (preposiciones, artículos, conjunciones) que no
# aportan significado para buscar productos. Se ignoran en el boost léxico
# y en el spellcheck, independientemente de su longitud. Vienen de
# config.yaml. Importante: ni "sin" ni "con" están aquí — ambas pueden
# formar parte de nombres de producto reales ("sudadera con capucha").
STOPWORDS = set(CONFIG["tokenizacion"]["stopwords"])

# Palabras que indican negación/exclusión. Cuando aparecen, la palabra
# siguiente NO se busca de forma positiva: se guarda como término a
# EXCLUIR de los resultados.
NEGADORES = set(CONFIG["tokenizacion"]["negadores"])

# Longitud mínima como red de seguridad adicional (evita ruido de 1-2 letras
# que se cuele si no está en la lista de stopwords), pero ya no es el filtro
# principal — eso lo hace STOPWORDS.
LONGITUD_MINIMA_PALABRA = 2


# ---------------------------------------------------------------------------
# Carga de índice y utilidades básicas (igual que en la versión anterior)
# ---------------------------------------------------------------------------

def load_index(prefix: str):
    vectors_path = f"{prefix}_vectors.npy"
    meta_path = f"{prefix}_meta.json"
    if not os.path.exists(vectors_path) or not os.path.exists(meta_path):
        sys.exit(
            f"No se encontró el índice '{prefix}'. Ejecuta primero build_index.py."
        )
    vectors = np.load(vectors_path)
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    return vectors, meta


def embed_query(query: str) -> np.ndarray:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": EMBEDDING_MODEL, "prompt": query},
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        sys.exit(
            "No se pudo conectar con Ollama. ¿Está instalado y corriendo?\n"
            "Prueba a ejecutar 'ollama list' en otra Terminal para comprobarlo."
        )

    if response.status_code == 404:
        sys.exit(
            f"Ollama respondió 404: el modelo '{EMBEDDING_MODEL}' no está descargado.\n"
            f"Ejecuta: ollama pull {EMBEDDING_MODEL}"
        )
    response.raise_for_status()
    return np.array(response.json()["embedding"], dtype=np.float32)


def cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = query_vec / np.linalg.norm(query_vec)
    matrix_norm = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix_norm @ query_norm


def format_categoria(row: dict) -> str:
    return " > ".join(
        c for c in [
            row.get("categoria_nivel1", ""),
            row.get("categoria_nivel2", ""),
            row.get("categoria_nivel3", ""),
            row.get("categoria_nivel4", ""),
        ] if c
    )


def variantes_stem(palabra: str) -> set:
    """
    Genera variantes simples de una palabra quitando terminaciones típicas
    de plural en español. Es una heurística básica (no un lematizador
    completo): en vez de intentar adivinar la forma singular "correcta",
    genera varias formas candidatas y deja que la comparación por
    intersección de conjuntos decida si alguna coincide.

    Ejemplos: "aros" -> {"aros", "aro"}
              "relojes" -> {"relojes", "reloje", "reloj"}
              "luces" -> {"luces", "luce", "luz"}
    """
    variantes = {palabra}
    if len(palabra) > LONGITUD_MINIMA_PALABRA + 1:
        if palabra.endswith("ces"):
            variantes.add(palabra[:-3] + "z")   # luces -> luz
        if palabra.endswith("es"):
            variantes.add(palabra[:-2])         # relojes -> reloj
        if palabra.endswith("s"):
            variantes.add(palabra[:-1])         # aros -> aro, pendientes -> pendiente
    return variantes


def frase_establecida(negador: str, palabra: str, meta: list, contexto: set) -> bool:
    """
    Comprueba si "negador + palabra" (ej. "sin aros") existe literalmente
    en el nombre de algún producto del catálogo, Y ese producto tiene
    relación con el resto de la búsqueda (contexto). Esto evita falsos
    positivos: "sin aros" existe en "Sujetador sin aros", pero eso no
    debería "salvar" la negación en "pendientes sin aros", porque ningún
    producto de pendientes se llama así.

    Si 'contexto' está vacío (no hay más palabras en la búsqueda aparte
    de la negación), se acepta con que exista la frase, sin más exigencia.
    """
    variantes_palabra = variantes_stem(palabra)
    for row in meta:
        nombre = row.get("nombre", "").lower()
        for variante in variantes_palabra:
            if f"{negador} {variante}" in nombre:
                nombre_tokens = tokenizar(nombre)
                if not contexto or (nombre_tokens & contexto):
                    return True
    return False


def extraer_exclusiones(query: str, meta: list) -> tuple:
    """
    Detecta patrones simples de negación ("sin X", "no X") en la búsqueda
    y separa la query en dos partes:
      - query_positiva: lo que sí se busca (incluyendo el negador si
        forma parte de un nombre de producto real, ej. "sin aros")
      - excluir: conjunto de palabras (con sus variantes de plural/singular)
        que deben EXCLUIRSE de los resultados, solo cuando la frase NO
        corresponde a un producto real relacionado con el resto de la
        búsqueda

    Es una heurística básica: solo entiende el patrón "negador + palabra
    siguiente", no negaciones complejas ni encadenadas ("ni X ni Y").

    Ejemplo: "pendientes sin aros" -> ("pendientes", {"aro", "aros"})
             porque ningún producto de pendientes se llama "sin aros"
    Ejemplo: "sujetador sin aros" -> ("sujetador sin aros", set())
             porque "sujetador sin aros" SÍ existe como producto real
    """
    palabras = query.split()
    incluir = []
    excluir = set()
    i = 0
    while i < len(palabras):
        limpio = re.sub(r"[^a-záéíóúñü0-9]", "", palabras[i].lower())
        if limpio in NEGADORES and i + 1 < len(palabras):
            siguiente = re.sub(r"[^a-záéíóúñü0-9]", "", palabras[i + 1].lower())
            resto = [p for j, p in enumerate(palabras) if j not in (i, i + 1)]
            contexto = tokenizar(" ".join(resto))

            if siguiente and not frase_establecida(limpio, siguiente, meta, contexto):
                excluir |= variantes_stem(siguiente)
                i += 2  # saltamos el negador y la palabra excluida
                continue
            # La frase existe como producto real relacionado con el resto
            # de la búsqueda: se trata como positiva, incluyendo el negador.
        incluir.append(palabras[i])
        i += 1
    return " ".join(incluir), excluir


def producto_excluido(row: dict, excluir: set) -> bool:
    """Comprueba si un producto contiene alguna de las palabras a excluir."""
    if not excluir:
        return False
    texto_producto = tokenizar(" ".join([
        row.get("nombre", ""),
        row.get("descripcion", ""),
        format_categoria(row),
        row.get("marca", ""),
    ]))
    return bool(texto_producto & excluir)


def tokenizar(texto: str) -> set:
    """
    Extrae palabras en minúsculas, ignorando puntuación, palabras
    demasiado cortas y palabras funcionales sin significado (STOPWORDS).
    Además, expande cada palabra a sus variantes de plural/singular
    (stemming básico) para que "aro" y "aros" cuenten como la misma
    palabra a efectos de búsqueda.
    """
    palabras = re.findall(r"[a-záéíóúñü0-9]+", texto.lower())
    resultado = set()
    for p in palabras:
        if len(p) >= LONGITUD_MINIMA_PALABRA and p not in STOPWORDS:
            resultado |= variantes_stem(p)
    return resultado


# ---------------------------------------------------------------------------
# 1. Boost léxico por campo, configurable
# ---------------------------------------------------------------------------

def lexical_score(query_words: set, row: dict, pesos: dict) -> float:
    """
    Calcula un score léxico por producto, sumando el peso del campo por
    cada palabra de la búsqueda que aparece en ese campo. Nombre pesa más
    que descripción, que pesa más que categoría (pesos configurables).
    """
    campos = {
        "nombre": row.get("nombre", ""),
        "descripcion": row.get("descripcion", ""),
        "categoria": format_categoria(row),
    }
    score = 0.0
    for campo, texto in campos.items():
        palabras_campo = tokenizar(texto)
        coincidencias = len(query_words & palabras_campo)
        score += coincidencias * pesos.get(campo, 0.0)
    return score


# ---------------------------------------------------------------------------
# 2. Spellcheck contra el vocabulario real del catálogo
# ---------------------------------------------------------------------------

def build_vocabulary(meta: list) -> set:
    """Construye el conjunto de palabras que existen realmente en el catálogo."""
    vocabulario = set()
    for row in meta:
        texto_completo = " ".join([
            row.get("nombre", ""),
            row.get("descripcion", ""),
            row.get("categoria_nivel1", ""),
            row.get("categoria_nivel2", ""),
            row.get("categoria_nivel3", ""),
            row.get("categoria_nivel4", ""),
            row.get("marca", ""),
        ])
        vocabulario |= tokenizar(texto_completo)
    return vocabulario


def corregir_query(query: str, vocabulario: set, cutoff: float = None):
    """
    Revisa palabra por palabra. Si una palabra ya existe en el vocabulario
    del catálogo, se deja igual. Si no, se busca la palabra más parecida
    dentro del vocabulario (por similitud de texto, no de significado) y,
    si supera el umbral 'cutoff', se sustituye.

    Devuelve la query corregida y un booleano indicando si hubo algún cambio.
    """
    if cutoff is None:
        cutoff = SPELLCHECK_CUTOFF_DEFECTO

    palabras_originales = query.split()
    palabras_corregidas = []
    hubo_cambio = False

    for palabra in palabras_originales:
        limpio = re.sub(r"[^a-záéíóúñü0-9]", "", palabra.lower())

        if len(limpio) < LONGITUD_MINIMA_PALABRA or limpio in STOPWORDS or limpio in vocabulario:
            palabras_corregidas.append(palabra)
            continue

        candidatos = get_close_matches(limpio, vocabulario, n=1, cutoff=cutoff)
        if candidatos:
            palabras_corregidas.append(candidatos[0])
            hubo_cambio = True
        else:
            palabras_corregidas.append(palabra)

    return " ".join(palabras_corregidas), hubo_cambio


# ---------------------------------------------------------------------------
# 3. Búsqueda en dos niveles: léxico primero, semántico después
# ---------------------------------------------------------------------------

def buscar(query: str, vectors: np.ndarray, meta: list, pesos: dict):
    """
    Ejecuta la búsqueda completa para una query ya decidida (original o
    corregida). Devuelve la lista de resultados ordenada y si hubo alguna
    coincidencia léxica.
    """
    query_words = tokenizar(query)
    lexical_scores = [lexical_score(query_words, row, pesos) for row in meta]
    hay_coincidencia_lexica = any(s > 0 for s in lexical_scores)

    query_vec = embed_query(query)
    sims = cosine_similarity(query_vec, vectors)

    resultados = list(zip(lexical_scores, sims, meta))

    # Nivel 1: productos con alguna coincidencia léxica real, ordenados
    # primero por score léxico y, en empate, por similitud semántica.
    nivel_1 = sorted(
        (r for r in resultados if r[0] > 0),
        key=lambda r: (r[0], r[1]),
        reverse=True,
    )
    # Nivel 2: el resto, ordenados solo por similitud semántica.
    nivel_2 = sorted(
        (r for r in resultados if r[0] == 0),
        key=lambda r: r[1],
        reverse=True,
    )

    return nivel_1 + nivel_2, hay_coincidencia_lexica


def main():
    parser = argparse.ArgumentParser(description="Busca en el catálogo con boost por campo, spellcheck, negación y ranking en dos niveles")
    parser.add_argument("--query", required=True, help="Texto de búsqueda del usuario")
    parser.add_argument("--index", default="index", help="Prefijo del índice generado")
    parser.add_argument("--top", type=int, default=5, help="Número de resultados")
    parser.add_argument("--solo-stock", action="store_true", help="Muestra solo productos con stock disponible")
    parser.add_argument("--peso-nombre", type=float, default=PESOS_DEFECTO["nombre"])
    parser.add_argument("--peso-descripcion", type=float, default=PESOS_DEFECTO["descripcion"])
    parser.add_argument("--peso-categoria", type=float, default=PESOS_DEFECTO["categoria"])
    parser.add_argument("--spellcheck-cutoff", type=float, default=SPELLCHECK_CUTOFF_DEFECTO,
                         help="Umbral de similitud (0-1) para aceptar una corrección ortográfica. Más alto = más estricto.")
    args = parser.parse_args()

    pesos = {
        "nombre": args.peso_nombre,
        "descripcion": args.peso_descripcion,
        "categoria": args.peso_categoria,
    }

    vectors, meta = load_index(args.index)

    # Paso 0: separar negaciones ("sin X", "no X") de la parte positiva
    # de la búsqueda, ANTES de hacer nada más.
    query_positiva, excluir = extraer_exclusiones(args.query, meta)

    if excluir:
        print(f"Excluyendo productos que coincidan con: {', '.join(sorted(excluir))}\n")
        mask = np.array([not producto_excluido(row, excluir) for row in meta])
        meta = [row for row, ok in zip(meta, mask) if ok]
        vectors = vectors[mask]

    if not meta:
        print("No queda ningún producto tras aplicar la exclusión.")
        return

    # Si no queda ningún término positivo (ej. la query era solo "sin aros"),
    # no tiene sentido buscar por significado: mostramos el catálogo ya
    # filtrado, sin pretender rankearlo por relevancia semántica.
    if not query_positiva.strip():
        print(
            f'"{args.query}" no tiene ningún término positivo de búsqueda '
            f"tras quitar la negación. Mostrando productos que cumplen la "
            f"exclusión, sin ranking por relevancia:\n"
        )
        ranked = [(0.0, 0.0, row) for row in meta]
        query_final = query_positiva
    else:
        query_final = query_positiva
        ranked, hay_match = buscar(query_final, vectors, meta, pesos)

        # Si no hubo NINGUNA coincidencia léxica, probamos spellcheck
        if not hay_match:
            vocabulario = build_vocabulary(meta)
            query_corregida, hubo_cambio = corregir_query(query_positiva, vocabulario, cutoff=args.spellcheck_cutoff)

            if hubo_cambio:
                print(f'Sin coincidencias exactas para "{query_positiva}". Probando con "{query_corregida}"...\n')
                query_final = query_corregida
                ranked, hay_match = buscar(query_final, vectors, meta, pesos)

    if args.solo_stock:
        ranked = [r for r in ranked if r[2].get("stock") == "Yes"]

    etiqueta_query = query_final if query_final else "(sin término positivo)"
    print(f'Resultados para: "{etiqueta_query}"' + (" (corregida)" if query_final != query_positiva else "") + "\n")

    for rank, (lex_score, sem_score, product) in enumerate(ranked[: args.top], start=1):
        precio = float(product.get("precio", 0))
        descuento = int(product.get("descuento", 0))
        precio_final = precio * (1 - descuento / 100) if descuento else precio
        tipo_match = "léxico" if lex_score > 0 else "semántico"

        print(f"{rank}. [{tipo_match}, lex={lex_score:.2f}, sem={sem_score:.3f}] {product.get('nombre')}  ({product.get('sku')})")
        print(f"    Categoría: {format_categoria(product)}")
        print(f"    Marca: {product.get('marca')}")
        if descuento:
            print(f"    Precio: {precio:.2f}€ → {precio_final:.2f}€ (-{descuento}%)")
        else:
            print(f"    Precio: {precio:.2f}€")
        print(f"    Stock: {'Disponible' if product.get('stock') == 'Yes' else 'Agotado'}")
        print()


if __name__ == "__main__":
    main()
