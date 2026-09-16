"""
search.py (field boost, spellcheck, and two-tier ranking)
------------------------------------------------------------------------
Changes from the earlier version:

1. Configurable per-field boost: nombre, descripcion, and categoria
   carry different weights (nombre > descripcion > categoria),
   adjustable via a constant or via the command line.
2. Spellcheck against the catalog's actual vocabulary: if a search has
   no lexical match at all, it checks whether any word closely
   resembles a word from the catalog, and if so, corrects it and
   re-runs the search automatically.
3. Two-tier ranking: products with a real lexical match are always
   shown first (sorted among themselves by semantic similarity), and
   the rest afterward, sorted only by semantic similarity. Pure
   semantic similarity can never "overtake" an exact lexical match.

Usage:
    python search.py --query "colar de plata" --top 5
    python search.py --query "algo para el frio" --top 5 --peso-nombre 1.5
"""

import argparse
import sys

import numpy as np

from config.config import cargar_config
from busqueda.normalizacion import tokenizar, variantes_stem
from indexado.indice import (
    load_index, embed_query, cosine_similarity, format_categoria,
    OllamaError, IndiceError,
)
from busqueda.negacion import extraer_exclusiones, producto_excluido
from busqueda.spellcheck import build_vocabulary, corregir_query, SPELLCHECK_CUTOFF_DEFECTO
from busqueda.variantes import agrupar_por_padre
from faq.intencion import detectar_intencion, construir_ejemplos_intencion
from faq.faq import cargar_faq, construir_indice_faq, responder_faq, RUTA_FAQ_POR_DEFECTO, FaqNoEncontradaError

CONFIG = cargar_config()

# Default field-boost weights. The higher the value, the more a match
# in that field is "rewarded". They come from config.yaml; they can be
# overridden on a per-run basis from the command line without touching
# the file.
PESOS_DEFECTO = CONFIG["pesos"]

# Minimum semantic similarity to trust a purely semantic result (no
# lexical match at all) as a genuine match, rather than "the least bad
# guess we had". See confianza.umbral_semantico in config.yaml.
UMBRAL_CONFIANZA_DEFECTO = CONFIG["confianza"]["umbral_semantico"]


def _numero_seguro(valor, tipo, defecto=0):
    """
    Converts 'valor' to 'tipo' (float/int), falling back to 'defecto'
    if the field is missing, empty, or malformed (e.g. a blank price
    cell, or a discount written as "10.0" where an int is expected).
    A single bad row in the catalog shouldn't crash the whole search.
    """
    try:
        return tipo(valor)
    except (TypeError, ValueError):
        try:
            return tipo(float(valor))
        except (TypeError, ValueError):
            return defecto


# ---------------------------------------------------------------------------
# 1. Configurable per-field lexical boost
# ---------------------------------------------------------------------------

