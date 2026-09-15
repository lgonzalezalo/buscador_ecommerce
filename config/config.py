"""
config.py
---------
Loads the project configuration from config.yaml. Centralizes what
used to be loose constants in build_index.py and search.py, so both
scripts always use the same Ollama model/URL, and so weights,
thresholds, and vocabulary can be tuned without touching Python code.

Usage:
    from config import cargar_config
    config = cargar_config()          # looks for config.yaml next to this file
    config = cargar_config("otro.yaml")

If config.yaml doesn't exist or is missing a key, these default values
are used instead (so the project never breaks due to missing config).
"""

import sys
from pathlib import Path

import yaml

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "config.yaml"

# PyYAML follows YAML 1.1: 'no', 'y', 'on', 'off' are parsed as
# booleans. That breaks Spanish word lists (negator "no", stopword "y").
# We copy SafeLoader's resolvers and drop only the boolean one, so
# 'no' and 'y' stay as plain text even when unquoted in the YAML file.
class _LoaderSinBoolsImplicitos(yaml.SafeLoader):
    pass


_LoaderSinBoolsImplicitos.yaml_implicit_resolvers = {
    ch: list(resolvers)
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
for _ch in list(_LoaderSinBoolsImplicitos.yaml_implicit_resolvers):
    _LoaderSinBoolsImplicitos.yaml_implicit_resolvers[_ch] = [
        (tag, regexp)
        for tag, regexp in _LoaderSinBoolsImplicitos.yaml_implicit_resolvers[_ch]
        if tag != "tag:yaml.org,2002:bool"
    ]
    if not _LoaderSinBoolsImplicitos.yaml_implicit_resolvers[_ch]:
        del _LoaderSinBoolsImplicitos.yaml_implicit_resolvers[_ch]

VALORES_POR_DEFECTO = {
    "ollama": {
        "url": "http://localhost:11434/api/embeddings",
        "model": "bge-m3",
    },
    "pesos": {
        "nombre": 1.0,
        "descripcion": 0.5,
        "categoria": 0.3,
    },
    "spellcheck": {
        "cutoff": 0.87,
    },
    "tokenizacion": {
        "longitud_minima_palabra": 2,
        "stopwords": [
            "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
            "por", "para", "en", "y", "o", "a", "al", "es", "su", "sus",
        ],
        "negadores": ["sin", "no"],
    },
}


def _fusionar(base: dict, overrides: dict) -> dict:
    """
    Merges two nested dictionaries: 'overrides' wins on conflict, but
    'base' keys that aren't overridden are kept. This way, if
    config.yaml only defines 'pesos.nombre', the rest of the defaults
    (spellcheck, stopwords, etc.) don't disappear.
    """
    resultado = dict(base)
    for clave, valor in overrides.items():
        if isinstance(valor, dict) and isinstance(resultado.get(clave), dict):
            resultado[clave] = _fusionar(resultado[clave], valor)
        else:
            resultado[clave] = valor
    return resultado


def cargar_config(ruta=None) -> dict:
    ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO

    if not ruta.exists():
        print(f"Aviso: no se encontró '{ruta}', usando valores por defecto.", file=sys.stderr)
        return VALORES_POR_DEFECTO

    with open(ruta, encoding="utf-8") as f:
        contenido = yaml.load(f, Loader=_LoaderSinBoolsImplicitos) or {}

    return _fusionar(VALORES_POR_DEFECTO, contenido)
