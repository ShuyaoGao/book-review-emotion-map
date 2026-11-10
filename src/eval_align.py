"""对齐准确率评估（金标 = 代理标注，见 data/gold/labels/*.json 与 docs/EVALUATION.md）。

  python src/eval_align.py                          # 规则(mock) / 只取 top1 / 全判 NONE 三个基线
  python src/eval_align.py --llm hf:Qwen/Qwen3-1.7B # 加一个本机小模型确认器（冒烟，显存 <= 4GB）

情节通道（C 类）的 mock 阈值只在 dev 子集（编号 %3==0）上网格搜索，test 子集上报告。
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np

from align import TOPK, BookIndex, build_confirm_prompt, mock_confirm, name_hits
from common import GOLD, INTERIM, load_books_config, new_run, read_jsonl, write_json, write_jsonl
from embed import embed


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"k": k, "n": n, "value": round(p, 4), "ci95_low": round(c - h, 4), "ci95_high": round(c + h, 4)}


def load_labels():
    out = {}
    for b in load_books_config():
        out[b["slug"]] = json.loads((GOLD / "labels" / f"{b['slug']}.json").read_text(encoding="utf-8"))
    return out


def sid_ok(sid: int, acc, scenes) -> bool:
    for a in acc:
        if isinstance(a, int) and a == sid:
            return True
        if isinstance(a, str) and a.startswith("ch") and scenes[sid]["chapter"] == int(a[2:]):
            return True
    return False


def retrieval_recall(recs, scenes_by_book, ks=(1, 5)):
    """检索上限：前 k 个候选里有没有正确场景。k 取 1、5 和实际候选数（TOPK）。
    2026-11-10 前这里只有 recall_at_1 / recall_at_5，而 recall_at_5 实际是对全部候选（当时的 TOPK）算的；
    TOPK=8 的运行里它其实是 recall@8，见 results/eval_align/2026-10-08_with_llm/NOTE.md。"""
    pos = [x for x in recs if x["gold"] != "none"]
    n_cand = max(len(x["cand_sids"]) for x in recs)
    out = {}
    for k in sorted(set(ks) | {n_cand}):
        if k > n_cand:
            continue
        hit = sum(any(sid_ok(s, x["gold"], scenes_by_book[x["slug"]]) for s in x["cand_sids"][:k]) for x in pos)
        out[f"recall_at_{k}"] = wilson(hit, len(pos))
    out["n_candidates"] = n_cand
    out["base_rate_specific"] = wilson(len(pos), len(recs))
    return out


def score_plot(preds, golds, scenes_by_book):
    """preds/golds: list[(slug, pred_sid|None)], list[acc|'none']"""
    n = len(preds)
    correct = tp = pos_pred = pos_gold = 0
    for (slug, p), g in zip(preds, golds):
        sc = scenes_by_book[slug]
        if g == "none":
            correct += p is None
        else:
            pos_gold += 1
            if p is not None and sid_ok(p, g, sc):
                correct += 1; tp += 1
        pos_pred += p is not None
    prec = wilson(tp, pos_pred) if pos_pred else None
    rec = wilson(tp, pos_gold) if pos_gold else None
    f1 = (2 * prec["value"] * rec["value"] / (prec["value"] + rec["value"])
          if prec and rec and (prec["value"] + rec["value"]) > 0 else 0.0)
    return {"accuracy": wilson(correct, n), "precision": prec, "recall": rec, "f1": round(f1, 4),
            "n": n, "n_gold_positive": pos_gold, "n_pred_positive": pos_pred}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-raw", nargs="*", default=None, help="run_local_llm.py 或服务器输出的 raw/<model>.jsonl")
    a = ap.parse_args()
    tag = "baselines" if not a.llm_raw else "with_llm"
    run = new_run("eval_align", tag, extra={"llm_raw": a.llm_raw})
    labels = load_labels()
    items = read_jsonl(GOLD / "gold_items.jsonl")
    books = {b["slug"]: b for b in load_books_config()}
    res = {"annotator": "agent:claude-opus-5.5（代理标注，非独立人工）", "quote": {}, "plot": {}}

    # ---------------- 引文通道 ----------------
    A = [it for it in items if it["kind"] == "A"]
    res["quote"]["A_precision"] = wilson(len(A), len(A))  # 全部 A 已逐条核对为正确（见 labels 的 "A": pred_correct）
    B = [it for it in items if it["kind"] == "B"]
    tp = fp = fn = tn = 0
    rows = []
    for it in B:
        g = labels[it["slug"]]["B"][it["item"].split("-")[1]]
        pred = it["pred_pids"]
        if g == "none":
            if pred: fp += 1
            else: tn += 1
        else:
            if pred and set(pred) & set(g["quote"]): tp += 1
            elif pred: fp += 1; fn += 1
            else: fn += 1
        rows.append({"item": it["item"], "gold": g, "pred": pred})
    res["quote"]["B"] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                         "precision": wilson(tp, tp + fp), "recall": wilson(tp, tp + fn)}
    write_jsonl(run / "raw" / "quote_B.jsonl", rows)

    # ---------------- 情节通道 ----------------
    C = [it for it in items if it["kind"] == "C"]
    reviews = {}
    for slug in books:
        reviews[slug] = {r["review_id"]: r for r in read_jsonl(INTERIM / "reviews_full" / f"{slug}.jsonl")}
    idx = {slug: BookIndex(slug) for slug in books}
    scenes_by_book = {slug: idx[slug].scenes for slug in books}
    recs = []
    for it in C:
        r = reviews[it["slug"]][it["review_id"]]
        s = r["sentences"]; i = it["sent_idx"]
        recs.append({**it, "sent": s[i][1], "prev": s[i - 1][1] if i > 0 else "", "next": s[i + 1][1] if i + 1 < len(s) else "",
                     "gold": labels[it["slug"]]["C"][it["item"].split("-")[1]]})
    for slug in books:
        sub = [x for x in recs if x["slug"] == slug]
        qv = embed([x["sent"] for x in sub])
        top, sims = idx[slug].retrieve(qv, k=TOPK)
        ps = idx[slug].passages()
        for x, t, sm in zip(sub, top, sims):
            x["cand_sids"] = [int(ps[j]["sid"]) for j in t]
            x["cand_texts"] = [ps[j]["text"] for j in t]
            x["sims"] = [float(v) for v in sm]
    golds = [x["gold"] for x in recs]
    res["plot"]["retrieval"] = retrieval_recall(recs, scenes_by_book)

    def mock_preds(tau, margin, subset):
        out = []
        for x in subset:
            ch = mock_confirm(np.array(x["sims"]), name_hits(x["sent"], books[x["slug"]]["characters"]),
                              x["cand_texts"], x["spoiler"], tau=tau, margin=margin)
            out.append((x["slug"], None if ch is None else x["cand_sids"][ch]))
        return out

    dev = [x for k, x in enumerate(recs) if k % 3 == 0]
    test = [x for k, x in enumerate(recs) if k % 3 != 0]
    grid = []
    for tau, margin in itertools.product([0.45, 0.5, 0.55, 0.6, 0.65, 0.7], [0.0, 0.02, 0.04, 0.06]):
        sc = score_plot(mock_preds(tau, margin, dev), [x["gold"] for x in dev], scenes_by_book)
        grid.append({"tau": tau, "margin": margin, "dev_f1": sc["f1"], "dev_acc": sc["accuracy"]["value"]})
    best = max(grid, key=lambda g: (g["dev_f1"], g["dev_acc"]))
    res["plot"]["mock_grid_dev"] = grid
    res["plot"]["mock_best_params"] = {"tau": best["tau"], "margin": best["margin"]}
    res["plot"]["default_params_in_align_py"] = {"tau": 0.55, "margin": 0.03}

    tg = [x["gold"] for x in test]
    res["plot"]["test"] = {
        "always_none": score_plot([(x["slug"], None) for x in test], tg, scenes_by_book),
        "embed_top1": score_plot([(x["slug"], x["cand_sids"][0]) for x in test], tg, scenes_by_book),
        "mock_default": score_plot(mock_preds(0.55, 0.03, test), tg, scenes_by_book),
        "mock_tuned": score_plot(mock_preds(best["tau"], best["margin"], test), tg, scenes_by_book),
    }
    res["plot"]["all"] = {
        "always_none": score_plot([(x["slug"], None) for x in recs], golds, scenes_by_book),
        "embed_top1": score_plot([(x["slug"], x["cand_sids"][0]) for x in recs], golds, scenes_by_book),
        "mock_default": score_plot(mock_preds(0.55, 0.03, recs), golds, scenes_by_book),
    }
    raw = [{"item": x["item"], "gold": x["gold"], "cand_sids": x["cand_sids"], "sims": [round(v, 4) for v in x["sims"]],
            "spoiler": x["spoiler"]} for x in recs]

    if a.llm_raw:
        # 读取 run_local_llm.py / 服务器 llm_annotate.py 的原始输出（按 gold_item 对齐），不在本进程加载 LLM
        gold_items = {g["gold_item"]: g for g in read_jsonl(GOLD.parent / "llm_items" / "gold_align.jsonl")}
        res["plot"]["llm"] = {}
        for path in a.llm_raw:
            outs = {r.get("gold_item") or r["id"]: r for r in read_jsonl(Path(path))}
            by_id = {g["id"]: k for k, g in gold_items.items()}
            preds, choices = [], []
            for x, rr in zip(recs, raw):
                o = outs.get(x["item"]) or outs.get(next((i for i, k in by_id.items() if k == x["item"]), None))
                c = (o or {}).get("parsed") and o["parsed"].get("choice")
                cands = gold_items[x["item"]]["cand_sids"] if x["item"] in gold_items else x["cand_sids"]
                rr.setdefault("llm", {})[Path(path).stem] = c
                choices.append(c)
                preds.append((x["slug"], cands[c - 1] if c and 1 <= c <= len(cands) else None))
            name = Path(path).stem
            res["plot"]["llm"][name] = {
                "raw_file": str(Path(path).as_posix()), "parse_rate": round(sum(c is not None for c in choices) / len(recs), 4),
                "choice_distribution": {str(k): choices.count(k) for k in sorted(set(choices), key=lambda v: (v is None, v or 0))},
                "degenerate": len(set(choices)) <= 1,
                "all": score_plot(preds, golds, scenes_by_book),
                "test": score_plot([p for k, p in enumerate(preds) if k % 3 != 0], tg, scenes_by_book),
            }
    write_jsonl(run / "raw" / "plot_C.jsonl", raw)
    write_json(run / "result.json", res)
    print(json.dumps({"quote": res["quote"], "retrieval": res["plot"]["retrieval"],
                      "test": {k: (v["accuracy"]["value"], v["precision"] and v["precision"]["value"],
                                   v["recall"] and v["recall"]["value"], v["f1"]) for k, v in res["plot"]["test"].items()},
                      "best": res["plot"]["mock_best_params"],
                      "llm": {k: {kk: vv for kk, vv in v.items() if kk != "all"} for k, v in res["plot"].get("llm", {}).items()}},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
