"""端到端管线。每个子命令都落 results/<campaign>/<date>[_tag]/{_env_stamp.json, raw/*.jsonl, result.json}。

  python src/pipeline.py align     [--confirm mock|top1|hf:<model>] [--corpus reviews_full]
  python src/pipeline.py emotion   [--confirm mock]
  python src/pipeline.py features
  python src/pipeline.py analyze   [--confirm mock] [--emo goemo|lexicon]
  python src/pipeline.py highlights [--confirm mock]
"""
from __future__ import annotations

import argparse
import collections
import json
import re

import numpy as np
import pandas as pd

from common import INTERIM, RESULTS, load_books_config, new_run, read_jsonl, write_json, write_jsonl

TEXT_RAW_NOTE = "*.text.jsonl 含评论文本（Goodreads 数据仅限学术、不得再分发），已 gitignore"


# ---------------------------------------------------------------- align
def cmd_align(a):
    from align import align_book
    from llm import get_backend
    backend = get_backend(a.confirm) if a.confirm not in ("mock", "top1", "quoteonly") else None
    tag = a.confirm.replace(":", "_").replace("/", "_")
    run = new_run("align", tag, extra={"confirm": a.confirm, "corpus": a.corpus})
    res = {"confirm": a.confirm, "corpus": a.corpus, "books": {}}
    for b in load_books_config():
        rows = read_jsonl(INTERIM / a.corpus / f"{b['slug']}.jsonl")
        raw = []
        ments, idx = align_book(b, rows, a.confirm if backend is None else "llm", backend=backend, raw_sink=raw)
        write_jsonl(INTERIM / b["slug"] / f"mentions_{tag}.jsonl", ments)
        write_jsonl(run / "raw" / f"{b['slug']}_plot_decisions.jsonl", raw)
        write_jsonl(run / "raw" / f"{b['slug']}_mentions.jsonl", ments)
        c = collections.Counter(m["type"] for m in ments)
        uniq = {(m["review_id"], m["sid"]) for m in ments}
        res["books"][b["slug"]] = {
            "n_reviews": len(rows), "n_sentences": sum(len(r["sentences"]) for r in rows),
            "quote_sentences": c.get("quote", 0), "plot_sentences": c.get("plot", 0),
            "plot_candidates": len(raw), "unique_review_scene_pairs": len(uniq),
            "reviews_with_any_mention": len({m["review_id"] for m in ments}),
        }
        print(b["slug"], res["books"][b["slug"]], flush=True)
    if backend is not None:
        res["peak_vram_gb"] = backend.peak_vram_gb()
    write_json(run / "result.json", res)


# ---------------------------------------------------------------- emotion
def mention_contexts(b, corpus, tag):
    """被对齐的评论句 + 前后各一句。reader_text 去掉了引用的原文（情绪只看读者自己的话）。"""
    from align import BookIndex
    idx = BookIndex(b["slug"])
    rows = {r["review_id"]: r for r in read_jsonl(INTERIM / corpus / f"{b['slug']}.jsonl")}
    ments = read_jsonl(INTERIM / b["slug"] / f"mentions_{tag}.jsonl")
    out = []
    seen = set()
    for m in ments:
        key = (m["review_id"], m["sent_idx"])
        if key in seen:
            continue
        seen.add(key)
        s = rows[m["review_id"]]["sentences"]
        i = m["sent_idx"]
        ctx = " ".join(x[1] for x in s[max(0, i - 1): i + 2])
        out.append({"review_id": m["review_id"], "sent_idx": i, "type": m["type"], "sid": m["sid"],
                    "rating": rows[m["review_id"]].get("rating"), "context": ctx[:1200],
                    "reader_text": idx.strip_book_text(ctx)[:1200]})
    return out


