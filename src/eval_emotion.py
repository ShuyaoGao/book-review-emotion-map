"""情绪打标器评估（代理标注金标）。

  python src/eval_emotion.py sample   # 抽 90 条评论语境：45 条任一打标器有输出 + 45 条随机非裸引用，生成工作表
  python src/eval_emotion.py score    # 读 data/gold/labels/emotion.json，算每个标签的精确率/召回率与“任一情绪”检出

工作表 data/gold/sheets/emotion.md 含评论原文（gitignore）；标注只存 ID 与标签。
"""
from __future__ import annotations

import json
import random
import sys

from common import GOLD, INTERIM, load_books_config, new_run, read_jsonl, write_json, write_jsonl
from emotion import LABELS
from eval_align import wilson

SEED = 7
CONFIRM = "quoteonly"


def load_all():
    from pipeline import mention_contexts
    rows = []
    for b in load_books_config():
        ctx = {(c["review_id"], c["sent_idx"]): c for c in mention_contexts(b, "reviews_full", CONFIRM)}
        for e in read_jsonl(INTERIM / b["slug"] / f"mention_emotions_{CONFIRM}.jsonl"):
            c = ctx[(e["review_id"], e["sent_idx"])]
            rows.append({**e, "book": b["slug"], "context": c["context"], "reader_text": c["reader_text"]})
    return rows


def sample():
    rng = random.Random(SEED)
    rows = load_all()
    fired = [r for r in rows if not r["bare_quote"] and (any(r["lex"].values()) or any(r["goemo"].values()))]
    rest = [r for r in rows if not r["bare_quote"] and r not in fired]
    s = rng.sample(fired, 45) + rng.sample(rest, 45)
    rng.shuffle(s)
    items, lines = [], ["# 情绪金标工作表（含评论原文，仅本机，勿提交）\n"]
    for k, r in enumerate(s):
        iid = f"E{k:02d}"
        items.append({"item": iid, "book": r["book"], "review_id": r["review_id"], "sent_idx": r["sent_idx"],
                      "stratum": "fired" if r in fired else "random"})
        lines.append(f"## {iid} [{r['book']}]\nCTX: {r['context'][:700]}\nREADER: {r['reader_text'][:400]}\n")
    write_jsonl(GOLD / "emotion_items.jsonl", items)
    (GOLD / "sheets" / "emotion.md").write_text("\n".join(lines), encoding="utf-8")
    print(len(items))


def score():
    run = new_run("eval_emotion")
    items = read_jsonl(GOLD / "emotion_items.jsonl")
    gold = json.loads((GOLD / "labels" / "emotion.json").read_text(encoding="utf-8"))["labels"]
    rows = {(r["book"], r["review_id"], r["sent_idx"]): r for r in load_all()}
    res = {"annotator": "agent:claude-opus-5.5（代理标注）", "n": len(items), "per_label": {}, "any_emotion": {}}
    G = []
    for it in items:
        g = set(gold[it["item"]])
        r = rows[(it["book"], it["review_id"], it["sent_idx"])]
        G.append((it, g, r))
    for lab in LABELS:
        res["per_label"][lab] = {"gold_positive": sum(lab in g for _, g, _ in G)}
        for name in ("lex", "goemo"):
            tp = sum(lab in g and r[name][lab] == 1 for _, g, r in G)
            fp = sum(lab not in g and r[name][lab] == 1 for _, g, r in G)
            fn = sum(lab in g and r[name][lab] == 0 for _, g, r in G)
            res["per_label"][lab][name] = {"tp": tp, "fp": fp, "fn": fn,
                                           "precision": wilson(tp, tp + fp), "recall": wilson(tp, tp + fn)}
    for name in ("lex", "goemo"):
        tp = sum(bool(g) and any(r[name].values()) for _, g, r in G)
        fp = sum((not g) and any(r[name].values()) for _, g, r in G)
        fn = sum(bool(g) and not any(r[name].values()) for _, g, r in G)
        # 微平均（标签级）
        mtp = sum(res["per_label"][l][name]["tp"] for l in LABELS)
        mfp = sum(res["per_label"][l][name]["fp"] for l in LABELS)
        mfn = sum(res["per_label"][l][name]["fn"] for l in LABELS)
        res["any_emotion"][name] = {"precision": wilson(tp, tp + fp), "recall": wilson(tp, tp + fn),
                                    "micro_precision": wilson(mtp, mtp + mfp), "micro_recall": wilson(mtp, mtp + mfn)}
    res["gold_any_emotion_rate"] = {
        "fired_stratum": wilson(sum(bool(g) for it, g, _ in G if it["stratum"] == "fired"), sum(it["stratum"] == "fired" for it, _, _ in G)),
        "random_stratum": wilson(sum(bool(g) for it, g, _ in G if it["stratum"] == "random"), sum(it["stratum"] == "random" for it, _, _ in G)),
    }
    write_jsonl(run / "raw" / "emotion_gold_vs_pred.jsonl",
                [{"item": it["item"], "gold": sorted(g), "lex": [k for k, v in r["lex"].items() if v],
                  "goemo": [k for k, v in r["goemo"].items() if v]} for it, g, r in G])
    write_json(run / "result.json", res)
    print(json.dumps(res["any_emotion"], indent=1, ensure_ascii=False))
    print(json.dumps(res["gold_any_emotion_rate"], ensure_ascii=False))
    for l in LABELS:
        p = res["per_label"][l]
        print(l, p["gold_positive"], "lex", p["lex"]["tp"], p["lex"]["fp"], p["lex"]["fn"], "| goemo", p["goemo"]["tp"], p["goemo"]["fp"], p["goemo"]["fn"])


if __name__ == "__main__":
    {"sample": sample, "score": score}[sys.argv[1]]()
