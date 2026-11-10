"""评论 → 桥段对齐。

两条通道：
  1) 引文通道（quote）：评论句里直接引了原文。用 5-gram 倒排索引找候选段落，
     再用 rapidfuzz 做模糊匹配确认（容忍标点、大小写、个别词出入）。
  2) 情节通道（plot）：评论只描述情节（"他终于认出她那段哭死"）。用 bge-m3 嵌入在“段落窗口”上检索 top-k，
     再由确认器判定是否真的指向某一桥段：
       - mock：规则确认（相似度阈值 + 与次优候选的差距 + 人名重合）
       - LLM：把评论句（含前后句）和 k 个候选原文给模型，让它选编号或回答 0（泛泛而谈 / 不指向具体桥段）

输出（每本书）：data/interim/<slug>/mentions_<confirm>.jsonl，单位 = (review_id, sent_idx)。
同一条评论多次指向同一场景只计一次（在 heat.py 里去重）。
"""
from __future__ import annotations

import collections
import json
import re
import unicodedata

import numpy as np
from rapidfuzz import fuzz

from common import INTERIM, read_jsonl
from embed import embed

SHINGLE = 5
MAX_SHINGLE_DF = 4          # 出现在 >4 个段落的 5-gram 视为套话，不参与定位
MIN_COVERED_TOKENS = 7      # 至少有 7 个词被共享 5-gram 覆盖才算引文
QUOTE_FUZZ = 88             # 引号内片段与段落的 partial_ratio 阈值
PASSAGE_WORDS = 160
TOPK = 8                    # 金标上 top5 召回 19/36、top10 26/36，取 8 折中（已披露：在金标上选的）

_PUNCT = re.compile(r"[^a-z0-9一-鿿 ]+")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("'", "")
    s = _PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def shingles(tokens: list[str], n: int = SHINGLE):
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


