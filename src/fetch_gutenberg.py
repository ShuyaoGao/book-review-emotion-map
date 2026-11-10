"""下载 Project Gutenberg 公版书纯文本，去掉 Gutenberg 头尾许可声明，落盘 data/books/<slug>.txt。

用法: python src/fetch_gutenberg.py            # 下载 configs/books.json 里的全部书
      python src/fetch_gutenberg.py 1342 1260  # 只下载给定 Gutenberg 编号（slug=pg<id>）

说明：只逐本请求公开的 cache/epub 纯文本，不批量爬站；请求头不含任何个人信息。
Gutenberg 文本在美国属公版；去掉头尾后不再使用 "Project Gutenberg" 商标（见其许可第 1.E 节）。
"""
from __future__ import annotations

import re
import sys
import time

import requests

from common import BOOKS, load_books_config, sha256, write_json

URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
START = re.compile(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\*\*\*", re.I)
END = re.compile(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK", re.I)


def strip_pg(text: str) -> str:
    s = START.search(text)
    e = END.search(text)
    body = text[s.end() if s else 0: e.start() if e else len(text)]
    return body.replace("\r\n", "\n").strip() + "\n"


def fetch(gid: int, slug: str) -> dict:
    BOOKS.mkdir(parents=True, exist_ok=True)
    out = BOOKS / f"{slug}.txt"
    if out.exists() and out.stat().st_size > 1000:
        return {"slug": slug, "gutenberg_id": gid, "path": str(out), "sha256": sha256(out), "cached": True}
    for attempt in range(4):
        try:
            r = requests.get(URL.format(id=gid), timeout=120)
            r.raise_for_status()
            break
        except Exception as e:  # noqa
            print(f"[retry] {gid}: {e}", flush=True)
            time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"download failed: {gid}")
    r.encoding = "utf-8"
    body = strip_pg(r.text)
    out.write_text(body, encoding="utf-8")
    time.sleep(2)  # 礼貌间隔
    return {"slug": slug, "gutenberg_id": gid, "url": URL.format(id=gid), "path": str(out),
            "chars": len(body), "sha256": sha256(out), "cached": False}


def main():
    if len(sys.argv) > 1:
        targets = [(int(a), f"pg{a}") for a in sys.argv[1:]]
    else:
        targets = [(b["gutenberg_id"], b["slug"]) for b in load_books_config()]
    log = [fetch(g, s) for g, s in targets]
    for x in log:
        print(x["slug"], x.get("chars"), x["sha256"][:12])
    write_json(BOOKS / "_manifest.json", log)


if __name__ == "__main__":
    main()
