"""汇总各 result.json → showcase/data.json，并把它内联进 showcase/index.html（离线单文件）。
同时用 matplotlib 画幻灯片用的 PNG（showcase/figs/）。

  python src/build_showcase.py

只放聚合量与公版原文；评论内容只以“读者高频用词”（跨多条评论聚合）和代理撰写的中文摘要出现，不含任何用户标识。
"""
from __future__ import annotations

import collections
import glob
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from common import INTERIM, RESULTS, ROOT, load_books_config, read_jsonl
from emotion import LABEL_ZH, LABELS

SHOW = ROOT / "showcase"
STOP = set("""a an the and or but if of to in on at by for with from as is was were be been being it its this that these those
i me my we our you your he him his she her they them their what which who whom whose there here so than then too very just
not no nor only own same such can will would should could may might must do does did doing have has had having about above
after again against all am any are because before below between both down during each few further how into more most other
out over under until up when where why while once off also book books read reading novel story chapter page pp p one quote quotes
line lines like really much many even still well get got go going make made says said say thing things way time ever never
lot bit whole every""".split())

# 代理撰写的读者反应摘要（读过代表性评论后用中文概括；不是原文，不含用户信息）
AGENT_SUMMARY = {
    ("gatsby", 2): "读者把 Nick 这句“身在其中又置身其外”当作叙述者立场的自白来引用，多半直接贴原句，少数称赞文字。",
    ("gatsby", 7): "第七章三十岁生日那段被当作全书的主题句之一；有读者说读到“驶向死亡”那句时彻底被文字折服。",
    ("gatsby", 6): "盖茨比第一次吻黛西的段落，读者多赞叹意象之美，也有人嫌文字绕、读不懂。",
    ("pride", 1): "开篇第一句被大量引用，还常被读者改写成“举世公认……”来给自己的书评开头。",
    ("pride", 34): "达西第一次求婚的台词常被原样引用，或改写成“我热烈地爱慕这本书”来表达喜爱。",
    ("pride", 50): "叙述者评价 Lydia 与 Wickham 婚姻的一句被反复摘录，读者多只贴原文、不加评论。",
    ("janeeyre", 12): "“女人和男人一样有感受”这一段被读者视为早期女性主义宣言，有人说读到这里忍不住欢呼。",
    ("janeeyre", 27): "简出走前“越孤独越要自重”一段，读者常与“法律与原则”连着引用，称赞其意志与语言。",
    ("janeeyre", 23): "“我不是鸟”被视为全书最响亮的独立宣言，读者认为这句话值得大声说出来。",
}

GROUPS = {  # 时间线着色：把 10 类情绪折成 4 组 + 未表态（色板只给 4 个分类色）
    "文笔赞叹": ["aesthetic"],
    "感动与共鸣": ["moved", "heartbreak", "comfort", "swoon", "resonance"],
    "好笑": ["amusement"],
    "冲击与愤怒": ["shock", "anger", "suspense"],
}


def latest(pattern):
    xs = sorted(glob.glob(str(RESULTS / pattern)))
    return xs[-1] if xs else None


def load_json(p):
    return json.loads(open(p, encoding="utf-8").read())


def keywords(texts, names, k=6):
    c = collections.Counter()
    nm = {n.lower() for n in names}
    for t in texts:
        for w in set(re.findall(r"[a-z]{3,}", t.lower())):
            if w not in STOP and w not in nm:
                c[w] += 1
    return [w for w, n in c.most_common(k) if n >= 2]


