"""
config.py
---------
Carga la configuración del proyecto desde config.yaml. Centraliza lo que
antes eran constantes sueltas en build_index.py y search.py, para que
ambos scripts usen siempre el mismo modelo/URL de Ollama y para poder
ajustar pesos, umbrales y vocabulario sin tocar código Python.

Uso:
    from config import cargar_config
    config = cargar_config()          # busca config.yaml junto a este fichero
    config = cargar_config("otro.yaml")

Si config.yaml no existe o le falta alguna clave, se usan estos valores
por defecto (para que el proyecto nunca se rompa por falta de config).
"""

import sys
from pathlib import Path

import yaml

RUTA_POR_DEFECTO = Path(__file__).resolve().parent / "config.yaml"

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
    Fusiona dos diccionarios anidados: 'overrides' gana si hay conflicto,
    pero las claves de 'base' que no se sobrescriben se conservan. Así,
    si config.yaml solo define 'pesos.nombre', el resto de valores por
    defecto (spellcheck, stopwords, etc.) no desaparecen.
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
        contenido = yaml.safe_load(f) or {}

    return _fusionar(VALORES_POR_DEFECTO, contenido)
