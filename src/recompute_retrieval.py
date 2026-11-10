"""从已有的 eval_align 运行记录（raw/plot_C.jsonl）重算检索召回，不重新嵌入、不改原记录。

  python src/recompute_retrieval.py results/eval_align/2026-10-08_with_llm

结果写进新的运行目录 results/eval_align/<今天>_retrieval_recount/，并注明来源运行。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common import INTERIM, ROOT, new_run, read_jsonl, write_json
from eval_align import retrieval_recall


def main(src: str):
    src = Path(src)
    if not src.is_absolute():
        src = ROOT / src
    recs = []
    for x in read_jsonl(src / "raw" / "plot_C.jsonl"):
        x["slug"] = x["item"].split("-")[0]
        recs.append(x)
    scenes = {slug: read_jsonl(INTERIM / slug / "scenes.jsonl") for slug in {x["slug"] for x in recs}}
    run = new_run("eval_align", "retrieval_recount", extra={"source_run": str(src.relative_to(ROOT)).replace("\\", "/")})
    res = {"source_run": str(src.relative_to(ROOT)).replace("\\", "/"),
           "note": "只用原运行 raw/plot_C.jsonl 里的候选列表和金标重算，没有重新检索。",
           "plot": {"retrieval": retrieval_recall(recs, scenes)}}
    write_json(run / "result.json", res)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
