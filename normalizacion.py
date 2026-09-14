"""
normalizacion.py
------------------
Everything related to turning raw text into comparable tokens: accents,
units of measurement, plurals/singulars, and the final tokenization
used by the rest of the system.

Depends on nothing else in the project except config.py — it's the
foundation that negacion.py, scoring.py, and spellcheck.py build on.
"""

import re

from config import cargar_config

CONFIG = cargar_config()
LONGITUD_MINIMA_PALABRA = CONFIG["tokenizacion"]["longitud_minima_palabra"]
STOPWORDS = set(CONFIG["tokenizacion"]["stopwords"])


# ---------------------------------------------------------------------------
# Accents
# ---------------------------------------------------------------------------

# Accent-normalization table: only accented/umlauted vowels.
# Important: "ñ" is NOT touched — it isn't an accented vowel, it's a
# letter in its own right in Spanish ("año" must never become "ano").
TABLA_ACENTOS = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuAEIOUU")


def quitar_acentos(texto: str) -> str:
    """Normalizes accents/umlauts so that 'joyeria' and 'Joyería' count
    as the same word for search purposes, without touching 'ñ'."""
    return texto.translate(TABLA_ACENTOS)


# ---------------------------------------------------------------------------
# Units of measurement
# ---------------------------------------------------------------------------

# Unit aliases -> canonical form. Anything on the left gets normalized
# to the form on the right (e.g. "gr", "grs", "gramos" -> "g"), so that
# "250gr", "250g" and "250 gr" all count as the same quantity in search.
UNIDADES_ALIAS = {
    "gramos": "g", "gramo": "g", "grs": "g", "gr": "g", "g": "g",
    "kilogramos": "kg", "kilogramo": "kg", "kilos": "kg", "kilo": "kg", "kgs": "kg", "kg": "kg",
    "miligramos": "mg", "miligramo": "mg", "mgs": "mg", "mg": "mg",
    "microgramos": "mcg", "microgramo": "mcg", "mcg": "mcg", "ug": "mcg",
    "litros": "l", "litro": "l", "lts": "l", "lt": "l", "l": "l",
    "mililitros": "ml", "mililitro": "ml", "ml": "ml",
    "centimetros": "cm", "centimetro": "cm", "cm": "cm",
    "milimetros": "mm", "milimetro": "mm", "mm": "mm",
    "metros": "m", "metro": "m", "m": "m",
}

# Sorted from longest to shortest so the regex tries "kilogramos" before
# "kg" or "g" (otherwise "g" could wrongly "eat" part of a longer unit).
_UNIDADES_PATRON = "|".join(sorted(UNIDADES_ALIAS.keys(), key=len, reverse=True))
_REGEX_CANTIDAD = re.compile(rf"(\d+(?:[.,]\d+)?)\s*({_UNIDADES_PATRON})\b")


def normalizar_unidades(texto: str) -> str:
    """
    Merges number+unit into a single canonical form with no space and
    no decimal separator: "250 gr", "250gr", "250 gramos" -> "250g";
    "0.25kg" and "0,25kg" -> "025kg" (same token for both, regardless
    of which decimal separator was used). Must be applied to text that
    is already lowercase (it doesn't handle case on its own).

    Note: the decimal separator is dropped on purpose. The goal is for
    two ways of writing the same quantity to produce the same token
    for search matching, not to preserve the numeric value for
    arithmetic.
    """
    def _reemplazar(m):
        numero = m.group(1).replace(",", ".").replace(".", "")
        unidad = UNIDADES_ALIAS[m.group(2)]
        return numero + unidad

    return _REGEX_CANTIDAD.sub(_reemplazar, texto)


# ---------------------------------------------------------------------------
# Basic stemming (plurals/singulars)
# ---------------------------------------------------------------------------

def variantes_stem(palabra: str) -> set:
    """
    Generates simple variants of a word by stripping typical Spanish
    plural endings. This is a basic heuristic (not a full lemmatizer):
    instead of trying to guess the "correct" singular form, it
    generates several candidate forms and lets set-intersection
    comparison decide whether any of them match.

    Examples: "aros" -> {"aros", "aro"}
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


# ---------------------------------------------------------------------------
# Final tokenization
# ---------------------------------------------------------------------------

def tokenizar(texto: str) -> set:
    """
    Extracts lowercase words with accents stripped (see quitar_acentos)
    and units normalized (see normalizar_unidades), ignoring
    punctuation, words that are too short, and functional words with
    no search value (STOPWORDS). It also expands each word to its
    plural/singular variants (basic stemming) so that "aro" and "aros"
    count as the same word for search purposes.
    """
    texto_normalizado = quitar_acentos(texto.lower())
    texto_normalizado = normalizar_unidades(texto_normalizado)
    palabras = re.findall(r"[a-zñ0-9]+", texto_normalizado)
    resultado = set()
    for p in palabras:
        if len(p) >= LONGITUD_MINIMA_PALABRA and p not in STOPWORDS:
            resultado |= variantes_stem(p)
    return resultado
