"""
intencion.py
-------------
Semantic intent classification (product search vs. general question),
using the same embedding mechanism already built for product search
and FAQ retrieval: a small set of example queries per intent, embedded
once per run, and a new query's intent is decided by which example
it's most similar to (nearest neighbor over a tiny few-shot set).

This replaces the earlier keyword-based router. The keyword approach
needed every verb conjugation ("envío" vs "enviáis") or synonym listed
by hand to be recognized; the embedding model already understands
they're related in meaning, so the example list only needs to cover
the topic once, in one natural phrasing.

Trade-off worth knowing: this costs a handful of extra embedding calls
per query (one per example, once per run) instead of being free
keyword matching — for a CLI tool with ~20 examples this is a small,
constant overhead, not something that scales with catalog size.
"""

import numpy as np

from indexado.indice import embed_query, cosine_similarity

# A handful of example queries per intent, embedded once per run and
# used as a tiny few-shot classifier. Keep these as NATURAL phrasings —
# there's no need to list conjugations or synonyms by hand anymore,
# that's exactly what the embedding model is doing for us now.
EJEMPLOS_PRODUCTO = [
    "sudadera con capucha negra",
    "quiero unas zapatillas para correr",
    "busco un collar de plata",
    "paracetamol 600mg 20 comprimidos",
    "vitamina c efervescente",
    "crema hidratante para la cara",
    "aspiradora sin cable",
    "camiseta de algodón manga corta",
    "pendientes de aro pequeños",
    "champú anticaspa",
]

EJEMPLOS_FAQ = [
    "¿cuánto tarda el envío?",
    "¿enviáis gratis a partir de algún importe?",
    "quiero hacer una devolución",
    "¿puedo devolver un producto ya abierto?",
    "¿qué métodos de pago aceptáis?",
    "¿cómo pagáis los reembolsos?",
    "¿tenéis tienda física?",
    "¿a qué hora abrís?",
    "¿los productos tienen garantía?",
    "¿cómo descargo la factura de mi pedido?",
    "necesito receta médica para este medicamento",
    "¿cómo contacto con atención al cliente?",
]


def construir_ejemplos_intencion():
    """
    Embeds the example queries for both intents once, and returns
    (vectores, etiquetas) ready to use with detectar_intencion().
    """
    textos = EJEMPLOS_PRODUCTO + EJEMPLOS_FAQ
    etiquetas = (["producto"] * len(EJEMPLOS_PRODUCTO)) + (["faq"] * len(EJEMPLOS_FAQ))
    vectores = np.array([embed_query(texto) for texto in textos], dtype=np.float32)
    return vectores, etiquetas


def detectar_intencion(query: str, vectores_ejemplos: np.ndarray, etiquetas_ejemplos: list,
                        query_vec: np.ndarray = None) -> str:
    """
    Returns "faq" or "producto": whichever few-shot example the query
    is most similar to, by cosine similarity (nearest neighbor).

    'query_vec', if given, is used instead of re-embedding 'query' —
    lets the caller reuse an embedding it already computed for the
    exact same text (see faq.py's responder_faq(), called on the same
    query right after this in the FAQ path).
    """
    if query_vec is None:
        query_vec = embed_query(query)
    sims = cosine_similarity(query_vec, vectores_ejemplos)
    mejor_idx = int(np.argmax(sims))
    return etiquetas_ejemplos[mejor_idx]
