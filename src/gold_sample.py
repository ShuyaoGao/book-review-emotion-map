"""抽取对齐金标样本，生成人工标注用的工作表。

三类样本（每本书分层随机抽，种子固定）：
  A  quote_prec   引文通道判为引文的句子（检验精确率）
  B  quote_recall 含引号且引号内 >= 5 词的句子，不论是否被判为引文（检验召回）
  C  plot         通过情节候选过滤的句子（一半剧透句、一半非剧透句），判断它指向哪个场景或“不指向具体场景”

工作表 data/gold/sheets/*.md 含评论原文，仅本机标注用，已 gitignore；
标注结果 data/gold/gold_align.jsonl 只存 ID 与标签（不含评论文本），可提交。

标注者：本项目代理（Claude）。金标是“代理标注”，不是独立人工标注，见 docs/EVALUATION.md 的局限说明。
"""
from __future__ import annotations

import random
import re
import sys

import numpy as np

from align import BookIndex, iter_review_sentences, norm, plot_candidate
from common import GOLD, INTERIM, load_books_config, read_jsonl, write_jsonl
from embed import embed

SEED = 20261008
N_A, N_B, N_C = 20, 20, 40


def bm25_top(idx: BookIndex, query: str, k: int = 3):
    from collections import Counter
    import math
    ps = idx.passages()
    if not hasattr(idx, "_bm"):
        docs = [norm(p["text"]).split() for p in ps]
        df = Counter(t for d in docs for t in set(d))
        idx._bm = (docs, df, np.mean([len(d) for d in docs]))
    docs, df, avg = idx._bm
    q = [t for t in norm(query).split() if len(t) > 2]
    N = len(docs)
    sc = []
    for i, d in enumerate(docs):
        tf = Counter(d)
        s = 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(d) / avg))
        sc.append(s)
    return list(np.argsort(-np.array(sc))[:k])


def main():
    rng = random.Random(SEED)
    books = load_books_config()
    corpus = sys.argv[1] if len(sys.argv) > 1 else "reviews_full"
    items = []
    (GOLD / "sheets").mkdir(parents=True, exist_ok=True)
    for b in books:
        idx = BookIndex(b["slug"])
        rows = read_jsonl(INTERIM / corpus / f"{b['slug']}.jsonl")
        A, B, C_sp, C_ns = [], [], [], []
        for r, i, flag, s, prev, nxt in iter_review_sentences(rows):
            q = idx.match_quote(s)
            rec = (r["review_id"], i, flag, s, prev, nxt)
            if q and q["n_cands"] <= 3:
                A.append((rec, q))
            if any(len(x.split()) >= 5 for x in re.findall(r"[\"“]([^\"”]+)[\"”]", s)):
                B.append((rec, q))
            if not q and plot_candidate(s, flag, b["characters"]):
                (C_sp if flag == 1 else C_ns).append(rec)
        sa = rng.sample(A, min(N_A, len(A)))
        sb = rng.sample(B, min(N_B, len(B)))
        sc = rng.sample(C_sp, min(N_C // 2, len(C_sp))) + rng.sample(C_ns, min(N_C // 2, len(C_ns)))
        print(b["slug"], "pool sizes A/B/Csp/Cns", len(A), len(B), len(C_sp), len(C_ns))
        lines = [f"# 金标工作表：{b['title']}（含评论原文，仅本机，勿提交）\n"]
        for kind, sample in (("A", sa), ("B", sb)):
            for k, (rec, q) in enumerate(sample):
                iid = f"{b['slug']}-{kind}{k:02d}"
                items.append({"item": iid, "slug": b["slug"], "kind": kind, "review_id": rec[0], "sent_idx": rec[1],
                              "spoiler": rec[2], "pred_pids": q["pids"] if q else None})
                lines.append(f"## {iid}\nSENT: {rec[3]}\n")
                if q:
                    for pid in q["pids"]:
                        lines.append(f"  -> pid {pid} (sid {idx.pid2sid[pid]}): {idx.paras[pid]['text'][:300]}\n")
                else:
                    lines.append("  -> (未匹配)\n")
        ps = idx.passages()
        if sc:
            qv = embed([rec[3] for rec in sc])
            top, sims = idx.retrieve(qv, k=6)
        for k, rec in enumerate(sc):
            iid = f"{b['slug']}-C{k:02d}"
            cand = list(dict.fromkeys([int(j) for j in top[k]] + bm25_top(idx, rec[3] + " " + rec[5], 3)))
            items.append({"item": iid, "slug": b["slug"], "kind": "C", "review_id": rec[0], "sent_idx": rec[1],
                          "spoiler": rec[2], "cand_psg": cand})
            lines.append(f"## {iid}  (spoiler={rec[2]})\nPREV: {rec[4][:200]}\nSENT: {rec[3]}\nNEXT: {rec[5][:200]}\n")
            for j in cand:
                p = ps[j]
                lines.append(f"  [psg {j} | sid {p['sid']} | ch {idx.scenes[p['sid']]['chapter']}] {' '.join(p['text'].split()[:70])}\n")
        (GOLD / "sheets" / f"{b['slug']}.md").write_text("\n".join(lines), encoding="utf-8")
    write_jsonl(GOLD / "gold_items.jsonl", items)
    print("items", len(items))


if __name__ == "__main__":
    main()
