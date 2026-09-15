"""
faq.py
-------
Retrieval-only RAG over a small FAQ/policy dataset: reuses the same
embedding mechanism already built for product search (embed_query,
cosine_similarity from indice.py) to find the most relevant FAQ entry
and return its answer directly.

Note: this is retrieval-only — it returns the closest FAQ answer
verbatim, it does not use an LLM to rephrase or compose a new answer.
Plugging in a real LLM (e.g. a cheap API like Claude Haiku) to turn the
retrieved answer into a more natural response is a natural next step,
not required for this to be useful today.

Intent routing (deciding whether a query even IS a FAQ question) lives
in intencion.py, on purpose — a different concern from retrieval.
"""

import csv

import numpy as np

from indexado.indice import embed_query, cosine_similarity

RUTA_FAQ_POR_DEFECTO = "faq.csv"


def cargar_faq(path: str = RUTA_FAQ_POR_DEFECTO) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def construir_indice_faq(faq_items: list) -> np.ndarray:
    """
    Embeds each FAQ entry (question + answer, for richer context) and
    returns the resulting matrix. With ~15-20 short entries this is
    fast enough to (re)build on every run — no need to persist it like
    the product index.
    """
    textos = [f"{item['pregunta']} {item['respuesta']}" for item in faq_items]
    vectores = [embed_query(texto) for texto in textos]
    return np.array(vectores, dtype=np.float32)


def responder_faq(query: str, faq_items: list, faq_vectors: np.ndarray):
    """
    Returns (entrada_faq, similitud) for the closest FAQ entry to the
    query, by cosine similarity.
    """
    query_vec = embed_query(query)
    sims = cosine_similarity(query_vec, faq_vectors)
    mejor_idx = int(np.argmax(sims))
    return faq_items[mejor_idx], float(sims[mejor_idx])
