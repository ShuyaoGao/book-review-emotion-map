"""本机小模型冒烟：读取 export_llm_items.py 导出的条目，逐条生成，原始输出落 results/local_llm/<date>_<task>_<model>/raw/。

  python src/run_local_llm.py --items data/llm_items/gold_align.jsonl --task align --model Qwen/Qwen3-1.7B

单独进程运行（不和嵌入模型、倒排索引同进程），显存预算 <= 4GB（HFBackend 超预算会直接报错退出）。
本机 1.7B 只用来验证通路；正式标注在 GPU 服务器上用 >= 7B 的多个模型（server/llm_annotate.py）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import new_run, write_json, write_jsonl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from llm_annotate import MAX_TOKENS, parse  # noqa: E402  与服务器共用同一个解析器


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--task", required=True, choices=["features", "emotion", "align"])
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    items = [json.loads(l) for l in open(a.items, encoding="utf-8") if l.strip()]
    if a.limit:
        items = items[: a.limit]
    from llm import HFBackend
    run = new_run("local_llm", f"{a.task}_{a.model.split('/')[-1]}", extra={"model": a.model, "task": a.task,
                                                                           "items": a.items, "n": len(items)})
    be = HFBackend(a.model)
    outs = be.generate([it["prompt"] for it in items], max_tokens=MAX_TOKENS[a.task])
    rows = []
    for it, o in zip(items, outs):
        rows.append({"id": it["id"], **({"gold_item": it["gold_item"]} if "gold_item" in it else {}),
                     "raw": o.strip()[:300], "parsed": parse(a.task, o, k=len(it.get("cand_sids", [])) or 8)})
    write_jsonl(run / "raw" / f"{a.model.replace('/', '__')}.jsonl", rows)
    ok = sum(r["parsed"] is not None for r in rows)
    write_json(run / "result.json", {"model": a.model, "task": a.task, "n": len(rows), "parse_ok": ok,
                                     "peak_vram_gb": be.peak_vram_gb()})
    print(run, ok, len(rows), be.peak_vram_gb())


if __name__ == "__main__":
    main()
