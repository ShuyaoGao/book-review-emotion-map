"""书本切分：章节 → 段落 → 场景（桥段）。

场景边界检测 = 章节边界（硬边界）+ 章内 TextTiling（嵌入版）：
  对每个段落间隙 g，比较左窗口（向前累积约 W 词的段落）与右窗口的平均嵌入余弦相似度 s_g，
  深度 depth_g = (左侧最高 s - s_g) + (右侧最高 s - s_g)；取局部极小且 depth 高的间隙为候选，
  在满足最短场景长度的前提下按深度从大到小贪心接受；超过最长长度的场景在最深间隙处再切。
验证：把章节标题去掉、整本书连起来跑同一算法，看它能否找回作者的章节边界（Pk / WindowDiff / 边界召回），
这是“无人工金标时的替代检验”，结果写在 result.json 的 validation 段。

用法: python src/segment.py               # 全部书
输出: data/interim/<slug>/paragraphs.jsonl, scenes.jsonl；results/segment/<date>/result.json
"""
from __future__ import annotations

import re
import sys

import numpy as np

from common import BOOKS, INTERIM, load_books_config, new_run, write_json, write_jsonl
from embed import BACKEND, embed

MIN_SCENE_WORDS = 300
MAX_SCENE_WORDS = 1600
WINDOW_WORDS = 300  # 在“找回章节边界”替代任务上从 {160,300,500,800} 中选出，见 STATUS
QUOTE_CHARS = "“”\""


def strip_illustrations(text: str) -> str:
    """删除 [Illustration ...] 块（可跨行、可嵌套方括号）。"""
    out, i, n = [], 0, len(text)
    while i < n:
        j = text.find("[Illustration", i)
        if j < 0:
            out.append(text[i:]); break
        out.append(text[i:j])
        depth, k = 0, j
        while k < n:
            if text[k] == "[":
                depth += 1
            elif text[k] == "]":
                depth -= 1
                if depth == 0:
                    k += 1; break
            k += 1
        i = k
    return "".join(out)


def clean_para(p: str) -> str:
    p = re.sub(r"\s+", " ", p).strip()
    p = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", p)   # _斜体_ 标记
    p = p.replace("_", "")
    return p


def dialogue_ratio(p: str) -> float:
    inside, total, on = 0, 0, False
    for ch in p:
        if ch in "“":
            on = True; continue
        if ch in "”":
            on = False; continue
        if ch == '"':
            on = not on; continue
        if not ch.isspace():
            total += 1
            inside += on
    return inside / total if total else 0.0


def split_book(book: dict) -> tuple[list[dict], list[str]]:
    raw = (BOOKS / f"{book['slug']}.txt").read_text(encoding="utf-8") if (BOOKS / f"{book['slug']}.txt").exists() \
        else (BOOKS / f"pg{book['gutenberg_id']}.txt").read_text(encoding="utf-8")
    if book.get("start_after"):
        k = raw.find(book["start_after"])
        assert k >= 0, f"start marker not found for {book['slug']}"
        raw = raw[k + len(book["start_after"]):]
    if book.get("end_before"):
        k = raw.find(book["end_before"])
        if k >= 0:
            raw = raw[:k]
    raw = re.sub(r"(?m)^\s*END\s*$", "", raw)
    head = re.compile(book["chapter_regex"])
    lines = raw.split("\n")
    chapters, cur, titles = [], [], []
    for ln in lines:
        if head.match(ln):
            if titles:
                chapters.append("\n".join(cur))
            titles.append(ln.strip().rstrip("]"))
            cur = []
        else:
            cur.append(ln)
    chapters.append("\n".join(cur))
    paras = []
    for ci, body in enumerate(chapters):
        body = strip_illustrations(body)
        for pj, p in enumerate(x for x in re.split(r"\n\s*\n", body) if x.strip()):
            t = clean_para(p)
            if not t or len(t) < 2:
                continue
            paras.append({"chapter": ci + 1, "text": t})
    tot = sum(len(p["text"].split()) for p in paras)
    acc = 0
    for i, p in enumerate(paras):
        w = len(p["text"].split())
        p.update({"book": book["slug"], "pid": i, "n_words": w,
                  "pos": round((acc + w / 2) / tot, 6), "pos_start": round(acc / tot, 6),
                  "dialogue_ratio": round(dialogue_ratio(p["text"]), 4)})
        acc += w
    return paras, titles


