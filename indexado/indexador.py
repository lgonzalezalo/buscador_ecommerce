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

Performance notes:
- Embeddings are generated concurrently (see embed_batch in indice.py)
  instead of one sequential HTTP round-trip per product — for a
  5.000-row catalog this is the difference between minutes and tens of
  minutes.
- Progress is checkpointed every --tamano-lote products. If the
  process is interrupted (Ollama crashes, machine sleeps, Ctrl+C), the
  next run picks up where it left off instead of starting over.
"""

import argparse
import csv
import json
import os
import sys

import numpy as np

from config.config import cargar_config
from indexado.indice import embed_batch, OllamaError

CONFIG = cargar_config()
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


def _main():
    parser = argparse.ArgumentParser(description="Indexa el catálogo dummy con embeddings (Ollama local)")
    parser.add_argument("--input", required=True, help="CSV de entrada (catalogo_dummy.csv)")
    parser.add_argument("--output", default="index", help="Prefijo de los ficheros de salida")
    parser.add_argument("--hilos", type=int, default=8,
                         help="Peticiones concurrentes a Ollama durante la indexación")
    parser.add_argument("--tamano-lote", type=int, default=200,
                         help="Productos por lote antes de guardar un checkpoint")
    args = parser.parse_args()

    catalog = load_catalog(args.input)
    print(f"Catálogo cargado: {len(catalog)} productos.")

    texts = [build_text(row) for row in catalog]

    checkpoint_vectors_path = f"{args.output}_checkpoint_vectors.npy"
    checkpoint_progreso_path = f"{args.output}_checkpoint_progreso.json"

    vectores_completados = []
    inicio = 0

    if os.path.exists(checkpoint_vectors_path) and os.path.exists(checkpoint_progreso_path):
        with open(checkpoint_progreso_path, encoding="utf-8") as f:
            progreso = json.load(f)
        if progreso.get("total_catalogo") == len(catalog):
            vectores_completados = list(np.load(checkpoint_vectors_path))
            inicio = len(vectores_completados)
            print(f"Retomando desde un checkpoint anterior: {inicio}/{len(catalog)} ya generados.\n")
        else:
            print(
                "Aviso: hay un checkpoint de una ejecución anterior con un "
                "catálogo de tamaño distinto — se ignora y se empieza de cero.\n",
                file=sys.stderr,
            )

    print(f"Generando embeddings con Ollama (modelo: {EMBEDDING_MODEL}, {args.hilos} en paralelo)...\n")

    for lote_inicio in range(inicio, len(texts), args.tamano_lote):
        lote = texts[lote_inicio: lote_inicio + args.tamano_lote]

        def _progreso(completados_en_lote, base=lote_inicio):
            print(f"  Embebidos {base + completados_en_lote}/{len(texts)}", end="\r")

        vectores_lote = embed_batch(lote, hilos=args.hilos, on_progreso=_progreso)
        vectores_completados.extend(vectores_lote)
        print(f"  Embebidos {min(lote_inicio + args.tamano_lote, len(texts))}/{len(texts)}")

        # Checkpoint: if this crashes or gets interrupted mid-catalog,
        # the next run resumes from here instead of starting over.
        np.save(checkpoint_vectors_path, np.array(vectores_completados, dtype=np.float32))
        with open(checkpoint_progreso_path, "w", encoding="utf-8") as f:
            json.dump({"total_catalogo": len(catalog)}, f)

    vectors_np = np.array(vectores_completados, dtype=np.float32)
    np.save(f"{args.output}_vectors.npy", vectors_np)

    with open(f"{args.output}_meta.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    # Done — the checkpoint files served their purpose, clean them up.
    for p in (checkpoint_vectors_path, checkpoint_progreso_path):
        if os.path.exists(p):
            os.remove(p)

    print(f"\nListo. Guardado:")
    print(f"  {args.output}_vectors.npy  -> matriz {vectors_np.shape}")
    print(f"  {args.output}_meta.json    -> {len(catalog)} productos")
    print(f"\nCoste: $0 (modelo corriendo en local, sin llamadas a API de pago)")


def main():
    """
    Thin wrapper: catches Ollama-related errors from indice.py in one
    place, instead of letting a mid-catalog failure produce a raw
    traceback. Progress up to the last checkpoint is preserved either
    way — see the checkpointing logic in _main().
    """
    try:
        _main()
    except OllamaError as e:
        print(f"\nError: {e}", file=sys.stderr)
        print("El progreso ya guardado en el checkpoint no se ha perdido — "
              "vuelve a ejecutar el mismo comando para retomarlo.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
