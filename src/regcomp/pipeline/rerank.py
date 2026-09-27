"""Second-stage reranking with FlashRank (open source, runs on CPU).

bge-m3 retrieves the top-20 candidates from pgvector; a cross-encoder reranks them and the top
5 go to the judge. A different model from the retriever also reduces the correlated-error risk
noted in docs/mutation_taxonomy.md. If reranking fails for any reason, the embedding order is
kept (graceful fallback) and the failure is counted.
"""

from pathlib import Path

MODEL = "ms-marco-MiniLM-L-12-v2"
CACHE_DIR = Path.home() / ".cache" / "flashrank"
_ranker = None
failures = 0


def _get_ranker():
    global _ranker
    if _ranker is None:  # lazy: the model loads only when first needed
        from flashrank import Ranker

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _ranker = Ranker(model_name=MODEL, cache_dir=str(CACHE_DIR))
    return _ranker


def rerank(query: str, candidates: list[tuple[str, str]], top_n: int) -> list[tuple[str, float]]:
    """candidates: [(id, text)] in embedding order. Returns [(id, score)] best first."""
    global failures
    try:
        from flashrank import RerankRequest

        passages = [{"id": cid, "text": text} for cid, text in candidates]
        ranked = _get_ranker().rerank(RerankRequest(query=query, passages=passages))
        return [(r["id"], float(r["score"])) for r in ranked[:top_n]]
    except Exception:
        failures += 1
        return [(cid, 0.0) for cid, _ in candidates[:top_n]]