def gap_scores(vecs: np.ndarray, words: list[int], window: int = WINDOW_WORDS) -> np.ndarray:
    """返回长度 n-1 的数组：间隙 g（段 g 与 g+1 之间）左右窗口的余弦相似度。"""
    n = len(vecs)
    s = np.zeros(max(n - 1, 0))
    for g in range(n - 1):
        lw, i, L = 0, g, []
        while i >= 0 and (lw < window or not L):
            L.append(i); lw += words[i]; i -= 1
        rw, j, R = 0, g + 1, []
        while j < n and (rw < window or not R):
            R.append(j); rw += words[j]; j += 1
        a = (vecs[L] * np.array(words)[L, None]).sum(0)
        b = (vecs[R] * np.array(words)[R, None]).sum(0)
        s[g] = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    return s


def depth_scores(s: np.ndarray) -> np.ndarray:
    d = np.zeros_like(s)
    for g in range(len(s)):
        lp = s[g]
        for i in range(g, -1, -1):
            if s[i] >= lp: lp = s[i]
            else: break
        rp = s[g]
        for j in range(g, len(s)):
            if s[j] >= rp: rp = s[j]
            else: break
        d[g] = (lp - s[g]) + (rp - s[g])
    return d


def tile(words: list[int], s: np.ndarray, min_w=MIN_SCENE_WORDS, max_w=MAX_SCENE_WORDS, thr_k=0.5) -> list[int]:
    """返回切分点（间隙下标列表，切在段 g 之后）。"""
    n = len(words)
    if n <= 1:
        return []
    d = depth_scores(s)
    cs = np.concatenate([[0], np.cumsum(words)])
    thr = d.mean() + thr_k * d.std() if len(d) > 1 else np.inf
    cand = [g for g in np.argsort(-d) if d[g] >= thr]
    cuts: list[int] = []

    def ok(g):
        pts = sorted(cuts + [g])
        bounds = [0] + [p + 1 for p in pts] + [n]
        return all(cs[bounds[k + 1]] - cs[bounds[k]] >= min_w for k in range(len(bounds) - 1))

    for g in cand:
        if ok(g):
            cuts.append(int(g))
    # 过长场景再切
    changed = True
    while changed:
        changed = False
        pts = sorted(cuts)
        bounds = [0] + [p + 1 for p in pts] + [n]
        for k in range(len(bounds) - 1):
            a, b = bounds[k], bounds[k + 1]
            if cs[b] - cs[a] > max_w and b - a > 1:
                inner = [g for g in range(a, b - 1)]
                inner.sort(key=lambda g: -d[g])
                for g in inner:
                    left, right = cs[g + 1] - cs[a], cs[b] - cs[g + 1]
                    if left >= min_w / 2 and right >= min_w / 2:
                        cuts.append(g); changed = True; break
                if changed:
                    break
    return sorted(set(cuts))


def build_scenes(paras: list[dict], vecs: np.ndarray) -> list[dict]:
    scenes = []
    for ch in sorted({p["chapter"] for p in paras}):
        idx = [i for i, p in enumerate(paras) if p["chapter"] == ch]
        words = [paras[i]["n_words"] for i in idx]
        s = gap_scores(vecs[idx], words)
        cuts = tile(words, s)
        bounds = [0] + [c + 1 for c in cuts] + [len(idx)]
        for k in range(len(bounds) - 1):
            members = idx[bounds[k]:bounds[k + 1]]
            scenes.append({"chapter": ch, "pids": members})
    for sid, sc in enumerate(scenes):
        ps = [paras[i] for i in sc["pids"]]
        w = sum(p["n_words"] for p in ps)
        sc.update({
            "book": ps[0]["book"], "sid": sid, "pid_start": sc["pids"][0], "pid_end": sc["pids"][-1],
            "n_words": w, "n_paras": len(ps),
            "pos": round(sum(p["pos"] * p["n_words"] for p in ps) / w, 6),
            "pos_start": ps[0]["pos_start"],
            "dialogue_ratio": round(sum(p["dialogue_ratio"] * p["n_words"] for p in ps) / w, 4),
            "text": "\n\n".join(p["text"] for p in ps),
        })
        del sc["pids"]
        for p in ps:
            p["sid"] = sid
    return scenes


