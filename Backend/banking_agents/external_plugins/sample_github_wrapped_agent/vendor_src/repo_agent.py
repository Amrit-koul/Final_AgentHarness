"""Minimal deterministic implementation representing a reviewed vendor repository."""


def run(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("A non-empty query is required")
    return f"Vendored repository analysis: {query.strip()}"
