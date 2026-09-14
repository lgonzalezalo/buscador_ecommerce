"""
variantes.py
-------------
Groups search results by producto_padre_id, so that "top N" means N
distinct products, not N rows that might all be different presentations
of the same item (e.g. 5 doses of the same painkiller). Also attaches
each result's sibling variants (other presentations of the same
product), pulled from the full catalog rather than only from the rows
that happened to match the query — the same way a real ecommerce page
shows "other sizes/formats available" even if you searched a specific one.

Backward-compatible with catalogs that don't model parent-child
variants (like the general ecommerce dummy catalog): when a row has no
producto_padre_id, it falls back to using its own sku as the grouping
key, so it simply becomes a group of size one.
"""


def obtener_padre_id(row: dict) -> str:
    """
    Groups by producto_padre_id when present; falls back to sku for
    catalogs that don't model parent-child variants (each product is
    then its own one-item group).
    """
    return row.get("producto_padre_id") or row.get("sku", "")


def agrupar_por_padre(ranked: list, meta: list) -> list:
    """
    Collapses a ranked result list so each PARENT product appears only
    once, keeping the score/position of its best-ranked variant, and
    attaching its sibling variants (from the full catalog, not just the
    ones that matched the query) for display.

    'ranked' is the list of (lex_score, sem_score, row) tuples as
    returned by buscar(), already sorted by relevance.
    'meta' is the full catalog (used to find ALL siblings of a matched
    parent, even ones that didn't match the query themselves).

    Returns a list of (lex_score, sem_score, row, hermanas) tuples,
    where 'hermanas' is the list of sibling rows (excluding the
    representative itself), sorted by valor_variante.
    """
    todas_por_padre = {}
    for row in meta:
        todas_por_padre.setdefault(obtener_padre_id(row), []).append(row)

    vistos = set()
    resultado = []
    for lex_score, sem_score, row in ranked:
        padre_id = obtener_padre_id(row)
        if padre_id in vistos:
            continue
        vistos.add(padre_id)

        hermanas = [
            r for r in todas_por_padre.get(padre_id, [])
            if r.get("sku") != row.get("sku")
        ]
        hermanas.sort(key=lambda r: r.get("valor_variante", ""))

        resultado.append((lex_score, sem_score, row, hermanas))
    return resultado
