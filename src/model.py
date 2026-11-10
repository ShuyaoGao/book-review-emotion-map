"""建模：哪些桥段特征预测热度、预测哪种情绪。

热度模型（场景层）：
  Poisson 准似然 GLM，y = 去重后的提及数；书固定效应；聚类稳健标准误（按 书×章）。
  naive    = 特征 + 书 FE
  adjusted = 特征 + 书 FE + log(词数) + 位置样条 + 章首/章末 + 全书首/末场景
  效应量：连续特征报告每 +1 SD 的发生率比 IRR（95% CI）；二值特征报告 0→1 的 IRR。
情绪模型（提及层）：
  Logit GLM，y = 该提及的评论语境是否表达某情绪；同样的特征与控制；按场景聚类。
  效应量：OR（每 +1 SD）。
多重比较：同一模型族内做 Benjamini–Hochberg，报告 q 值。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from heat import bspline_basis


def bh(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, i in enumerate(order[::-1]):
        k = n - rank
        prev = min(prev, p[i] * n / k)
        q[i] = prev
    return q


def design(df: pd.DataFrame, features: list[str], controls: bool, standardize: bool = True):
    X = pd.DataFrame(index=df.index)
    scales = {}
    for f in features:
        v = df[f].astype(float)
        binary = set(np.unique(v.dropna())) <= {0.0, 1.0}
        if standardize and not binary:
            sd = v.std(ddof=0) or 1.0
            X[f] = (v - v.mean()) / sd
            scales[f] = {"type": "per_sd", "sd": float(sd)}
        else:
            X[f] = v
            scales[f] = {"type": "binary" if binary else "raw"}
    for b in sorted(df["book"].unique())[1:]:
        X[f"fe_{b}"] = (df["book"] == b).astype(float)
    if controls:
        X["log_words"] = np.log(df["n_words"].astype(float))
        B = bspline_basis(df["pos"].values, 4)
        for j in range(B.shape[1]):
            X[f"pos_s{j}"] = B[:, j]
        for c in ("chapter_open", "chapter_close", "book_first", "book_last"):
            if c in df:
                X[c] = df[c].astype(float)
    X.insert(0, "const", 1.0)
    return X, scales


def fit(df: pd.DataFrame, y: str, features: list[str], controls: bool, family: str = "poisson",
        cluster: str = "cluster") -> dict:
    import statsmodels.api as sm
    X, scales = design(df, features, controls)
    fam = sm.families.Poisson() if family == "poisson" else sm.families.Binomial()
    groups = pd.factorize(df[cluster])[0]
    m = sm.GLM(df[y].astype(float).values, X.values, family=fam).fit(cov_type="cluster", cov_kwds={"groups": groups})
    params = pd.Series(m.params, index=X.columns)
    bse = pd.Series(m.bse, index=X.columns)
    pv = pd.Series(m.pvalues, index=X.columns)
    rows = []
    for f in features:
        b, se = params[f], bse[f]
        rows.append({"feature": f, "scale": scales[f]["type"], "coef": float(b), "se": float(se),
                     "ratio": float(np.exp(b)), "ci_low": float(np.exp(b - 1.96 * se)),
                     "ci_high": float(np.exp(b + 1.96 * se)), "p": float(pv[f])})
    q = bh(np.array([r["p"] for r in rows]))
    for r, qq in zip(rows, q):
        r["q_bh"] = float(qq)
    out = {"y": y, "family": family, "controls": controls, "n": int(len(df)), "n_clusters": int(groups.max() + 1),
           "effects": rows, "ratio_name": "IRR" if family == "poisson" else "OR"}
    if controls:
        out["control_coefs"] = {c: {"coef": float(params[c]), "p": float(pv[c])}
                                for c in X.columns if c in ("log_words", "chapter_open", "chapter_close", "book_first", "book_last")}
    if family == "poisson":
        mu = m.fittedvalues
        out["pearson_dispersion"] = float(np.sum((df[y].values - mu) ** 2 / mu) / (len(df) - X.shape[1]))
    return out


def effects_table(res: dict) -> pd.DataFrame:
    t = pd.DataFrame(res["effects"])
    return t[["feature", "scale", "ratio", "ci_low", "ci_high", "p", "q_bh"]].round(4)