def lexical_score(query_words: set, row: dict, pesos: dict) -> float:
    """
    Computes a lexical score for a product, adding the field's weight
    for each query word that appears in that field. Name is weighted
    more heavily than description, which is weighted more heavily than
    category (weights are configurable).
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
# 2. Two-tier search: lexical first, semantic second
# ---------------------------------------------------------------------------

def buscar(query: str, vectors: np.ndarray, meta: list, pesos: dict, query_vec: np.ndarray = None):
    """
    Runs the full search for a query that's already been decided
    (original or corrected). Returns the sorted list of results and
    whether there was any lexical match.

    'query_vec', if given, is used instead of re-embedding 'query' —
    the caller must only pass this when it already computed the
    embedding for this EXACT string elsewhere (e.g. intent
    classification, when negation extraction didn't change anything).
    """
    query_words = tokenizar(query)
    lexical_scores = [lexical_score(query_words, row, pesos) for row in meta]
    hay_coincidencia_lexica = any(s > 0 for s in lexical_scores)

    if query_vec is None:
        query_vec = embed_query(query)
    sims = cosine_similarity(query_vec, vectors)

    resultados = list(zip(lexical_scores, sims, meta))

    # Tier 1: products with a real lexical match, sorted first by
    # lexical score and, on a tie, by semantic similarity.
    nivel_1 = sorted(
        (r for r in resultados if r[0] > 0),
        key=lambda r: (r[0], r[1]),
        reverse=True,
    )
    # Tier 2: everything else, sorted only by semantic similarity.
    nivel_2 = sorted(
        (r for r in resultados if r[0] == 0),
        key=lambda r: r[1],
        reverse=True,
    )

    return nivel_1 + nivel_2, hay_coincidencia_lexica


def _main():
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
    parser.add_argument("--faq", default=RUTA_FAQ_POR_DEFECTO, help="CSV de preguntas frecuentes")
    parser.add_argument("--intencion", choices=["auto", "producto", "faq"], default="auto",
                         help="Forzar el tipo de consulta en vez de detectarlo automáticamente (útil para demos/tests)")
    parser.add_argument("--umbral-confianza", type=float, default=UMBRAL_CONFIANZA_DEFECTO,
                         help="Similitud semántica mínima (0-1) para considerar un resultado puramente semántico como una coincidencia real, no 'lo menos malo que había'.")
    args = parser.parse_args()

    # Step -1: decide whether this is a product search or a general
    # question (shipping, returns, payment...), BEFORE loading the
    # product index at all — a FAQ query doesn't need it.
    intencion = args.intencion
    query_vec_original = None
    if intencion == "auto":
        ejemplos_vectores, ejemplos_etiquetas = construir_ejemplos_intencion()
        # Embed the query once here; if we end up on the FAQ path below,
        # this exact same text gets reused instead of asking Ollama for
        # the same embedding a second time.
        query_vec_original = embed_query(args.query)
        intencion = detectar_intencion(args.query, ejemplos_vectores, ejemplos_etiquetas,
                                        query_vec=query_vec_original)

    if intencion == "faq":
        faq_items = cargar_faq(args.faq)
        faq_vectors = construir_indice_faq(faq_items)
        mejor, similitud = responder_faq(args.query, faq_items, faq_vectors, query_vec=query_vec_original)

        print(f'Consulta detectada como pregunta general (no de producto).\n')
        print(f"P: {mejor['pregunta']}")
        print(f"R: {mejor['respuesta']}")
        print(f"\n(similitud: {similitud:.3f})")
        return

    pesos = {
        "nombre": args.peso_nombre,
        "descripcion": args.peso_descripcion,
        "categoria": args.peso_categoria,
    }

    vectors, meta = load_index(args.index)

    # Step 0: split off any negation ("sin X", "no X") from the
    # positive part of the query, BEFORE doing anything else.
    query_positiva, excluir = extraer_exclusiones(args.query, meta)

    if excluir:
        print(f"Excluyendo productos que coincidan con: {', '.join(sorted(excluir))}\n")
        mask = np.array([not producto_excluido(row, excluir) for row in meta])
        meta = [row for row, ok in zip(meta, mask) if ok]
        vectors = vectors[mask]

    if not meta:
        print("No queda ningún producto tras aplicar la exclusión.")
        return

    # If there's no positive term left (e.g. the query was just "sin
    # aros"), searching by meaning makes no sense: show the already
    # filtered catalog without pretending to rank it by relevance.
    baja_confianza = False
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
        # Reuse the embedding already computed for intent classification
        # ONLY if negation extraction didn't change the text at all —
        # otherwise this is a different string and needs its own embedding.
        reutilizar_vec = query_vec_original if query_final == args.query else None
        ranked, hay_match = buscar(query_final, vectors, meta, pesos, query_vec=reutilizar_vec)

        # If there was NO lexical match at all, try spellcheck
        if not hay_match:
            vocabulario = build_vocabulary(meta)
            query_corregida, hubo_cambio = corregir_query(query_positiva, vocabulario, cutoff=args.spellcheck_cutoff)

            if hubo_cambio:
                print(f'Sin coincidencias exactas para "{query_positiva}". Probando con "{query_corregida}"...\n')
                query_final = query_corregida
                ranked, hay_match = buscar(query_final, vectors, meta, pesos)

        # Still no lexical match after spellcheck, AND the best purely
        # semantic score is weak: this isn't a confident result, it's
        # the least-bad guess among mediocre candidates (e.g. searching
        # for something the catalog simply doesn't have).
        if not hay_match and ranked and ranked[0][1] < args.umbral_confianza:
            baja_confianza = True

    if args.solo_stock:
        ranked = [r for r in ranked if r[2].get("stock") == "Yes"]

    # Group by parent product, so "--top N" means N distinct products,
    # not N rows that could all be different presentations of the same
    # item (e.g. 5 doses of the same painkiller).
    agrupado = agrupar_por_padre(ranked, meta)

    if args.solo_stock:
        agrupado = [
            (lex, sem, row, [h for h in hermanas if h.get("stock") == "Yes"])
            for lex, sem, row, hermanas in agrupado
        ]

    etiqueta_query = query_final if query_final else "(sin término positivo)"
    if baja_confianza:
        print(
            f'No encontramos ninguna coincidencia clara para "{etiqueta_query}". '
            f"Esto es lo más parecido que tenemos, por si te interesa:\n"
        )
    else:
        print(f'Resultados para: "{etiqueta_query}"' + (" (corregida)" if query_final != query_positiva else "") + "\n")

    for rank, (lex_score, sem_score, product, hermanas) in enumerate(agrupado[: args.top], start=1):
        precio = _numero_seguro(product.get("precio", 0), float)
        descuento = _numero_seguro(product.get("descuento", 0), int)
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

        if hermanas:
            print(f"    Otras presentaciones ({len(hermanas)}):")
            for h in hermanas:
                precio_h = _numero_seguro(h.get("precio", 0), float)
                descuento_h = _numero_seguro(h.get("descuento", 0), int)
                precio_h_final = precio_h * (1 - descuento_h / 100) if descuento_h else precio_h
                stock_h = "Disponible" if h.get("stock") == "Yes" else "Agotado"
                valor_h = h.get("valor_variante") or h.get("nombre")
                if descuento_h:
                    precio_txt = f"{precio_h:.2f}€ → {precio_h_final:.2f}€ (-{descuento_h}%)"
                else:
                    precio_txt = f"{precio_h:.2f}€"
                print(f"      - {valor_h}: {precio_txt} · {stock_h} ({h.get('sku')})")
        print()


def main():
    """
    Thin wrapper around _main(): this is the only place in the search
    pipeline that's allowed to end the process. Every library function
    below (embed_query, load_index, cargar_faq...) raises an exception
    instead of calling sys.exit() itself, so they stay usable from
    anywhere else (a test, a future web API) without taking the whole
    process down on a single failure.
    """
    try:
        _main()
    except (OllamaError, IndiceError, FaqNoEncontradaError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
