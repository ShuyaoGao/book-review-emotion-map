"""文本嵌入：默认 BAAI/bge-m3（MIT 许可，中英多语）。

- 本机显存预算 <= 4GB：加载前读 nvidia-smi，空闲不足 4GB 时退回 CPU。fp16 下 bge-m3 约 1.2GB。
- 结果按 (模型, 文本哈希) 缓存在 data/cache/emb/，重复运行不重算。
- 没有 torch / sentence-transformers 时退回 TF-IDF+SVD（仅用于跑通管线，质量低，会在结果里标明 backend）。
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import numpy as np

from common import DATA

CACHE = DATA / "cache" / "emb"
DEFAULT_MODEL = os.environ.get("P8_EMBED_MODEL", "BAAI/bge-m3")
_MODEL = {}
BACKEND = {"name": None}


def gpu_free_mb() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return None


def _load(model_name: str):
    if model_name in _MODEL:
        return _MODEL[model_name]
    from sentence_transformers import SentenceTransformer
    import torch
    free = gpu_free_mb()
    device = "cuda" if (torch.cuda.is_available() and free is not None and free > 4000) else "cpu"
    m = SentenceTransformer(model_name, device=device)
    if device == "cuda":
        m = m.half()
    m.max_seq_length = 512
    _MODEL[model_name] = m
    BACKEND["name"] = f"{model_name}@{device}"
    print(f"[embed] {model_name} on {device} (gpu free {free} MB)", flush=True)
    return m


def _key(model_name: str, texts: list[str]) -> str:
    h = hashlib.sha256(model_name.encode())
    for t in texts:
        h.update(b"\x00" + t.encode("utf-8"))
    return h.hexdigest()[:24]


def embed(texts: list[str], model_name: str = DEFAULT_MODEL, batch_size: int = 32, cache: bool = True) -> np.ndarray:
    """返回 L2 归一化后的向量 (n, d)。"""
    if not texts:
        return np.zeros((0, 8), dtype=np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{_key(model_name, texts)}.npy"
    if cache and path.exists():
        BACKEND["name"] = BACKEND["name"] or f"{model_name}@cache"
        return np.load(path)
    try:
        m = _load(model_name)
        v = m.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False,
                     convert_to_numpy=True).astype(np.float32)
    except ImportError:
        v = _tfidf_fallback(texts)
        BACKEND["name"] = "tfidf-svd-fallback"
    if cache:
        np.save(path, v)
    return v


def _tfidf_fallback(texts):
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    x = TfidfVectorizer(sublinear_tf=True, min_df=1).fit_transform(texts)
    k = max(2, min(256, x.shape[1] - 1, x.shape[0] - 1))
    v = TruncatedSVD(k, random_state=0).fit_transform(x)
    v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-9
    return v.astype(np.float32)


def release():
    _MODEL.clear()
    try:
        import gc, torch
        gc.collect(); torch.cuda.empty_cache()
    except Exception:
        pass
