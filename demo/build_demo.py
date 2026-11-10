"""showcase/data.json → demo/demo.html（离线单文件、自动播放的现场演示页）。

  python demo/build_demo.py

只用已有结果（showcase/data.json 由 src/build_showcase.py 从各 result.json 汇总而来），不重算任何东西。
与展示页同一条红线：只放聚合量、公版原文、跨 ≥2 条评论聚合的高频词、代理撰写的中文摘要；
不含评论原文和任何用户标识。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "showcase" / "data.json"
TPL = ROOT / "demo" / "demo.template.html"
OUT = ROOT / "demo" / "demo.html"

GROUPS = ["文笔赞叹", "感动与共鸣", "好笑", "冲击与愤怒", "未表态", "无提及"]
ORDER = ["gatsby", "pride", "janeeyre"]


def r(x, n=3):
    return None if x is None else round(float(x), n)


def main():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    books = {}
    for slug in ORDER:
        b = d["books"][slug]
        sc = b["scenes"]
        total = sum(s["w"] for s in sc)
        cum, rows = 0, []
        for s in sc:
            rows.append([s["sid"], s["ch"], r(cum / total, 5), r(s["w"] / total, 5),
                         s["m"], r(s["e"], 2), r(s["h"], 3), GROUPS.index(s["g"])])
            cum += s["w"]
        by_sid = {s["sid"]: s for s in sc}
        card_n = {c["sentence"]: c["n_reviews"] for c in b["cards"]}
        detail = {}

        def put(sid, extra):
            s = by_sid[sid]
            q = extra.get("top_quote") or s["q"]
            detail[str(sid)] = {
                "ch": s["ch"], "pos": s["pos"], "m": s["m"], "e": r(s["e"], 2), "h": r(s["h"], 2),
                "q": q, "qn": extra.get("top_quote_reviews") or card_n.get(q),
                "open": extra.get("scene_opening") or s["open"],
                "feat": extra.get("features", []), "hooks": extra.get("hooks", []),
                "emo": s["emo"], "nctx": s["n_ctx"], "bare": s["bare"], "kw": s["kw"], "sum": s["sum"],
            }

        for h in b["highlights"]:
            put(h["sid"], h)
        raw_peak = max(sc, key=lambda s: s["m"])["sid"]
        if str(raw_peak) not in detail:
            put(raw_peak, {})
        books[slug] = {
            "zh": b["title_zh"], "en": b["title"], "author": b["author"], "year": b["year"],
            "nReviews": b["n_reviews"], "nScenes": b["seg"]["n_scenes"], "nWords": b["seg"]["n_words"],
            "nChapters": b["seg"]["n_chapters"], "nCtx": b["emotion"]["n_contexts"],
            "bare": b["emotion"]["bare_quote_share"], "top10": b["concentration"]["top10_share"],
            "nQuoted": b["concentration"]["n_quoted_sentences"],
            "scenes": rows, "detail": detail,
            "peaks": [h["sid"] for h in b["highlights"]], "rawPeak": raw_peak,
            "cards": [{"s": c["sentence"], "ch": c["chapter"], "n": c["n_reviews"], "sid": c["sid"]} for c in b["cards"]],
        }
    ev = d["eval"]
    aph = next(e for e in d["heat_model"]["adjusted"] if e["f"] == "aphorism_n")
    glob = {
        "nReviews": sum(books[s]["nReviews"] for s in ORDER),
        "nScenes": sum(books[s]["nScenes"] for s in ORDER),
        "quoteA": [ev["quote_A_precision"]["k"], ev["quote_A_precision"]["n"]],
        "quoteRecall": [ev["quote_B"]["recall"]["k"], ev["quote_B"]["recall"]["n"]],
        "plotF1": r(ev["plot_test"]["mock_default"]["f1"], 2),
        "aph": [aph["r"], aph["lo"], aph["hi"], r(aph["q"], 3)],
        "groups": GROUPS,
        "source": d["meta"]["built_from"],
    }
    payload = json.dumps({"books": books, "order": ORDER, "g": glob}, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = TPL.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
