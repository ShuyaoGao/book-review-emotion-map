"""核心函数的单元测试（不依赖下载的数据集、不加载模型）。"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "adapters"))
sys.path.insert(0, str(ROOT / "server"))


def test_norm_and_shingles():
    from align import norm, shingles
    assert norm("“I am no bird,” she said—") == "i am no bird she said"
    assert shingles("a b c d e f".split(), 5) == ["a b c d e", "b c d e f"]


def test_strip_illustrations_nested():
    from segment import strip_illustrations
    t = "x [Illustration: “He came” [_Copyright 1894_]] y [Illustration] z"
    assert strip_illustrations(t).split() == ["x", "y", "z"]


def test_dialogue_ratio():
    from segment import dialogue_ratio
    assert dialogue_ratio("“abc” def") == 0.5
    assert dialogue_ratio("plain text") == 0.0


def test_seg_metrics_perfect_and_random():
    from segment import seg_metrics
    true = {9, 19, 29}
    m = seg_metrics(true, set(true), 40)
    assert m["pk"] == 0 and m["windowdiff"] == 0 and m["boundary_recall_tol2"] == 1
    m2 = seg_metrics(true, {2, 3, 4}, 40)
    assert m2["pk"] > 0


def test_tile_respects_min_length():
    from segment import tile
    words = [100] * 20
    s = np.ones(19); s[9] = 0.0   # 一个明显的低谷
    cuts = tile(words, s, min_w=300, max_w=5000)
    assert 9 in cuts
    bounds = [0] + [c + 1 for c in cuts] + [20]
    assert all((bounds[k + 1] - bounds[k]) * 100 >= 300 for k in range(len(bounds) - 1))


def test_eb_alpha_and_heat_shrinkage():
    from heat import eb_alpha
    E = np.full(200, 5.0)
    rng = np.random.default_rng(0)
    O = rng.poisson(E)            # 纯 Poisson：没有额外方差 → 先验极强（a 很大）
    assert eb_alpha(O, E) > 50
    O2 = rng.poisson(E * rng.gamma(1.0, 1.0, 200))   # 过度离散
    assert eb_alpha(O2, E) < 5


def test_survival_curve_endpoints():
    from heat import survival_curve
    s = survival_curve(np.array([0.0, 1.0]), 0.3, 0.7)
    assert abs(s[0] - 1) < 1e-9 and abs(s[1] - 0.3) < 1e-9


def test_simulation_normalization_recovers_late_highlights():
    from heat import simulate
    summ, _ = simulate(reps=4, n_scenes=120, n_readers=2000)
    truth = summ["truth_late_share_top20"]
    assert summ["mentions"]["late_share_top20"]["mean"] < truth - 0.08
    assert abs(summ["oe_eb"]["late_share_top20"]["mean"] - truth) < 0.08


def test_bh_monotone():
    from model import bh
    q = bh(np.array([0.01, 0.04, 0.03, 0.5]))
    assert np.all(q >= np.array([0.01, 0.04, 0.03, 0.5]) - 1e-12) and q.max() <= 1


def test_poisson_fit_recovers_effect():
    from model import fit
    rng = np.random.default_rng(1)
    n = 600
    df = pd.DataFrame({"book": rng.choice(["a", "b", "c"], n), "pos": rng.uniform(0, 1, n),
                       "n_words": rng.integers(300, 900, n), "x": rng.normal(size=n)})
    mu = np.exp(-6 + np.log(df["n_words"]) + 0.3 * df["x"])
    df["y"] = rng.poisson(mu)
    df["cluster"] = np.arange(n) // 10
    r = fit(df, "y", ["x"], controls=True)
    e = r["effects"][0]
    assert e["ci_low"] < np.exp(0.3 * df["x"].std(ddof=0)) < e["ci_high"]


def test_lexicon_and_aphorism():
    from emotion import lexicon
    from features import aphorisms
    assert lexicon("This line made me cry")["moved"] == 1
    assert lexicon("好笑死了哈哈")["amusement"] == 1
    a = aphorisms("It is a truth universally acknowledged, that a single man in possession of a good fortune must be in want of a wife. He said no.", ["Darcy"])
    assert len(a) == 1


def test_server_parsers_and_fleiss():
    from llm_annotate import agreement_categorical, fleiss_kappa, parse
    assert parse("align", '{"choice": 3}')["choice"] == 3
    assert parse("emotion", 'x {"moved":1,"anger":0} y')["moved"] == 1
    assert fleiss_kappa([[3, 0], [0, 3], [3, 0]]) == 1.0
    res = agreement_categorical({"m1": {i: 1 for i in range(10)}, "m2": {i: i % 2 for i in range(10)}}, [0, 1])
    assert res["fleiss_kappa"] is None and "退化" in res["blocked_reason"]


def test_weread_adapter_chinese_alignment(tmp_path):
    from weread_export import align, parse_export, split_paragraphs
    book = "第一章\n\n天气很好，我们一起去河边散步，看见一只白色的鸟。\n\n第二章\n\n他终于认出了她，眼泪一下子流了出来，那是二十年前的约定。"
    exp = tmp_path / "notes.txt"
    exp.write_text("◆ 第二章\n>> 他终于认出了她，眼泪一下子流了出来  12人划线\n>> 不存在于书中的一句话随便写写\n", encoding="utf-8")
    hs = parse_export(exp)
    assert hs[0]["count"] == 12 and hs[0]["chapter"]
    paras = split_paragraphs(book)
    al = align(hs, paras)
    assert paras[al[0]["pid"]].startswith("他终于认出了她")
    assert al[1]["pid"] is None
