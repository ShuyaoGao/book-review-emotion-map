"""桥段热度：被提及数 → 按阅读位置归一化 → 经验贝叶斯收缩。

为什么要归一化：
  - 划线类数据（微信读书“N人划线”）有明显的幸存者偏差：越往后读的人越少，后面的段落天然被划得少。
  - 书评类数据（Goodreads）则相反地存在“首尾效应”：开头名句和结局最常被提起；同时有剧透顾虑，读者会回避结局。
两种偏差都是“位置的平滑函数”，与桥段本身是否打动人无关。

三种热度：
  raw        提及数（同一条评论对同一场景只计一次；引文跨多个候选段落时按 1/k 分摊）
  oe         观测/期望：期望 = Poisson GLM( 提及数 ~ log(词数) + 位置样条 + 书固定效应 ) 的拟合值
  oe_eb      经验贝叶斯：(O + a) / (E + a)，a 由过度离散度的矩估计给出，压低小样本的偶然高峰
  surv       逆生存加权：w(x) = 1/S(x)，S(x) 为读到位置 x 的读者比例（需外部提供，如平台的“读完率”）

用法: python src/heat.py simulate      # 合成数据检验：哪种热度能找回真实的“桥段吸引力”
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from common import new_run, write_json, write_jsonl


def bspline_basis(x: np.ndarray, df: int = 4) -> np.ndarray:
    """简单的截断幂样条基（三次），节点取分位数；够用且不依赖 patsy。"""
    x = np.asarray(x, float)
    knots = np.quantile(x, np.linspace(0, 1, df)[1:-1]) if df > 2 else []
    cols = [x, x ** 2, x ** 3] + [np.clip(x - k, 0, None) ** 3 for k in knots]
    B = np.column_stack(cols)
    return (B - B.mean(0)) / (B.std(0) + 1e-12)


def expected_by_position(df: pd.DataFrame, y: str = "mentions", spline_df: int = 4) -> np.ndarray:
    """Poisson GLM：y ~ offset(log n_words) + 位置样条 + 书固定效应，返回期望提及数。"""
    import statsmodels.api as sm
    X = [bspline_basis(df["pos"].values, spline_df)]
    books = sorted(df["book"].unique())
    for b in books[1:]:
        X.append((df["book"] == b).astype(float).values[:, None])
    X = sm.add_constant(np.column_stack(X))
    m = sm.GLM(df[y].values, X, family=sm.families.Poisson(), offset=np.log(df["n_words"].values)).fit()
    return m.fittedvalues if hasattr(m.fittedvalues, "__len__") else np.asarray(m.fittedvalues)


def eb_alpha(O: np.ndarray, E: np.ndarray) -> float:
    """Gamma-Poisson 的先验形状参数 a（矩估计）：Var(O/E) ≈ 1/a + 1/E。"""
    r = O / np.maximum(E, 1e-9)
    v = np.var(r) - np.mean(1.0 / np.maximum(E, 1e-9))
    return float(1.0 / v) if v > 1e-6 else 1e6


def add_heat(df: pd.DataFrame, y: str = "mentions") -> pd.DataFrame:
    df = df.copy()
    df["expected"] = expected_by_position(df, y)
    a = eb_alpha(df[y].values, df["expected"].values)
    df["oe"] = df[y] / df["expected"]
    df["oe_eb"] = (df[y] + a) / (df["expected"] + a)
    df["log_oe_eb"] = np.log(df["oe_eb"])
    df["density"] = 1000.0 * df[y] / df["n_words"]
    df.attrs["eb_alpha"] = a
    return df


def survival_curve(pos: np.ndarray, finish_rate: float, shape: float = 1.0) -> np.ndarray:
    """Weibull 型留存：S(0)=1，S(1)=finish_rate；shape<1 表示前期流失快。"""
    lam = -np.log(finish_rate)
    return np.exp(-lam * np.power(np.clip(pos, 0, 1), shape))


def surv_weighted(counts: np.ndarray, pos: np.ndarray, finish_rate: float, shape: float = 1.0) -> np.ndarray:
    return counts / survival_curve(pos, finish_rate, shape)


# ---------------------------------------------------------------- 合成数据检验
def simulate(seed: int = 7, n_books: int = 3, n_scenes: int = 250, n_readers: int = 4000,
             finish_rate: float = 0.35, shape: float = 0.6, reps: int = 50):
    """真实吸引力 a_s 已知 → 读者按留存曲线读到某处后流失 → 读到的场景以 ∝ a_s 的概率被划线/提及。
    比较各热度指标与 a_s 的 Spearman 相关、Top-10 命中。"""
    from scipy.stats import spearmanr
    rng = np.random.default_rng(seed)
    rows, metrics = [], []
    for rep in range(reps):
        recs = []
        for b in range(n_books):
            pos = (np.arange(n_scenes) + 0.5) / n_scenes
            words = rng.integers(300, 1200, n_scenes)
            appeal = rng.lognormal(0, 0.6, n_scenes)
            peaks = rng.choice(n_scenes, 8, replace=False)
            appeal[peaks] *= rng.uniform(3, 6, 8)
            S = survival_curve(pos, finish_rate, shape)
            # 每个读者读到的最远位置
            u = rng.uniform(size=n_readers)
            reach = np.where(u < finish_rate, 1.0, (np.log(u) / np.log(finish_rate)) ** (1 / shape))
            n_reached = (reach[:, None] >= pos[None, :]).sum(0)
            p = 0.004 * appeal * words / 700
            m = rng.binomial(n_reached, np.clip(p, 0, 1))
            for i in range(n_scenes):
                recs.append({"book": f"b{b}", "sid": i, "pos": pos[i], "n_words": int(words[i]),
                             "appeal": appeal[i], "mentions": int(m[i]), "S_true": S[i]})
        df = pd.DataFrame(recs)
        df = add_heat(df)
        df["raw_density"] = df["mentions"] / df["n_words"]
        df["surv_true"] = surv_weighted(df["mentions"].values, df["pos"].values, finish_rate, shape) / df["n_words"]
        # 用真实吸引力/词数 当真值（吸引力是“每词每读者”的）
        res = {}
        for col in ["mentions", "raw_density", "oe", "oe_eb", "surv_true"]:
            rho = np.mean([spearmanr(g[col], g["appeal"]).statistic for _, g in df.groupby("book")])
            top = np.mean([len(set(g.nlargest(10, col)["sid"]) & set(g.nlargest(10, "appeal")["sid"])) / 10
                           for _, g in df.groupby("book")])
            # 后半本的高光是否被低估：后 1/3 场景在 top-20 中的占比 vs 真值
            late = np.mean([(g.nlargest(20, col)["pos"] > 2 / 3).mean() for _, g in df.groupby("book")])
            res[col] = {"spearman": rho, "top10_recall": top, "late_share_top20": late}
        res["truth_late_share_top20"] = np.mean([(g.nlargest(20, "appeal")["pos"] > 2 / 3).mean() for _, g in df.groupby("book")])
        metrics.append(res)
        if rep == 0:
            rows = df.to_dict("records")
    summ = {}
    for col in ["mentions", "raw_density", "oe", "oe_eb", "surv_true"]:
        summ[col] = {k: {"mean": round(float(np.mean([m[col][k] for m in metrics])), 4),
                         "sd": round(float(np.std([m[col][k] for m in metrics])), 4)}
                     for k in ["spearman", "top10_recall", "late_share_top20"]}
    summ["truth_late_share_top20"] = round(float(np.mean([m["truth_late_share_top20"] for m in metrics])), 4)
    return summ, rows


def main():
    if sys.argv[1:] and sys.argv[1] == "simulate":
        params = dict(seed=7, n_books=3, n_scenes=250, n_readers=4000, finish_rate=0.35, shape=0.6, reps=50)
        run = new_run("heat_sim", extra={"SYNTHETIC": True, "params": params})
        summ, rows = simulate(**params)
        write_jsonl(run / "raw" / "rep0_scenes.jsonl", rows)
        write_json(run / "result.json", {"SYNTHETIC": "合成数据，仅检验归一化方法，不是发现", "params": params,
                                         "metrics": summ})
        print(pd.DataFrame({k: {m: v["mean"] for m, v in d.items()} for k, d in summ.items() if isinstance(d, dict)}).T)
        print("truth late share", summ["truth_late_share_top20"])


if __name__ == "__main__":
    main()