def seg_metrics(true_cuts: set[int], pred_cuts: set[int], n: int) -> dict:
    """Pk 与 WindowDiff（以段落为单位），以及容差 ±2 段的边界召回/精确率。"""
    tb = np.zeros(n - 1, dtype=int); pb = np.zeros(n - 1, dtype=int)
    for c in true_cuts: tb[c] = 1
    for c in pred_cuts: pb[c] = 1
    nseg = len(true_cuts) + 1
    k = max(2, int(round(n / nseg / 2)))
    pk_err = wd_err = 0
    m = n - k
    for i in range(m):
        t = tb[i:i + k].sum(); p = pb[i:i + k].sum()
        pk_err += (t > 0) != (p > 0)
        wd_err += t != p
    hit_t = sum(any(abs(c - p) <= 2 for p in pred_cuts) for c in true_cuts)
    hit_p = sum(any(abs(c - p) <= 2 for c in true_cuts) for p in pred_cuts)
    return {"pk": round(pk_err / m, 4), "windowdiff": round(wd_err / m, 4), "k": k,
            "boundary_recall_tol2": round(hit_t / max(1, len(true_cuts)), 4),
            "boundary_precision_tol2": round(hit_p / max(1, len(pred_cuts)), 4),
            "n_true": len(true_cuts), "n_pred": len(pred_cuts)}


def random_baseline(true_cuts, n, n_pred, reps=200, seed=0):
    rng = np.random.default_rng(seed)
    res = [seg_metrics(true_cuts, set(rng.choice(n - 1, size=n_pred, replace=False).tolist()), n) for _ in range(reps)]
    return {k: round(float(np.mean([r[k] for r in res])), 4) for k in ("pk", "windowdiff", "boundary_recall_tol2", "boundary_precision_tol2")}


def main():
    books = load_books_config()
    only = set(sys.argv[1:])
    run = new_run("segment")
    result = {"params": {"min_scene_words": MIN_SCENE_WORDS, "max_scene_words": MAX_SCENE_WORDS,
                         "window_words": WINDOW_WORDS}, "books": {}, "validation": {}}
    for b in books:
        if only and b["slug"] not in only:
            continue
        paras, titles = split_book(b)
        vecs = embed([p["text"] for p in paras])
        scenes = build_scenes(paras, vecs)
        d = INTERIM / b["slug"]
        write_jsonl(d / "paragraphs.jsonl", paras)
        write_jsonl(d / "scenes.jsonl", scenes)
        np.save(d / "para_emb.npy", vecs)
        sw = [s["n_words"] for s in scenes]
        result["books"][b["slug"]] = {
            "n_chapters": len(titles), "n_paragraphs": len(paras), "n_words": sum(p["n_words"] for p in paras),
            "n_scenes": len(scenes), "scene_words_median": int(np.median(sw)),
            "scene_words_p10_p90": [int(np.percentile(sw, 10)), int(np.percentile(sw, 90))],
        }
        # ── 替代检验：整本连起来（不告诉算法章节），能否找回章节边界 ──
        words = [p["n_words"] for p in paras]
        s = gap_scores(vecs, words)
        true_cuts = {i for i in range(len(paras) - 1) if paras[i]["chapter"] != paras[i + 1]["chapter"]}
        # 只让算法输出与章节数相同数量的切点（按深度排序取前 K，满足最短长度）
        dsc = depth_scores(s)
        cs = np.concatenate([[0], np.cumsum(words)])
        order = np.argsort(-dsc); pred = []
        for g in order:
            if len(pred) >= len(true_cuts):
                break
            pts = sorted(pred + [int(g)])
            bounds = [0] + [p + 1 for p in pts] + [len(paras)]
            if all(cs[bounds[k + 1]] - cs[bounds[k]] >= MIN_SCENE_WORDS for k in range(len(bounds) - 1)):
                pred.append(int(g))
        m = seg_metrics(true_cuts, set(pred), len(paras))
        m["random_baseline"] = random_baseline(true_cuts, len(paras), len(pred))
        result["validation"][b["slug"]] = m
        write_jsonl(run / "raw" / f"{b['slug']}_scenes_index.jsonl",
                    [{k: v for k, v in sc.items() if k != "text"} for sc in scenes])
        print(b["slug"], result["books"][b["slug"]], m, flush=True)
    result["embed_backend"] = BACKEND["name"]
    write_json(run / "result.json", result)


if __name__ == "__main__":
    main()
