"""
build_index.py (adapted for the ecommerce dummy catalog)
-----------------------------------------------------------
Generates embeddings using local Ollama, from a catalog with the
following columns: sku, nombre, descripcion, categoria_nivel1..4,
precio, stock, descuento, marca.

Prerequisites:
    1. Install Ollama: https://ollama.com
    2. Pull the model: ollama pull bge-m3
    3. Ollama must be running

Usage:
    python build_index.py --input catalogo_dummy.csv --output index
"""

import argparse
import csv
import json
import sys

import numpy as np
import requests

from config import cargar_config

CONFIG = cargar_config()
OLLAMA_URL = CONFIG["ollama"]["url"]
EMBEDDING_MODEL = CONFIG["ollama"]["model"]

COLUMNAS_REQUERIDAS = ["sku", "nombre"]


def build_text(row: dict) -> str:
    """
    Concatenates a product's relevant fields into a single text to be
    embedded. The full category path is included because it helps the
    model capture context (e.g. telling apart a "Bufanda" in
    Ropa > Accesorios from a product in a different category).
    """
    categorias = " > ".join(
        c for c in [
            row.get("categoria_nivel1", ""),
            row.get("categoria_nivel2", ""),
            row.get("categoria_nivel3", ""),
            row.get("categoria_nivel4", ""),
        ] if c
    )
    parts = [
        row.get("nombre", ""),
        row.get("marca", ""),
        categorias,
        row.get("descripcion", ""),
    ]
    return " | ".join(p.strip() for p in parts if p and p.strip())


def load_catalog(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        # Auto-detect whether the CSV uses "," or ";" as the delimiter.
        # This is needed because, depending on the system's language/
        # region, Excel sometimes saves CSVs with ";" instead of ",".
        muestra = f.read(4096)
        f.seek(0)
        try:
            dialecto = csv.Sniffer().sniff(muestra, delimiters=",;")
        except csv.Error:
            dialecto = csv.excel  # fallback: assume comma if detection fails

        reader = csv.DictReader(f, dialect=dialecto)
        rows = list(reader)

    if not rows:
        sys.exit(f"El CSV '{path}' está vacío.")
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in rows[0]]
    if faltantes:
        sys.exit(
            f"Faltan columnas obligatorias en el CSV: {faltantes}\n"
            f"Columnas encontradas: {list(rows[0].keys())}\n"
            f"Comprueba que el separador sea ',' o ';' y que la cabecera sea correcta."
        )
    return rows


def embed_text(text: str) -> list[float]:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": EMBEDDING_MODEL, "prompt": text},
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
    return response.json()["embedding"]


def main():
    parser = argparse.ArgumentParser(description="Indexa el catálogo dummy con embeddings (Ollama local)")
    parser.add_argument("--input", required=True, help="CSV de entrada (catalogo_dummy.csv)")
    parser.add_argument("--output", default="index", help="Prefijo de los ficheros de salida")
    args = parser.parse_args()

    catalog = load_catalog(args.input)
    print(f"Catálogo cargado: {len(catalog)} productos.")
    print(f"Generando embeddings con Ollama (modelo: {EMBEDDING_MODEL})...\n")

    texts = [build_text(row) for row in catalog]
    all_vectors = []

    for i, text in enumerate(texts, start=1):
        vector = embed_text(text)
        all_vectors.append(vector)
        if i % 50 == 0 or i == len(texts):
            print(f"  Embebidos {i}/{len(texts)}")

    vectors_np = np.array(all_vectors, dtype=np.float32)
    np.save(f"{args.output}_vectors.npy", vectors_np)

    with open(f"{args.output}_meta.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\nListo. Guardado:")
    print(f"  {args.output}_vectors.npy  -> matriz {vectors_np.shape}")
    print(f"  {args.output}_meta.json    -> {len(catalog)} productos")
    print(f"\nCoste: $0 (modelo corriendo en local, sin llamadas a API de pago)")


if __name__ == "__main__":
    main()
