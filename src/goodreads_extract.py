"""从 UCSD Book Graph 的 goodreads_reviews_spoiler.json.gz 中抽取目标书目的评论。

两步：
  python src/goodreads_extract.py scan      # 统计每个 book_id 的评论数，与 works 表的 best_book_id 关联出书名
  python src/goodreads_extract.py extract   # 按 configs/books.json 的 goodreads_book_ids 抽取评论到 data/interim/reviews/<slug>.jsonl

数据许可：UCSD 页面原文 "academic use only ... do not redistribute ... or use for commercial purposes"。
因此抽取结果只放在 data/interim（gitignore），展示时只用聚合量和不含用户标识的短摘录。
抽取时直接丢弃 user_id（不需要）；review_id 是数据集作者已匿名化的哈希，仅用于去重与追溯。
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys

from common import INTERIM, RAW, load_books_config, write_json, write_jsonl

SPOILER = RAW / "ucsd" / "goodreads_reviews_spoiler.json.gz"
WORKS = RAW / "ucsd" / "goodreads_book_works.json.gz"


def scan(top: int = 400):
    cnt = collections.Counter()
    with gzip.open(SPOILER, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            cnt[d["book_id"]] += 1
    best = {}
    with gzip.open(WORKS, "rt", encoding="utf-8") as f:
        for line in f:
            w = json.loads(line)
            if w.get("best_book_id"):
                best[w["best_book_id"]] = (w.get("original_title"), w.get("original_publication_year"), w["work_id"])
    rows = []
    for bid, n in cnt.most_common():
        if bid in best:
            t, y, wid = best[bid]
            rows.append({"book_id": bid, "n_reviews": n, "title": t, "year": y, "work_id": wid})
    out = INTERIM / "goodreads_spoiler_book_counts.json"
    write_json(out, {"n_books": len(cnt), "n_reviews": sum(cnt.values()),
                     "n_matched_best_book": len(rows), "rows": rows[:top],
                     "old_titles_pre1930": [r for r in rows if r["year"] and r["year"].isdigit() and int(r["year"]) < 1930][:300]})
    print(f"books={len(cnt)} reviews={sum(cnt.values())} matched={len(rows)} -> {out}")


def extract():
    books = load_books_config()
    want = {}
    for b in books:
        for bid in b["goodreads_book_ids"]:
            want[str(bid)] = b["slug"]
    out = collections.defaultdict(list)
    with gzip.open(SPOILER, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            slug = want.get(d["book_id"])
            if slug is None:
                continue
            out[slug].append({
                "review_id": d["review_id"],
                "book_id": d["book_id"],
                "rating": d.get("rating"),
                "has_spoiler": d.get("has_spoiler"),
                "timestamp": d.get("timestamp"),
                # [[spoiler_flag, sentence], ...]
                "sentences": d["review_sentences"],
            })
    stats = {}
    for slug, rows in out.items():
        n = write_jsonl(INTERIM / "reviews" / f"{slug}.jsonl", rows)
        ns = sum(len(r["sentences"]) for r in rows)
        nsp = sum(int(s[0]) for r in rows for s in r["sentences"])
        stats[slug] = {"reviews": n, "sentences": ns, "spoiler_sentences": nsp}
        print(slug, stats[slug])
    write_json(INTERIM / "reviews" / "_stats.json", stats)


DEDUP = RAW / "ucsd" / "goodreads_reviews_dedup.json.gz"
_SPLIT = re.compile(r"(?<=[.!?])[\"”’)]*\s+(?=[\"“'(]?[A-Z0-9])|\n+")
_SPOIL = re.compile(r"\(view spoiler\)\[(.*?)\(hide spoiler\)\]", re.S)
_EN_STOP = re.compile(r"\b(the|and|of|to|is|was|it|that|this|book)\b", re.I)


def split_review(text: str):
    """完整书评 → [[spoiler_flag, sentence], ...]；(view spoiler)[...] 包裹的句子标为 1。"""
    out = []
    pos = 0
    chunks = []
    for m in _SPOIL.finditer(text):
        chunks.append((0, text[pos:m.start()])); chunks.append((1, m.group(1))); pos = m.end()
    chunks.append((0, text[pos:]))
    for flag, ch in chunks:
        for sent in _SPLIT.split(ch):
            sent = re.sub(r"\s+", " ", sent).strip()
            if len(sent) >= 2:
                out.append([flag, sent])
    return out


def is_english(text: str) -> bool:
    if not text:
        return False
    asc = sum(c.isascii() for c in text) / len(text)
    return asc > 0.9 and len(_EN_STOP.findall(text[:2000])) >= 3


def extract_dedup():
    """主语料：完整去重书评（15.7M 条）里目标书目的英文书评；与 spoiler 子集按 review_id 合并句级剧透标签。"""
    books = load_books_config()
    want = {str(bid): b["slug"] for b in books for bid in b["goodreads_book_ids"]}
    spoil = {}
    for b in books:
        p = INTERIM / "reviews" / f"{b['slug']}.jsonl"
        if p.exists():
            for line in open(p, encoding="utf-8"):
                d = json.loads(line)
                spoil[d["review_id"]] = d["sentences"]
    out = collections.defaultdict(list)
    n_seen = n_lang = 0
    with gzip.open(DEDUP, "rt", encoding="utf-8") as f:
        for line in f:
            if '"book_id"' not in line:
                continue
            d = json.loads(line)
            slug = want.get(d["book_id"])
            if slug is None:
                continue
            n_seen += 1
            txt = d.get("review_text") or ""
            if not is_english(txt) or len(txt) < 20:
                n_lang += 1
                continue
            rid = d["review_id"]
            sents = spoil.get(rid) or split_review(txt)
            out[slug].append({"review_id": rid, "book_id": d["book_id"], "rating": d.get("rating"),
                              "n_votes": d.get("n_votes"), "date_added": d.get("date_added"),
                              "from_spoiler_subset": rid in spoil, "sentences": sents})
    stats = {"n_seen": n_seen, "n_dropped_non_english_or_short": n_lang}
    for slug, rows in out.items():
        n = write_jsonl(INTERIM / "reviews_full" / f"{slug}.jsonl", rows)
        stats[slug] = {"reviews": n, "sentences": sum(len(r["sentences"]) for r in rows),
                       "spoiler_sentences": sum(int(s[0]) for r in rows for s in r["sentences"]),
                       "matched_spoiler_subset": sum(r["from_spoiler_subset"] for r in rows)}
        print(slug, stats[slug])
    write_json(INTERIM / "reviews_full" / "_stats.json", stats)


if __name__ == "__main__":
    {"scan": scan, "extract": extract, "extract_dedup": extract_dedup}[sys.argv[1]]()
