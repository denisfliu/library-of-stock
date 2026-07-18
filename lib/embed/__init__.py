"""lib/embed — local embedding pipeline (offline pilot, July 2026).

Embeds mirror question text and topic corpora with Qwen3-Embedding-0.6B
into mirror/embeddings.sqlite (a sidecar keyed by qbreader ``_id`` so it
survives mirror re-seeds). Downstream consumers: digest clue clustering,
embedding-based related topics, and (later) the R2-partitioned online
search index.

Model choice and the query/document prompt asymmetry are centralized in
``model.py`` — every embedder and every future query path must go through
it so corpus and query vectors stay comparable.
"""
