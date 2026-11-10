"""按 work_id 从 goodreads_books.json.gz 找出同一作品的全部版本 book_id，只保留英文或语言未标注的版本，
回写 configs/books.json 的 goodreads_book_ids（第一个保持 best_book_id）。

用法: python src/goodreads_editions.py
"""
from __future__ import annotations

import gzip
import json

from common import CONFIGS, INTERIM, RAW, write_json

BOOKS_GZ = RAW / "ucsd" / "goodreads_books.json.gz"
OK_LANG = {"", "eng", "en-US", "en-GB", "en-CA", "en"}


def main():
    cfg = json.loads((CONFIGS / "books.json").read_text(encoding="utf-8"))
    work2slug = {b["goodreads_work_id"]: b["slug"] for b in cfg["books"]}
    found = {b["slug"]: [] for b in cfg["books"]}
    with gzip.open(BOOKS_GZ, "rt", encoding="utf-8") as f:
        for line in f:
            if '"work_id"' not in line:
                continue
            d = json.loads(line)
            slug = work2slug.get(d.get("work_id"))
            if slug and d.get("language_code", "") in OK_LANG:
                found[slug].append({"book_id": d["book_id"], "lang": d.get("language_code"),
                                    "title": d.get("title"), "text_reviews_count": d.get("text_reviews_count")})
    for b in cfg["books"]:
        ids = [b["goodreads_book_ids"][0]] + sorted({x["book_id"] for x in found[b["slug"]]} - {b["goodreads_book_ids"][0]}, key=int)
        b["goodreads_book_ids"] = ids
        print(b["slug"], len(ids), "editions")
    (CONFIGS / "books.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    write_json(INTERIM / "goodreads_editions.json", found)


if __name__ == "__main__":
    main()
