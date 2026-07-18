"""Qwen3-Embedding-0.6B wrapper — the single source of embedding vectors.

Why this model: best open sub-1B retrieval quality (mid-2026), 1024 dims
with Matryoshka truncation, 4k-token context (long tossups don't truncate),
and Workers AI serves the identical model (@cf/qwen/qwen3-embedding-0.6b)
so query-time embedding at the edge stays free and comparable.

Qwen3-Embedding is asymmetric: queries need the "query" prompt prefix,
documents are embedded bare. Always use encode_queries / encode_documents —
never call the underlying model directly.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib import common  # noqa: F401  (UTF-8 stdio)

MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
DIMS = 1024


class Embedder:
    def __init__(self, device: str | None = None):
        import torch
        from sentence_transformers import SentenceTransformer

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        # fp16 halves VRAM (the 4070 laptop card has 8 GB shared with the
        # desktop) with no measurable retrieval quality loss.
        model_kwargs = {"torch_dtype": torch.float16} if device == "cuda" else {}
        self.model = SentenceTransformer(
            MODEL_ID,
            device=device,
            model_kwargs=model_kwargs,
            processor_kwargs={"padding_side": "left"},
        )

    def encode_documents(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """L2-normalized fp32 vectors, shape (len(texts), DIMS)."""
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 256,
        ).astype(np.float32)

    def encode_queries(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        return self.model.encode(
            texts,
            prompt_name="query",
            batch_size=batch_size,
            normalize_embeddings=True,
        ).astype(np.float32)
