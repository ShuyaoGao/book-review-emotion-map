"""导出给 GPU 服务器批量 LLM 标注的条目（JSONL）。

  python src/export_llm_items.py
输出 data/llm_items/（gitignore，含 Goodreads 评论文本，只在本机与实验室服务器之间 rsync，不得外传）：
  features.jsonl   每个场景一条：{id, book, sid, prompt}
  emotion.jsonl    每个被对齐的评论语境一条：{id, book, review_id, sent_idx, prompt}
  align.jsonl      每个情节候选句一条：{id, book, review_id, sent_idx, cand_sids, prompt}
  gold_align.jsonl 金标 C 类 120 条（同 align 格式），用于在服务器上评估 LLM 确认器
提示词版本写在每条的 prompt_version 字段；服务器脚本只负责跑模型和算一致性，不再拼提示词，
保证本机与服务器用的是同一份提示词。
"""
from __future__ import annotations

from align import TOPK, BookIndex, build_confirm_prompt, iter_review_sentences, plot_candidate, CONFIRM_PROMPT_VER
from common import DATA, GOLD, INTERIM, load_books_config, read_jsonl, write_jsonl
from embed import embed
from emotion import EMO_PROMPT, EMO_PROMPT_VER
from features import FEATURE_PROMPT_VER, build_feature_prompt
from pipeline import mention_contexts

OUT = DATA / "llm_items"


def main(corpus: str = "reviews_full", confirm_tag: str = "mock"):
    feats, emos, aligns, gold = [], [], [], []
    gold_keys = {(x["slug"], x["review_id"], x["sent_idx"]): x["item"]
                 for x in read_jsonl(GOLD / "gold_items.jsonl") if x["kind"] == "C"}
    for b in load_books_config():
        slug = b["slug"]
        for s in read_jsonl(INTERIM / slug / "scenes.jsonl"):
            feats.append({"id": f"{slug}:{s['sid']}", "book": slug, "sid": s["sid"],
                          "prompt_version": FEATURE_PROMPT_VER, "prompt": build_feature_prompt(b, s)})
        for c in mention_contexts(b, corpus, confirm_tag):
            emos.append({"id": f"{slug}:{c['review_id']}:{c['sent_idx']}", "book": slug, "review_id": c["review_id"],
                         "sent_idx": c["sent_idx"], "sid": c["sid"], "type": c["type"], "prompt_version": EMO_PROMPT_VER,
                         "prompt": EMO_PROMPT.format(title=b["title"], text=c["context"])})
        idx = BookIndex(slug)
        rows = read_jsonl(INTERIM / corpus / f"{slug}.jsonl")
        cands = []
        for r, i, flag, s, prev, nxt in iter_review_sentences(rows):
            q = idx.match_quote(s)
            if q is None and plot_candidate(s, flag, b["characters"]):
                cands.append((r["review_id"], i, flag, s, prev, nxt))
        top, sims = idx.retrieve(embed([c[3] for c in cands]), k=TOPK)
        ps = idx.passages()
        for (rid, i, flag, s, prev, nxt), t, sm in zip(cands, top, sims):
            rec = {"id": f"{slug}:{rid}:{i}", "book": slug, "review_id": rid, "sent_idx": i, "spoiler": flag,
                   "cand_sids": [int(ps[j]["sid"]) for j in t], "sims": [round(float(v), 4) for v in sm],
                   "prompt_version": CONFIRM_PROMPT_VER,
                   "prompt": build_confirm_prompt(b["title"], prev, s, nxt, [ps[j]["text"] for j in t])}
            aligns.append(rec)
            if (slug, rid, i) in gold_keys:
                gold.append({**rec, "gold_item": gold_keys[(slug, rid, i)]})
    for name, rows in (("features", feats), ("emotion", emos), ("align", aligns), ("gold_align", gold)):
        n = write_jsonl(OUT / f"{name}.jsonl", rows)
        print(name, n)


if __name__ == "__main__":
    main()