def cmd_emotion(a):
    from emotion import LABELS, GoEmo, lexicon
    from sklearn.metrics import cohen_kappa_score
    run = new_run("emotion", a.confirm, extra={"goemo_model": "SamLowe/roberta-base-go_emotions", "threshold": 0.5})
    ge = GoEmo()
    res = {"books": {}, "agreement_lexicon_vs_goemo": {}}
    allL, allG = [], []
    for b in load_books_config():
        ctx = mention_contexts(b, a.corpus, a.confirm)
        # 只看读者自己的话；去掉原文后不足 3 个词的记为“裸引用”（只贴原文不表态），情绪全 0
        texts = [c["reader_text"] for c in ctx]
        bare = [len(t.split()) < 3 for t in texts]
        L = [lexicon(t) if not bb else {k: 0 for k in LABELS} for t, bb in zip(texts, bare)]
        G, graw = ge.label([t if t.strip() else "." for t in texts])
        G = [g if not bb else {k: 0 for k in LABELS} for g, bb in zip(G, bare)]
        recs = []
        for c, l, g, gr, bb in zip(ctx, L, G, graw, bare):
            recs.append({k: c[k] for k in ("review_id", "sent_idx", "type", "sid", "rating")} |
                        {"bare_quote": bb, "n_reader_words": len(c["reader_text"].split()),
                         "lex": l, "goemo": g, "goemo_raw": gr})
        write_jsonl(INTERIM / b["slug"] / f"mention_emotions_{a.confirm}.jsonl", recs)
        write_jsonl(run / "raw" / f"{b['slug']}_emotions.jsonl", recs)
        allL += L; allG += G
        res["books"][b["slug"]] = {"n_contexts": len(ctx), "bare_quote_share": round(float(np.mean(bare)), 4),
                                   "prevalence_lexicon": {k: round(np.mean([x[k] for x in L]), 4) for k in LABELS},
                                   "prevalence_goemo": {k: round(np.mean([x[k] for x in G]), 4) for k in LABELS}}
        print(b["slug"], len(ctx), flush=True)
    for k in LABELS:
        x = [d[k] for d in allL]; y = [d[k] for d in allG]
        if len(set(x)) < 2 or len(set(y)) < 2:
            res["agreement_lexicon_vs_goemo"][k] = {"kappa": None, "blocked_reason": "某一方方差为 0"}
        else:
            res["agreement_lexicon_vs_goemo"][k] = {"kappa": round(float(cohen_kappa_score(x, y)), 4),
                                                    "pct_agree": round(float(np.mean(np.array(x) == np.array(y))), 4)}
    write_json(run / "result.json", res)
    print(json.dumps(res["agreement_lexicon_vs_goemo"], indent=1))


# ---------------------------------------------------------------- features
def cmd_features(a):
    from features import code_thresholds, rule_codes, rule_features
    run = new_run("features", "rules")
    res = {"books": {}}
    pre = {}
    for b in load_books_config():
        scenes = read_jsonl(INTERIM / b["slug"] / "scenes.jsonl")
        pre[b["slug"]] = [(s, *rule_features(s, b["characters"])) for s in scenes]
    thr = code_thresholds([f for v in pre.values() for _, f, _ in v])
    res["code_thresholds"] = thr
    for b in load_books_config():
        scenes = [s for s, _, _ in pre[b["slug"]]]
        by_ch = collections.defaultdict(list)
        for s in scenes:
            by_ch[s["chapter"]].append(s["sid"])
        recs = []
        for s, f, aph in pre[b["slug"]]:
            codes = rule_codes(f, s, thr)
            recs.append({"book": b["slug"], "sid": s["sid"], "chapter": s["chapter"], "pos": s["pos"],
                         "n_words": s["n_words"], "chapter_open": int(s["sid"] == by_ch[s["chapter"]][0]),
                         "chapter_close": int(s["sid"] == by_ch[s["chapter"]][-1]),
                         "book_first": int(s["sid"] == 0), "book_last": int(s["sid"] == len(scenes) - 1),
                         **f, "codes_rule": codes, "aphorisms": aph[:5]})
        write_jsonl(INTERIM / b["slug"] / "scene_features.jsonl", recs)
        write_jsonl(run / "raw" / f"{b['slug']}_scene_features.jsonl", recs)
        df = pd.DataFrame([{k: v for k, v in r.items() if k not in ("codes_rule", "aphorisms")} for r in recs])
        res["books"][b["slug"]] = {"n_scenes": len(recs), "means": df.drop(columns=["book"]).mean().round(3).to_dict(),
                                   "code_prevalence": pd.DataFrame([r["codes_rule"] for r in recs]).drop(columns=["scene_type"]).mean().round(3).to_dict(),
                                   "scene_type_counts": collections.Counter(r["codes_rule"]["scene_type"] for r in recs)}
    write_json(run / "result.json", res)


# ---------------------------------------------------------------- analyze
CONT_FEATURES = ["dialogue_ratio", "conflict_per1k", "reversal_per1k", "death_parting_per1k", "reunion_per1k",
                 "romance_per1k", "sensory_per1k", "suspense_per1k", "humor_per1k", "aphorism_n", "exclaim_per1k"]


