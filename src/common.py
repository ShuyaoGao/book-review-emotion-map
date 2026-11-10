"""公共工具：路径、运行目录、留痕（_env_stamp.json / raw/*.jsonl / result.json）。"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
BOOKS = DATA / "books"
INTERIM = DATA / "interim"
GOLD = DATA / "gold"
CONFIGS = ROOT / "configs"
RESULTS = ROOT / "results"


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=_default) + "\n")
            n += 1
    return n


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=_default), encoding="utf-8")


def _default(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except Exception:
        pass
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not serializable: {type(o)}")


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def git_head() -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True, timeout=5)
        head = r.stdout.strip() or None
        if head and dirty.stdout.strip():
            head += "+dirty"
        return head
    except Exception:
        return None


def _pkg_versions(names):
    out = {}
    from importlib import metadata
    for n in names:
        try:
            out[n] = metadata.version(n)
        except Exception:
            out[n] = None
    return out


def new_run(campaign: str, tag: str | None = None, extra: dict | None = None, seed: int | None = 42) -> Path:
    """创建 results/<campaign>/<YYYY-MM-DD>[_tag]/ 并写 _env_stamp.json。"""
    day = datetime.now().strftime("%Y-%m-%d")
    run = RESULTS / campaign / (day + (f"_{tag}" if tag else ""))
    (run / "raw").mkdir(parents=True, exist_ok=True)
    gpu = None
    try:
        import torch  # noqa
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
    except Exception:
        pass
    stamp = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "host": platform.node(),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "gpu": gpu,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "packages": _pkg_versions(["numpy", "pandas", "scipy", "scikit-learn", "rapidfuzz", "torch",
                                   "sentence-transformers", "transformers"]),
        "seed": seed,
        "argv": sys.argv,
        "git": git_head(),
    }
    if extra:
        stamp.update(extra)
    write_json(run / "_env_stamp.json", stamp)
    return run


def load_books_config() -> list[dict]:
    return json.loads((CONFIGS / "books.json").read_text(encoding="utf-8"))["books"]
