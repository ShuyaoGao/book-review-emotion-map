"""获客产出：每本书的高光桥段清单、金句卡片、拆书短视频/书单号切入点建议。

  python src/highlights.py [--confirm quoteonly] [--emo goemo]

只使用公版原文（Gutenberg）。评论只出现聚合量；代表性评论摘录 <= 25 词、不带任何用户标识，
且只写入 results/**/raw/*.text.jsonl（gitignore）与私有展示页，不进 git（Goodreads 数据不得再分发）。
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re

import numpy as np
import pandas as pd

from align import BookIndex, norm, shingles
from common import INTERIM, RESULTS, load_books_config, new_run, read_jsonl, write_json, write_jsonl
from emotion import LABEL_ZH, LABELS
from features import sentences

FEAT_ZH = {"aphorism": "金句", "romance": "爱情/表白", "death_parting": "死亡/离别", "reversal": "揭示/反转",
           "conflict": "冲突", "reunion": "重逢", "suspense": "悬疑/不安", "humor": "幽默", "sensory": "感官描写"}


def latest_scene_table(confirm, emo):
    runs = sorted(glob.glob(str(RESULTS / "analysis" / f"*_{confirm}_{emo}" / "scene_table.csv")))
    if not runs:
        raise SystemExit("先运行 pipeline.py analyze")
    return pd.read_csv(runs[-1]), runs[-1]


def quote_sentence_counts(b, confirm):
    """把引文提及落到原文句子：同一评论对同一句只计一次。"""
    idx = BookIndex(b["slug"])
    rows = {r["review_id"]: r for r in read_jsonl(INTERIM / "reviews_full" / f"{b['slug']}.jsonl")}
    sent_cache = {}
    cnt = collections.defaultdict(set)
    for m in read_jsonl(INTERIM / b["slug"] / f"mentions_{confirm}.jsonl"):
        if m["type"] != "quote":
            continue
        pid = m["pid"]
        if pid not in sent_cache:
            sent_cache[pid] = sentences(idx.paras[pid]["text"])
        rs = norm(rows[m["review_id"]]["sentences"][m["sent_idx"]][1])
        rsh = set(shingles(rs.split(), 4))
        best, bk = 0, None
        for k, s in enumerate(sent_cache[pid]):
            ov = len(rsh & set(shingles(norm(s).split(), 4)))
            if ov > best:
                best, bk = ov, k
        if bk is not None and best >= 1:
            cnt[(pid, bk)].add(m["review_id"])
    out = []
    for (pid, k), rids in cnt.items():
        p = idx.paras[pid]
        out.append({"pid": pid, "sid": p["sid"], "chapter": p["chapter"], "pos": p["pos"],
                    "sentence": sent_cache[pid][k].strip("“”\" "), "n_reviews": len(rids)})
    out.sort(key=lambda x: -x["n_reviews"])
    return out, idx


def hook_ideas(codes: dict, emo_top: list[str], is_first: bool, is_last: bool, quote: str) -> list[str]:
    q = quote if len(quote) <= 90 else quote[:88] + "…"
    ideas = []
    if is_first:
        ideas.append(f"开篇钩子：把第一句「{q}」打在封面上，3 秒内提问“这句话其实是反讽，你看出来了吗”。")
    if is_last:
        ideas.append(f"结尾余韵：用最后一句「{q}」做片尾字幕，引导评论区写“你读到这里时的感受”。")
    if codes.get("aphorism"):
        ideas.append(f"金句卡：单句上图，配一句现代场景的“翻译”，适合书单号图文与小红书封面。")
    if codes.get("romance"):
        ideas.append("情感名场面：截取表白/求婚的 2–3 句对白，做“如果是你会怎么回答”的互动。")
    if codes.get("death_parting") or "heartbreak" in emo_top:
        ideas.append("悲剧倒叙：先给结局画面，再回到起点讲“他是怎么一步步走到这里的”。")
    if codes.get("reversal"):
        ideas.append("反转悬念：用“你以为……其实……”句式，把揭示前后的两句话并排呈现。")
    if codes.get("conflict", 0) >= 2:
        ideas.append("冲突对峙：选一段针锋相对的对白做双人配音，适合短视频口播。")
    if "aesthetic" in emo_top:
        ideas.append("文笔向：读者最常见的反应是赞叹文笔，适合“一段话读三遍”的慢读视频。")
    if "amusement" in emo_top or codes.get("humor"):
        ideas.append("幽默向：把讽刺对白做成表情包或“古人吐槽”合集。")
    return ideas[:3] or ["通用：原文朗读 + 一句话点评，突出这一段被读者反复引用的理由。"]


def excerpt(text: str, n_words: int = 25) -> str:
    w = text.split()
    return " ".join(w[:n_words]) + ("…" if len(w) > n_words else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", default="quoteonly")
    ap.add_argument("--emo", default="goemo")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()
    df, src = latest_scene_table(a.confirm, a.emo)
    run = new_run("highlights", f"{a.confirm}_{a.emo}", extra={"scene_table": src})
    res = {"scene_table": src, "books": {}}
    text_rows = []
    for b in load_books_config():
        slug = b["slug"]
        sd = df[df["book"] == slug].copy()
        feats = {r["sid"]: r for r in read_jsonl(INTERIM / slug / "scene_features.jsonl")}
        emos = read_jsonl(INTERIM / slug / f"mention_emotions_{a.confirm}.jsonl")
        rows = {r["review_id"]: r for r in read_jsonl(INTERIM / "reviews_full" / f"{slug}.jsonl")}
        qs, idx = quote_sentence_counts(b, a.confirm)
        total_q = sum(x["n_reviews"] for x in qs)
        conc = {"n_quoted_sentences": len(qs), "total_review_sentence_pairs": total_q,
                "top10_share": round(sum(x["n_reviews"] for x in qs[:10]) / max(1, total_q), 4)}
        by_sid_q = collections.defaultdict(list)
        for x in qs:
            by_sid_q[x["sid"]].append(x)
        emo_by_sid = collections.defaultdict(list)
        for e in emos:
            emo_by_sid[e["sid"]].append(e)
        cand = sd[sd["mentions"] >= 3].sort_values("oe_eb", ascending=False).head(a.top)
        hl = []
        for rank, (_, r) in enumerate(cand.iterrows(), 1):
            sid = int(r["sid"])
            es = emo_by_sid.get(sid, [])
            ec = collections.Counter(k for e in es for k in LABELS if e[a.emo][k])
            emo_top = [k for k, _ in ec.most_common(3)]
            top_q = by_sid_q.get(sid, [{}])[0]
            codes = feats[sid]["codes_rule"]
            reps = []
            for e in sorted(es, key=lambda e: -e["n_reader_words"]):
                if e["bare_quote"] or e["n_reader_words"] < 6:
                    continue
                sent = rows[e["review_id"]]["sentences"][e["sent_idx"]][1]
                reps.append({"excerpt": excerpt(idx.strip_book_text(sent) if len(sent.split()) > 40 else sent),
                             "emotions": [k for k in LABELS if e[a.emo][k]]})
                if len(reps) >= 2:
                    break
            item = {"rank": rank, "sid": sid, "chapter": int(r["chapter"]), "pos": round(float(r["pos"]), 4),
                    "mentions": round(float(r["mentions"]), 2), "expected": round(float(r["expected"]), 2),
                    "heat_oe_eb": round(float(r["oe_eb"]), 3), "n_words": int(r["n_words"]),
                    "top_quote": top_q.get("sentence"), "top_quote_reviews": top_q.get("n_reviews"),
                    "scene_opening": excerpt(idx.scenes[sid]["text"], 40),
                    "features": [FEAT_ZH[k] for k in FEAT_ZH if (codes.get(k) or 0) >= 1 and k != "sensory"]
                                + (["感官描写"] if codes.get("sensory") == 2 else []),
                    "reader_emotions": {LABEL_ZH[k]: v for k, v in ec.most_common(4)},
                    "n_contexts": len(es), "bare_quote_share": round(np.mean([e["bare_quote"] for e in es]), 3) if es else None,
                    "hooks": hook_ideas(codes, emo_top, bool(r["book_first"]), bool(r["book_last"]), top_q.get("sentence") or "")}
            text_rows.append({"book": slug, "sid": sid, "representative_excerpts": reps})
            item["n_representative_excerpts"] = len(reps)
            hl.append(item)
        cards = [{"rank": k + 1, "sentence": x["sentence"], "chapter": x["chapter"], "pos": round(x["pos"], 4),
                  "n_reviews": x["n_reviews"], "sid": x["sid"]} for k, x in enumerate(qs[:12])]
        res["books"][slug] = {"title": b["title"], "title_zh": b["title_zh"], "author": b["author"],
                              "quote_concentration": conc, "highlights": hl, "quote_cards": cards}
        print(slug, conc, [(h["rank"], h["chapter"], h["mentions"], h["heat_oe_eb"]) for h in hl[:5]])
    write_jsonl(run / "raw" / "representative_excerpts.text.jsonl", text_rows)
    write_json(run / "result.json", res)


if __name__ == "__main__":
    main()