class BookIndex:
    def __init__(self, slug: str):
        self.slug = slug
        d = INTERIM / slug
        self.paras = read_jsonl(d / "paragraphs.jsonl")
        self.scenes = read_jsonl(d / "scenes.jsonl")
        self.norm = [norm(p["text"]) for p in self.paras]
        self.inv = collections.defaultdict(set)
        for p, t in zip(self.paras, self.norm):
            for sh in shingles(t.split()):
                self.inv[sh].add(p["pid"])
        self.pid2sid = {p["pid"]: p["sid"] for p in self.paras}
        self._passages = None

    # ---------- 引文通道 ----------
    def match_quote(self, sentence: str):
        toks = norm(sentence).split()
        if len(toks) < SHINGLE:
            return None
        cover = collections.defaultdict(set)   # pid -> 被覆盖的句内 token 下标
        for i, sh in enumerate(shingles(toks)):
            pids = self.inv.get(sh)
            if not pids or len(pids) > MAX_SHINGLE_DF:
                continue
            for pid in pids:
                cover[pid].update(range(i, i + SHINGLE))
        if not cover:
            return self._match_quoted_span(sentence)
        best = max(cover.values(), key=len)
        n_best = len(best)
        if n_best < MIN_COVERED_TOKENS:
            return self._match_quoted_span(sentence)
        cands = [pid for pid, c in cover.items() if len(c) >= max(MIN_COVERED_TOKENS, 0.8 * n_best)]
        cands.sort(key=lambda p: -len(cover[p]))
        return {"pids": cands[:3], "n_cands": len(cands), "covered": n_best, "n_tokens": len(toks),
                "coverage": round(n_best / len(toks), 3), "via": "shingle"}

    def _match_quoted_span(self, sentence: str):
        """处理较短的、带引号的引文（不足以形成 7 词共享 5-gram 的）。"""
        spans = re.findall(r"[\"“]([^\"”]{12,300})[\"”]", sentence)
        for sp in spans:
            st = norm(sp).split()
            if len(st) < 4:
                continue
            keys = shingles(st, 4)
            probe = [keys[0], keys[len(keys) // 2], keys[-1]]
            cand = set()
            for pid, t in enumerate(self.norm):
                if any(k in t for k in probe):
                    cand.add(pid)
            scored = [(fuzz.partial_ratio(" ".join(st), self.norm[pid]), pid) for pid in cand]
            scored = [x for x in scored if x[0] >= QUOTE_FUZZ]
            if 0 < len(scored) <= 3:
                scored.sort(reverse=True)
                return {"pids": [p for _, p in scored], "n_cands": len(scored), "covered": len(st),
                        "n_tokens": len(norm(sentence).split()), "coverage": None, "via": "quoted_span",
                        "fuzz": scored[0][0]}
        return None

    def strip_book_text(self, text: str) -> str:
        """去掉评论里引用的原文，只留读者自己的话（情绪打标用，否则会把原文里的情绪词算到读者头上）。
        1) 删掉引号内片段；2) 删掉被书中任一 5-gram 覆盖的词。返回规范化（小写、去标点）的文本。"""
        t = re.sub(r"[\"“][^\"”]{0,400}[\"”]", " ", text)
        toks = norm(t).split()
        covered = set()
        for i, sh in enumerate(shingles(toks)):
            if sh in self.inv:
                covered.update(range(i, i + SHINGLE))
        return " ".join(w for k, w in enumerate(toks) if k not in covered)

    # ---------- 情节通道 ----------
    def passages(self):
        """场景内把相邻段落合成 ~160 词的窗口，作为检索单元。"""
        if self._passages is None:
            out = []
            by_sid = collections.defaultdict(list)
            for p in self.paras:
                by_sid[p["sid"]].append(p)
            for sid in sorted(by_sid):
                buf, w = [], 0
                for p in by_sid[sid]:
                    buf.append(p); w += p["n_words"]
                    if w >= PASSAGE_WORDS:
                        out.append(self._mk(buf, sid)); buf, w = [], 0
                if buf:
                    if out and out[-1]["sid"] == sid and w < PASSAGE_WORDS / 3:
                        prev = out.pop(); buf = prev["_paras"] + buf
                    out.append(self._mk(buf, sid))
            for i, ps in enumerate(out):
                ps["psg"] = i
            self._passages = out
            self.passage_vecs = embed([p["text"] for p in out])
        return self._passages

    @staticmethod
    def _mk(buf, sid):
        return {"sid": sid, "pids": [p["pid"] for p in buf], "text": " ".join(p["text"] for p in buf), "_paras": buf}

    def retrieve(self, qvecs: np.ndarray, k: int = TOPK):
        self.passages()
        sims = qvecs @ self.passage_vecs.T
        top = np.argsort(-sims, axis=1)[:, :k]
        return top, np.take_along_axis(sims, top, axis=1)


def name_hits(text: str, names: list[str]) -> set[str]:
    return {n for n in names if re.search(r"\b" + re.escape(n) + r"\b", text)}


GENERIC = re.compile(r"\b(this book|the book|the novel|the author|i (loved|liked|hated|enjoyed|read)|"
                     r"stars?|rating|reread|re-read|audiobook|kindle|narrator of the audio|classic)\b", re.I)


def plot_candidate(sent: str, flag, names) -> bool:
    toks = sent.split()
    if len(toks) < 6 or len(toks) > 80:
        return False
    hits = name_hits(sent, names)
    if flag == 1 and len(toks) >= 6:
        return True
    return bool(hits) and not GENERIC.search(sent)


def mock_confirm(sims_row, names_in_sent: set, passage_texts: list[str], flag, tau=0.55, margin=0.03):
    """规则确认器：返回选中的候选下标或 None。阈值在金标 dev 子集上选定，见 eval_align.py。"""
    s1 = float(sims_row[0]); s2 = float(sims_row[1]) if len(sims_row) > 1 else 0.0
    t = tau - (0.03 if flag == 1 else 0.0)
    if s1 < t or (s1 - s2) < margin:
        return None
    if names_in_sent and not any(re.search(r"\b" + re.escape(n) + r"\b", passage_texts[0]) for n in names_in_sent):
        return None
    return 0


CONFIRM_PROMPT_VER = "align_confirm_v1"
CONFIRM_PROMPT = """You are matching a reader's review sentence to the passage of the novel "{title}" that it refers to.

Review sentence (with surrounding context in brackets):
[{prev}] >>> {sent} <<< [{next}]

Candidate passages:
{cands}

Question: Does the review sentence (between >>> <<<) refer to a SPECIFIC moment/event/line that is shown in one of the candidate passages?
- If yes, answer with that passage number.
- If the sentence is a general opinion, describes a character in general, refers to a moment not shown in any candidate, or you are unsure, answer 0.
Reply ONLY with JSON: {{"choice": <0-{k}>}}"""


def build_confirm_prompt(title, prev, sent, nxt, cand_texts):
    cands = "\n".join(f"({i + 1}) {' '.join(t.split()[:110])}" for i, t in enumerate(cand_texts))
    return CONFIRM_PROMPT.format(title=title, prev=prev[:200], sent=sent, next=nxt[:200], cands=cands, k=len(cand_texts))


def iter_review_sentences(rows):
    for r in rows:
        sents = r["sentences"]
        for i, (flag, s) in enumerate(sents):
            prev = sents[i - 1][1] if i > 0 else ""
            nxt = sents[i + 1][1] if i + 1 < len(sents) else ""
            yield r, i, flag, s, prev, nxt


def align_book(book: dict, reviews: list[dict], confirm: str = "mock", backend=None, raw_sink=None,
               restrict: set | None = None):
    """返回 mentions 列表。restrict: 只处理给定 (review_id, sent_idx) 集合（金标评估用）。"""
    idx = BookIndex(book["slug"])
    names = book["characters"]
    mentions, plot_q = [], []
    for r, i, flag, s, prev, nxt in iter_review_sentences(reviews):
        if restrict is not None and (r["review_id"], i) not in restrict:
            continue
        q = idx.match_quote(s)
        if q and q["n_cands"] <= 3:
            w = 1.0 / len(q["pids"])
            for pid in q["pids"]:
                mentions.append({"review_id": r["review_id"], "sent_idx": i, "type": "quote", "pid": pid,
                                 "sid": idx.pid2sid[pid], "weight": round(w, 4), "score": q["coverage"],
                                 "via": q["via"], "spoiler": flag})
            continue
        if q:   # 套话式引文（>3 个候选），不计热度
            continue
        if confirm != "quoteonly" and plot_candidate(s, flag, names):
            plot_q.append((r, i, flag, s, prev, nxt))
    if plot_q:
        passages = idx.passages()
        qv = embed([x[3] for x in plot_q])
        top, sims = idx.retrieve(qv)
        prompts, metas = [], []
        for (r, i, flag, s, prev, nxt), trow, srow in zip(plot_q, top, sims):
            cand_texts = [passages[j]["text"] for j in trow]
            meta = {"review_id": r["review_id"], "sent_idx": i, "spoiler": flag,
                    "cands": [int(passages[j]["sid"]) for j in trow], "cand_psg": [int(j) for j in trow],
                    "sims": [round(float(x), 4) for x in srow]}
            if confirm == "mock":
                ch = mock_confirm(srow, name_hits(s, names), cand_texts, flag)
                meta["choice"] = None if ch is None else ch + 1
                metas.append(meta)
            elif confirm == "top1":
                meta["choice"] = 1
                metas.append(meta)
            else:
                prompts.append(build_confirm_prompt(book["title"], prev, s, nxt, cand_texts))
                metas.append(meta)
        if prompts:
            from llm import parse_json_obj
            outs = backend.generate(prompts, max_tokens=20)
            for m, o in zip(metas, outs):
                j = parse_json_obj(o)
                c = j.get("choice") if isinstance(j, dict) else None
                try:
                    c = int(c)
                except Exception:
                    c = None
                m["raw"] = o.strip()[:80]
                m["choice"] = c if (c is not None and 1 <= c <= TOPK) else (0 if c == 0 else None)
                m["parse_ok"] = c is not None
        for m in metas:
            if raw_sink is not None:
                raw_sink.append(m)
            if m.get("choice"):
                k = m["choice"] - 1
                mentions.append({"review_id": m["review_id"], "sent_idx": m["sent_idx"], "type": "plot",
                                 "pid": int(passages[m["cand_psg"][k]]["pids"][0]), "sid": m["cands"][k],
                                 "weight": 1.0, "score": m["sims"][k], "via": confirm, "spoiler": m["spoiler"]})
    return mentions, idx
