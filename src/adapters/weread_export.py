"""微信读书（用户本人导出 / 用户自愿捐赠）的划线 → 段落热度。

不访问任何微信读书接口。输入只能是用户自己导出的文件：
  - 文本：App “笔记 → 导出 → 复制到剪贴板”后粘贴保存的 .txt（格式随版本变化，[未核实]）。
    这里做宽松解析：以 ◆ / # / 第X章 开头的行视为章节标题，以 >> / ▶ / > 开头或其余非空行视为一条划线；
    行尾的 “N人划线” “(N)” 会被识别为热门划线人数。
  - JSON：官方 Skill（github.com/tencent/wechatreading）返回的列表，字段名不确定，按
    text / markText / content / abstract 依次取文本，按 count / markCount / num 取人数（[未核实]）。
输出与 Goodreads 管线同构：每条划线对齐到原文段落（中文用字符 6-gram 匹配），得到每段的划线数，
再交给 heat.py 做位置归一化（划线有“越往后读的人越少”的衰减，可用 surv_weighted）。

用法: python src/adapters/weread_export.py <export.txt|json> <公版原文.txt> [--finish-rate 0.3]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

CH_HEAD = re.compile(r"^\s*(◆|#+|第[一二三四五六七八九十百千0-9]+[章回节卷])")
COUNT = re.compile(r"(\d+)\s*人划线|[（(](\d+)[)）]\s*$")
PREFIX = re.compile(r"^\s*(>>|▶|>|•|-)\s*")


def parse_export(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        items = json.loads(raw)
        if isinstance(items, dict):
            items = next((v for v in items.values() if isinstance(v, list)), [])
        out = []
        for it in items:
            t = next((it.get(k) for k in ("text", "markText", "content", "abstract") if it.get(k)), None)
            n = next((it.get(k) for k in ("count", "markCount", "num") if it.get(k) is not None), 1)
            if t:
                out.append({"text": str(t), "count": int(n), "chapter": it.get("chapterTitle")})
        return out
    out, chapter = [], None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if CH_HEAD.match(line):
            chapter = CH_HEAD.sub("", line).strip() or line.strip()
            continue
        m = COUNT.search(line)
        n = int(m.group(1) or m.group(2)) if m else 1
        t = COUNT.sub("", PREFIX.sub("", line)).strip()
        if len(t) >= 4:
            out.append({"text": t, "count": n, "chapter": chapter})
    return out


def _clean(s: str) -> str:
    return re.sub(r"[\s，。！？；：、“”‘’（）《》…—,.!?;:'\"()\-]+", "", s)


def char_ngrams(s: str, n: int = 6) -> set[str]:
    s = _clean(s)
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))} or ({s} if s else set())


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\n(?=　　)", text) if p.strip()]


def align(highlights: list[dict], paragraphs: list[str], min_overlap: float = 0.6) -> list[dict]:
    inv = collections.defaultdict(set)
    grams = [char_ngrams(p) for p in paragraphs]
    for i, g in enumerate(grams):
        for x in g:
            inv[x].add(i)
    out = []
    for h in highlights:
        hg = char_ngrams(h["text"])
        if not hg:
            continue
        votes = collections.Counter(i for x in hg for i in inv.get(x, ()))
        if not votes:
            out.append({**h, "pid": None, "overlap": 0.0})
            continue
        pid, k = votes.most_common(1)[0]
        ov = k / len(hg)
        out.append({**h, "pid": pid if ov >= min_overlap else None, "overlap": round(ov, 3)})
    return out


def paragraph_heat(aligned: list[dict], paragraphs: list[str], finish_rate: float | None = None):
    import numpy as np
    from heat import survival_curve
    words = np.array([max(1, len(_clean(p))) for p in paragraphs], float)
    pos = (np.cumsum(words) - words / 2) / words.sum()
    cnt = np.zeros(len(paragraphs))
    for a in aligned:
        if a["pid"] is not None:
            cnt[a["pid"]] += a["count"]
    adj = cnt / survival_curve(pos, finish_rate) if finish_rate else cnt
    return [{"pid": i, "pos": round(float(pos[i]), 4), "chars": int(words[i]), "highlights": float(cnt[i]),
             "highlights_surv_adj": round(float(adj[i]), 3), "text": paragraphs[i][:80]} for i in range(len(paragraphs))]


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("book")
    ap.add_argument("--finish-rate", type=float, default=None, help="读完率（如书籍页显示的读完人数/在读人数），用于逆留存加权")
    a = ap.parse_args()
    hs = parse_export(Path(a.export))
    paras = split_paragraphs(Path(a.book).read_text(encoding="utf-8"))
    al = align(hs, paras)
    heat = paragraph_heat(al, paras, a.finish_rate)
    top = sorted(heat, key=lambda r: -r["highlights_surv_adj"])[:10]
    print(json.dumps({"n_highlights": len(hs), "n_aligned": sum(x["pid"] is not None for x in al), "top": top},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
