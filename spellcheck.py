"""
spellcheck.py
--------------
Spelling correction against the catalog's actual vocabulary (not a
generic Spanish dictionary): builds the set of words that genuinely
exist in the catalog, and corrects a query toward the closest matching
word only when it doesn't match anything that already exists.

Depends on normalizacion.py (tokenizar, quitar_acentos, STOPWORDS,
LONGITUD_MINIMA_PALABRA).
"""

import re
from difflib import get_close_matches

from config import cargar_config
from normalizacion import tokenizar, quitar_acentos, STOPWORDS, LONGITUD_MINIMA_PALABRA

CONFIG = cargar_config()
SPELLCHECK_CUTOFF_DEFECTO = CONFIG["spellcheck"]["cutoff"]


def build_vocabulary(meta: list) -> set:
    """Builds the set of words that genuinely exist in the catalog."""
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
    Checks the query word by word. If a word already exists in the
    catalog's vocabulary, it's left unchanged. If not, it looks for the
    closest matching word within the vocabulary (by text similarity,
    not by meaning) and, if it's above the 'cutoff' threshold,
    substitutes it.

    Returns the corrected query and a boolean flag indicating whether
    any change was made.
    """
    if cutoff is None:
        cutoff = SPELLCHECK_CUTOFF_DEFECTO

    palabras_originales = query.split()
    palabras_corregidas = []
    hubo_cambio = False

    for palabra in palabras_originales:
        limpio = re.sub(r"[^a-zñ0-9]", "", quitar_acentos(palabra.lower()))

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