def scene_table(confirm: str, emo: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    from emotion import LABELS
    from heat import add_heat
    S, M = [], []
    for b in load_books_config():
        feats = pd.DataFrame(read_jsonl(INTERIM / b["slug"] / "scene_features.jsonl"))
        ments = read_jsonl(INTERIM / b["slug"] / f"mentions_{confirm}.jsonl")
        # 去重：同一评论对同一场景只计一次；引文分摊权重取最大
        pair = {}
        for m in ments:
            k = (m["review_id"], m["sid"])
            w = m["weight"]
            if k not in pair or w > pair[k]["weight"]:
                pair[k] = m
        cnt = collections.Counter(); cq = collections.Counter(); cp = collections.Counter()
        for (rid, sid), m in pair.items():
            cnt[sid] += m["weight"]
            (cq if m["type"] == "quote" else cp)[sid] += m["weight"]
        feats["mentions"] = feats["sid"].map(cnt).fillna(0.0)
        feats["mentions_quote"] = feats["sid"].map(cq).fillna(0.0)
        feats["mentions_plot"] = feats["sid"].map(cp).fillna(0.0)
        feats["cluster"] = b["slug"] + "-" + feats["chapter"].astype(str)
        S.append(feats)
        emos = read_jsonl(INTERIM / b["slug"] / f"mention_emotions_{confirm}.jsonl")
        for e in emos:
            M.append({"book": b["slug"], "sid": e["sid"], "type": e["type"], **{f"emo_{k}": e[emo][k] for k in LABELS}})
    df = pd.concat(S, ignore_index=True)
    df = add_heat(df)
    md = pd.DataFrame(M)
    md = md.merge(df.drop(columns=[c for c in df.columns if c.startswith("emo_")], errors="ignore"),
                  on=["book", "sid"], how="left")
    md["cluster"] = md["book"] + "-" + md["sid"].astype(str)
    return df, md


def cmd_analyze(a):
    from emotion import LABELS
    from model import effects_table, fit
    run = new_run("analysis", f"{a.confirm}_{a.emo}", extra={"confirm": a.confirm, "emotion_labeler": a.emo})
    df, md = scene_table(a.confirm, a.emo)
    res = {"n_scenes": len(df), "n_mention_contexts": len(md), "eb_alpha": df.attrs.get("eb_alpha"),
           "features": CONT_FEATURES, "heat": {}, "emotion": {}, "position_profile": {}}
    # 位置剖面：按十分位看提及密度（展示幸存者/首尾偏差）
    df["decile"] = np.minimum((df["pos"] * 10).astype(int), 9)
    prof = df.groupby("decile").agg(words=("n_words", "sum"), m=("mentions", "sum"), mq=("mentions_quote", "sum"),
                                    mp=("mentions_plot", "sum"))
    res["position_profile"] = {
        "mentions_per_10k_words": (1e4 * prof["m"] / prof["words"]).round(3).tolist(),
        "quote_per_10k_words": (1e4 * prof["mq"] / prof["words"]).round(3).tolist(),
        "plot_per_10k_words": (1e4 * prof["mp"] / prof["words"]).round(3).tolist(),
    }
    for y in ("mentions", "mentions_quote", "mentions_plot"):
        if df[y].sum() == 0:
            res["heat"][y] = {"blocked_reason": "该通道没有提及（例如 quoteonly 模式下的情节通道）"}
            continue
        for ctrl in (False, True):
            r = fit(df, y, CONT_FEATURES, controls=ctrl, family="poisson")
            res["heat"][f"{y}.{'adjusted' if ctrl else 'naive'}"] = r
            if y == "mentions":
                print(f"\n== heat {y} controls={ctrl}  dispersion={r.get('pearson_dispersion'):.1f}")
                print(effects_table(r).to_string(index=False))
    for k in LABELS:
        col = f"emo_{k}"
        if md[col].nunique() < 2 or md[col].sum() < 40:
            res["emotion"][k] = {"blocked_reason": f"阳性数 {int(md[col].sum())} < 40 或无方差（逻辑回归不稳定）"}
            continue
        r = fit(md, col, CONT_FEATURES, controls=True, family="binomial")
        r["prevalence"] = float(md[col].mean())
        res["emotion"][k] = r
    df.drop(columns=["decile"]).to_csv(run / "scene_table.csv", index=False, encoding="utf-8-sig")
    write_jsonl(run / "raw" / "scene_heat.jsonl",
                df[["book", "sid", "pos", "n_words", "mentions", "mentions_quote", "mentions_plot", "expected", "oe",
                    "oe_eb"]].to_dict("records"))
    write_json(run / "result.json", res)
    # 情绪显著项摘要
    for k, r in res["emotion"].items():
        if "effects" in r:
            sig = [(e["feature"], round(e["ratio"], 2)) for e in r["effects"] if e["q_bh"] < 0.05]
            print(f"emo {k:10s} prev={r['prevalence']:.3f} sig={sig}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--confirm", default="mock")
    ap.add_argument("--corpus", default="reviews_full")
    ap.add_argument("--emo", default="goemo")
    a = ap.parse_args()
    {"align": cmd_align, "emotion": cmd_emotion, "features": cmd_features, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