def main():
    books = load_books_config()
    an = load_json(latest("analysis/*_quoteonly_goemo/result.json"))
    an_lex = load_json(latest("analysis/*_quoteonly_lex/result.json"))
    an_mock = load_json(latest("analysis/*_mock_goemo/result.json"))
    st = pd.read_csv(latest("analysis/*_quoteonly_goemo/scene_table.csv"))
    hl = load_json(latest("highlights/*/result.json"))
    ev = load_json(latest("eval_align/*_with_llm/result.json"))
    eve = load_json(latest("eval_emotion/*/result.json"))
    seg = load_json(latest("segment/*/result.json"))
    sim = load_json(latest("heat_sim/*/result.json"))
    emo_run = load_json(latest("emotion/*_quoteonly/result.json"))
    align_run = load_json(latest("align/*_quoteonly/result.json"))
    ext = load_json(INTERIM / "reviews_full" / "_stats.json")

    data = {"books": {}, "meta": {}}
    for b in books:
        slug = b["slug"]
        sd = st[st["book"] == slug].sort_values("sid")
        scenes = read_jsonl(INTERIM / slug / "scenes.jsonl")
        emos = read_jsonl(INTERIM / slug / "mention_emotions_quoteonly.jsonl")
        from pipeline import mention_contexts
        ctx = {(c["review_id"], c["sent_idx"]): c["reader_text"] for c in mention_contexts(b, "reviews_full", "quoteonly")}
        by_sid = collections.defaultdict(list)
        for e in emos:
            by_sid[e["sid"]].append(e)
        hbook = hl["books"][slug]
        topq = {}
        for c in hbook["quote_cards"]:
            topq.setdefault(c["sid"], c["sentence"])
        sc_rows = []
        for _, r in sd.iterrows():
            sid = int(r["sid"])
            es = by_sid.get(sid, [])
            grp = collections.Counter()
            for e in es:
                fired = {k for k in LABELS if e["goemo"][k]}
                for g, labs in GROUPS.items():
                    if fired & set(labs):
                        grp[g] += 1
            dom = grp.most_common(1)[0][0] if grp else ("未表态" if es else "无提及")
            emo_counts = collections.Counter(LABEL_ZH[k] for e in es for k in LABELS if e["goemo"][k])
            kw = keywords([ctx.get((e["review_id"], e["sent_idx"]), "") for e in es if not e["bare_quote"]], b["characters"])
            sc_rows.append({
                "sid": sid, "ch": int(r["chapter"]), "pos": round(float(r["pos"]), 4), "w": int(r["n_words"]),
                "m": round(float(r["mentions"]), 2), "e": round(float(r["expected"]), 2), "h": round(float(r["oe_eb"]), 3),
                "g": dom, "n_ctx": len(es), "bare": round(float(np.mean([e["bare_quote"] for e in es])), 2) if es else None,
                "emo": dict(emo_counts.most_common(4)), "kw": kw,
                "open": " ".join(scenes[sid]["text"].split()[:45]) + "…",
                "q": topq.get(sid), "sum": AGENT_SUMMARY.get((slug, int(r["chapter"]))) if any(
                    h["sid"] == sid and h["rank"] <= 3 for h in hbook["highlights"]) else None,
            })
        data["books"][slug] = {"title": b["title"], "title_zh": b["title_zh"], "author": b["author"], "year": b["year"],
                               "gutenberg_id": b["gutenberg_id"], "n_reviews": ext[slug]["reviews"],
                               "n_sentences": ext[slug]["sentences"], "align": align_run["books"][slug],
                               "emotion": emo_run["books"][slug], "seg": seg["books"][slug],
                               "scenes": sc_rows, "highlights": hbook["highlights"], "cards": hbook["quote_cards"],
                               "concentration": hbook["quote_concentration"]}

    def eff(res):
        return [{"f": e["feature"], "r": round(e["ratio"], 3), "lo": round(e["ci_low"], 3), "hi": round(e["ci_high"], 3),
                 "p": e["p"], "q": e["q_bh"]} for e in res["effects"]]

    data["heat_model"] = {"adjusted": eff(an["heat"]["mentions.adjusted"]), "naive": eff(an["heat"]["mentions.naive"]),
                          "mock_adjusted": eff(an_mock["heat"]["mentions.adjusted"]),
                          "controls": an["heat"]["mentions.adjusted"]["control_coefs"],
                          "dispersion": an["heat"]["mentions.adjusted"]["pearson_dispersion"],
                          "n": an["heat"]["mentions.adjusted"]["n"], "n_clusters": an["heat"]["mentions.adjusted"]["n_clusters"]}
    data["position_profile"] = an["position_profile"]["mentions_per_10k_words"]

    # 特征 × 情绪 描述性关联：代码=1 的场景 vs =0 的场景，评论语境表达该情绪的比例之比
    feats = {}
    for b in books:
        for r in read_jsonl(INTERIM / b["slug"] / "scene_features.jsonl"):
            feats[(b["slug"], r["sid"])] = r["codes_rule"]
    rows = []
    for b in books:
        for e in read_jsonl(INTERIM / b["slug"] / "mention_emotions_quoteonly.jsonl"):
            if e["bare_quote"]:
                continue
            c = feats[(b["slug"], e["sid"])]
            rows.append({**{f"c_{k}": int((c.get(k) or 0) >= 1) for k in
                            ("aphorism", "romance", "death_parting", "reversal", "conflict", "reunion", "humor", "suspense")},
                         **{f"e_{k}": int(e["goemo"][k]) for k in LABELS}})
    md = pd.DataFrame(rows)
    mat = []
    for k in ("aphorism", "romance", "death_parting", "reversal", "conflict", "reunion", "humor", "suspense"):
        for l in LABELS:
            a1 = md[md[f"c_{k}"] == 1][f"e_{l}"]; a0 = md[md[f"c_{k}"] == 0][f"e_{l}"]
            p1 = (a1.sum() + 0.5) / (len(a1) + 1); p0 = (a0.sum() + 0.5) / (len(a0) + 1)
            mat.append({"f": k, "e": l, "rr": round(float(p1 / p0), 3), "k1": int(a1.sum()), "n1": int(len(a1)),
                        "k0": int(a0.sum()), "n0": int(len(a0))})
    data["feature_emotion"] = {"cells": mat, "n_contexts_nonbare": int(len(md)), "labeler": "GoEmotions（阈值 0.5）"}
    data["emotion_models"] = {k: ({"prev": v["prevalence"], "effects": eff(v)} if "effects" in v else {"blocked": v["blocked_reason"]})
                              for k, v in an["emotion"].items()}

    # 检索召回：2026-10-08_with_llm 的 recall_at_5 实际是 recall@8（键名错误，见该目录 NOTE.md）；
    # 若有针对该运行的重算记录（src/recompute_retrieval.py），用重算结果。
    retr = ev["plot"]["retrieval"]
    ev_dir = Path(latest("eval_align/*_with_llm/result.json")).parent
    rc = latest("eval_align/*_retrieval_recount/result.json")
    if rc:
        rcj = load_json(rc)
        if Path(rcj["source_run"]).name == ev_dir.name:
            retr = rcj["plot"]["retrieval"]
    data["eval"] = {
        "quote_A_precision": ev["quote"]["A_precision"], "quote_B": ev["quote"]["B"],
        "plot_retrieval": retr, "plot_test": ev["plot"]["test"],
        "plot_llm": {k: v["test"] for k, v in ev["plot"].get("llm", {}).items()},
        "emotion": eve["any_emotion"], "emotion_gold_rate": eve["gold_any_emotion_rate"],
        "emotion_per_label": {k: {"gold": v["gold_positive"], "lex": [v["lex"]["tp"], v["lex"]["fp"], v["lex"]["fn"]],
                                  "goemo": [v["goemo"]["tp"], v["goemo"]["fp"], v["goemo"]["fn"]]}
                              for k, v in eve["per_label"].items()},
        "segmentation": seg["validation"], "heat_sim": sim["metrics"], "heat_sim_truth_late": sim["metrics"]["truth_late_share_top20"],
        "lex_vs_goemo_kappa": emo_run["agreement_lexicon_vs_goemo"],
    }
    data["meta"] = {"built_from": {k: v for k, v in {
        "analysis": latest("analysis/*_quoteonly_goemo/result.json"), "highlights": latest("highlights/*/result.json"),
        "eval_align": latest("eval_align/*_with_llm/result.json"), "eval_emotion": latest("eval_emotion/*/result.json")}.items()},
        "label_zh": LABEL_ZH, "groups": GROUPS}
    data["meta"]["built_from"] = {k: str(v).replace(str(ROOT) + "\\", "").replace("\\", "/") for k, v in data["meta"]["built_from"].items()}
    SHOW.mkdir(exist_ok=True)
    (SHOW / "data.json").write_text(json.dumps(data, ensure_ascii=False, default=float), encoding="utf-8")
    tpl = (SHOW / "src" / "index.template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, default=float).replace("</", "<\\/"))
    (SHOW / "index.html").write_text(html, encoding="utf-8")
    print("showcase/index.html", len(html) // 1024, "KB")
    figs(data)


def figs(data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
        if any(f in x.name for x in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = f
            break
    plt.rcParams["axes.unicode_minus"] = False
    out = SHOW / "figs"; out.mkdir(exist_ok=True)
    INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
    COL = {"文笔赞叹": "#2a78d6", "感动与共鸣": "#eb6834", "好笑": "#1baf7a", "冲击与愤怒": "#eda100", "未表态": "#c3c2b7", "无提及": "#e1e0d9"}

    def style(ax):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#c3c2b7")
        ax.tick_params(colors=MUTED, labelsize=10)
        ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)

    for slug, b in data["books"].items():
        fig, axes = plt.subplots(2, 1, figsize=(12, 5.4), dpi=150, sharex=True, gridspec_kw={"height_ratios": [1, 1]})
        sc = b["scenes"]
        for ax, key, lab in ((axes[0], "m", "原始提及数"), (axes[1], "h", "位置校正热度")):
            xs = [s["pos"] for s in sc]
            ws = [max(0.004, s["w"] / sum(t["w"] for t in sc) * 0.95) for s in sc]
            ax.bar(xs, [s[key] for s in sc], width=ws, color=[COL[s["g"]] for s in sc], align="center")
            ax.set_ylabel(lab, fontsize=10, color=INK); style(ax)
        axes[1].set_xlabel("书中位置（0 = 开头，1 = 结尾）", fontsize=10, color=INK)
        axes[1].set_xlim(0, 1)
        handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COL.values()]
        axes[0].legend(handles, list(COL.keys()), ncol=6, fontsize=9, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.22))
        fig.suptitle(f"{b['title_zh']}（{b['title']}）：场景热度时间线", fontsize=13, color=INK, y=1.02)
        fig.tight_layout(); fig.savefig(out / f"timeline_{slug}.png", bbox_inches="tight"); plt.close(fig)

    FZ = {"dialogue_ratio": "对话占比", "conflict_per1k": "冲突词", "reversal_per1k": "揭示/反转词", "death_parting_per1k": "死亡/离别词",
          "reunion_per1k": "重逢词", "romance_per1k": "爱情词", "sensory_per1k": "感官词", "suspense_per1k": "悬疑词",
          "humor_per1k": "幽默词", "aphorism_n": "格言式句子数", "exclaim_per1k": "感叹号"}
    eff = sorted(data["heat_model"]["adjusted"], key=lambda e: e["r"])
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    for i, e in enumerate(eff):
        c = "#2a78d6" if e["q"] < 0.1 else MUTED
        ax.plot([e["lo"], e["hi"]], [i, i], color=c, lw=2, solid_capstyle="round")
        ax.plot(e["r"], i, "o", color=c, ms=7, mec="white", mew=2)
    ax.axvline(1, color="#c3c2b7", lw=1)
    ax.set_yticks(range(len(eff))); ax.set_yticklabels([FZ[e["f"]] for e in eff], fontsize=10, color=INK)
    ax.set_xlabel("发生率比 IRR（每 +1 SD，95% CI；蓝色 = BH q < 0.1）", fontsize=10, color=INK)
    style(ax); ax.yaxis.grid(False); ax.xaxis.grid(True, color=GRID)
    ax.set_title("哪些桥段特征预测“被引用”（控制位置、篇幅与书固定效应）", fontsize=12, color=INK)
    fig.tight_layout(); fig.savefig(out / "heat_forest.png", bbox_inches="tight"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    pp = data["position_profile"]
    ax.bar([f"{i*10}–{i*10+10}%" for i in range(10)], pp, color="#2a78d6", width=0.6)
    ax.set_ylabel("每万词被引用次数", fontsize=10, color=INK); style(ax)
    ax.set_title("书评引用的位置分布：首尾高、中间低（三本书合计）", fontsize=12, color=INK)
    plt.xticks(fontsize=9)
    fig.tight_layout(); fig.savefig(out / "position_profile.png", bbox_inches="tight"); plt.close(fig)

    sm = data["eval"]["heat_sim"]
    names = {"mentions": "原始计数", "raw_density": "按篇幅", "oe": "观测/期望", "oe_eb": "观测/期望+EB", "surv_true": "已知留存曲线（上限）"}
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    ks = list(names)
    ax.bar([names[k] for k in ks], [sm[k]["late_share_top20"]["mean"] for k in ks], color="#2a78d6", width=0.6)
    ax.axhline(data["eval"]["heat_sim_truth_late"], color="#eb6834", lw=2)
    ax.text(4.4, data["eval"]["heat_sim_truth_late"] + 0.01, "真实值", color=INK, fontsize=9, ha="right")
    ax.set_ylabel("Top20 高光中后 1/3 的占比", fontsize=10, color=INK); style(ax)
    ax.set_title("合成数据：原始计数低估后半本的高光，归一化后找回", fontsize=12, color=INK)
    plt.xticks(fontsize=9)
    fig.tight_layout(); fig.savefig(out / "heat_sim.png", bbox_inches="tight"); plt.close(fig)
    print("figs ->", out)


if __name__ == "__main__":
    main()
