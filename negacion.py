"""
negacion.py
------------
Catalog-aware negation detection ("sin X", "no X"): splits a query into
the part that's actually a positive search and the part to exclude,
telling apart a generic negation ("pendientes sin aros" -> excludes
hoops) from a real product name ("sujetador sin aros" -> searched as-is).

Depends on normalizacion.py (tokenizar, variantes_stem) and indice.py
(format_categoria).
"""

import re

from config import cargar_config
from normalizacion import tokenizar, variantes_stem, quitar_acentos
from indice import format_categoria

CONFIG = cargar_config()

# Words that signal negation/exclusion. When one appears, the following
# word is NOT searched positively: it's stored as a term to EXCLUDE
# from the results.
NEGADORES = set(CONFIG["tokenizacion"]["negadores"])


def frase_establecida(negador: str, palabra: str, meta: list, contexto: set) -> bool:
    """
    Checks whether "negador + palabra" (e.g. "sin aros") exists
    literally in the name of some product in the catalog, AND that
    product is related to the rest of the query (contexto). This
    avoids false positives: "sin aros" exists in "Sujetador sin
    aros", but that shouldn't "save" the negation in "pendientes sin
    aros", because no earring product is actually named that way.

    If 'contexto' is empty (there are no other words in the query
    besides the negation), it's accepted as soon as the phrase exists,
    with no further requirement.
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
    Detects simple negation patterns ("sin X", "no X") in the query and
    splits it into two parts:
      - query_positiva: what's actually searched for (including the
        negator if it's part of a real product name, e.g. "sin aros")
      - excluir: a set of words (with their plural/singular variants)
        that must be EXCLUDED from the results, only when the phrase
        does NOT correspond to a real product related to the rest of
        the query

    This is a basic heuristic: it only understands the "negator + next
    word" pattern, not complex or chained negations ("neither X nor Y").

    Example: "pendientes sin aros" -> ("pendientes", {"aro", "aros"})
             because no earring product is named "sin aros"
    Example: "sujetador sin aros" -> ("sujetador sin aros", set())
             because "sujetador sin aros" DOES exist as a real product
    """
    palabras = query.split()
    incluir = []
    excluir = set()
    i = 0
    while i < len(palabras):
        limpio = re.sub(r"[^a-zñ0-9]", "", quitar_acentos(palabras[i].lower()))
        if limpio in NEGADORES and i + 1 < len(palabras):
            siguiente = re.sub(r"[^a-zñ0-9]", "", quitar_acentos(palabras[i + 1].lower()))
            resto = [p for j, p in enumerate(palabras) if j not in (i, i + 1)]
            contexto = tokenizar(" ".join(resto))

            if siguiente and not frase_establecida(limpio, siguiente, meta, contexto):
                excluir |= variantes_stem(siguiente)
                i += 2  # skip the negator and the excluded word
                continue
            # The phrase exists as a real product related to the rest
            # of the query: treat it as positive, keeping the negator.
        incluir.append(palabras[i])
        i += 1
    return " ".join(incluir), excluir


def producto_excluido(row: dict, excluir: set) -> bool:
    """Checks whether a product contains any of the words to exclude."""
    if not excluir:
        return False
    texto_producto = tokenizar(" ".join([
        row.get("nombre", ""),
        row.get("descripcion", ""),
        format_categoria(row),
        row.get("marca", ""),
    ]))
    return bool(texto_producto & excluir)
