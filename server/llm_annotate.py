#!/usr/bin/env python
"""GPU 服务器：多个本地开源模型对同一批条目做 LLM 标注，并算模型间一致性（带退化守卫）。

落 _env_stamp.json、逐条原始输出 raw/<model>.jsonl、result.json。

用法（Linux GPU 服务器上，需要 vLLM；可放进任务队列串行跑）：
  python server/llm_annotate.py \
      --task features --items data/llm_items/features.jsonl \
      --models Qwen/Qwen2.5-7B-Instruct Qwen/Qwen3-8B meta-llama/Llama-3.1-8B-Instruct \
      --out results/llm_features_$(date +%F)

task:
  features  输出 JSON 编码（scene_type + 9 个代码）  → 有序代码算 ICC(2,k)，二值代码算 Fleiss κ
  emotion   输出 10 个 0/1 情绪标签                    → 每个标签 Fleiss κ + 两两 Cohen κ
  align     输出 {"choice": 0..K}                      → Fleiss κ（类别）+ 与金标比较（gold_align.jsonl 时）

退化守卫：任一模型对某个代码给出常数（方差 0）→ 该代码的一致性记为 null 并给 blocked_reason，
绝不把 pingouin 在方差为 0 时安静吐出的 -1 / NaN 当结果。打分类任务至少用 7B 模型；0.6B/1.7B 只够验通路。
"""
import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

FEATURES_BIN = ["reversal", "death_parting", "reunion", "romance", "aphorism", "humor"]
FEATURES_ORD = ["conflict", "sensory", "suspense"]
SCENE_TYPES = ["dialogue", "action", "description", "introspection", "summary", "letter"]
EMO = ["moved", "heartbreak", "anger", "amusement", "shock", "comfort", "swoon", "suspense", "resonance", "aesthetic"]
MAX_TOKENS = {"features": 120, "emotion": 120, "align": 20}


def parse_json(s):
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    m = re.search(r"\{.*?\}", s, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def to01(v):
    return int(v) if v in (0, 1, "0", "1", True, False) else None


def parse(task, txt, k=8):
    j = parse_json(txt)
    if not isinstance(j, dict):
        return None
    if task == "features":
        out = {"scene_type": j.get("scene_type") if j.get("scene_type") in SCENE_TYPES else None}
        for c in FEATURES_BIN:
            out[c] = to01(j.get(c))
        for c in FEATURES_ORD:
            try:
                v = int(j.get(c)); out[c] = v if v in (0, 1, 2) else None
            except Exception:
                out[c] = None
        return out
    if task == "emotion":
        return {c: to01(j.get(c)) for c in EMO}
    if task == "align":
        try:
            v = int(j.get("choice"))
            return {"choice": v if 0 <= v <= k else None}
        except Exception:
            return {"choice": None}


def env_stamp(out, args):
    import torch, vllm, transformers
    def _git(d):
        try:
            return subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip() or None
        except Exception:
            return None
    stamp = {"run_at": datetime.now().isoformat(timespec="seconds"), "host": platform.node(),
             "gpu": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
             "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
             "python": sys.version.split()[0], "torch": torch.__version__, "vllm": vllm.__version__,
             "transformers": transformers.__version__, "models": args.models, "task": args.task,
             "argv": sys.argv, "script_git": _git(Path(__file__).parent), "seed": 0, "temperature": 0.0}
    (out / "_env_stamp.json").write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8")


def fleiss_kappa(table):
    """table: n_items x n_categories 计数矩阵（每行和 = 评分者数）。"""
    import numpy as np
    t = np.asarray(table, float)
    n_raters = t.sum(1)[0]
    p_j = t.sum(0) / t.sum()
    P_i = ((t * t).sum(1) - n_raters) / (n_raters * (n_raters - 1))
    Pbar, Pe = P_i.mean(), (p_j ** 2).sum()
    if Pe >= 1 - 1e-12:
        return None
    return float((Pbar - Pe) / (1 - Pe))


def agreement_categorical(values_by_model, cats):
    """values_by_model: {model: {id: value}} → Fleiss κ + 两两一致率；含退化守卫。"""
    import numpy as np
    models = list(values_by_model)
    common = sorted(set.intersection(*(set(k for k, v in d.items() if v is not None) for d in values_by_model.values())))
    distinct = {m: sorted({values_by_model[m][i] for i in common}, key=str) for m in models}
    degenerate = {m: d for m, d in distinct.items() if len(d) <= 1}
    res = {"n_common": len(common), "distinct_values": {m: [str(x) for x in d] for m, d in distinct.items()},
           "constant_raters": {m: [str(x) for x in d] for m, d in degenerate.items()}}
    if degenerate or len(common) < 5 or len(models) < 2:
        res["fleiss_kappa"] = None
        res["blocked_reason"] = ("模型退化：%s 对全部条目给了同一个值" % "、".join(degenerate)) if degenerate else "共有条目或模型数不足"
        return res
    table = np.zeros((len(common), len(cats)))
    for r, i in enumerate(common):
        for m in models:
            table[r, cats.index(values_by_model[m][i])] += 1
    res["fleiss_kappa"] = fleiss_kappa(table)
    res["pairwise_agreement"] = {f"{a}|{b}": float(np.mean([values_by_model[a][i] == values_by_model[b][i] for i in common]))
                                 for a, b in combinations(models, 2)}
    return res


def agreement_icc(values_by_model):
    import pandas as pd, pingouin as pg
    models = list(values_by_model)
    common = sorted(set.intersection(*(set(k for k, v in d.items() if v is not None) for d in values_by_model.values())))
    long = pd.DataFrame([{"target": i, "rater": m, "score": values_by_model[m][i]} for m in models for i in common])
    degenerate = {m: sorted(set(values_by_model[m][i] for i in common)) for m in models
                  if len(set(values_by_model[m][i] for i in common)) <= 1}
    res = {"n_common": len(common), "constant_raters": degenerate}
    between = float(long.groupby("target")["score"].mean().var(ddof=1)) if common else 0.0
    if degenerate or between == 0 or len(common) < 5 or len(models) < 2:
        res["icc"] = None
        res["blocked_reason"] = "模型退化或组间方差为 0 / 条目不足，ICC 无定义"
        return res
    icc = pg.intraclass_corr(data=long, targets="target", raters="rater", ratings="score").set_index("Type")
    ci = "CI95" if "CI95" in icc.columns else "CI95%"
    res["icc"] = {t.lower().replace("(", "").replace(")", "").replace(",", "_"):
                  {"value": round(float(icc.loc[t, "ICC"]), 4), "ci95_low": round(float(icc.loc[t, ci][0]), 4),
                   "ci95_high": round(float(icc.loc[t, ci][1]), 4)} for t in icc.index}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=["features", "emotion", "align"])
    ap.add_argument("--items", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--gpu-util", type=float, default=0.88)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out); (out / "raw").mkdir(parents=True, exist_ok=True)
    items = [json.loads(l) for l in Path(a.items).read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.limit:
        items = items[: a.limit]
    print(f"[i] {a.task}: {len(items)} 条 × {len(a.models)} 个模型", flush=True)
    env_stamp(out, a)
    from vllm import LLM, SamplingParams
    from transformers import AutoTokenizer
    parsed = {}
    for m in a.models:
        tok = AutoTokenizer.from_pretrained(m)
        kw = {"enable_thinking": False} if "Qwen3" in m else {}
        prompts = [tok.apply_chat_template([{"role": "user", "content": it["prompt"]}], tokenize=False,
                                           add_generation_prompt=True, **kw) for it in items]
        llm = LLM(model=m, gpu_memory_utilization=a.gpu_util, max_model_len=a.max_model_len, enforce_eager=True,
                  disable_log_stats=True, trust_remote_code=True)
        outs = llm.generate(prompts, SamplingParams(temperature=0.0, max_tokens=MAX_TOKENS[a.task]))
        rows, d = [], {}
        for it, o in zip(items, outs):
            txt = o.outputs[0].text
            p = parse(a.task, txt, k=len(it.get("cand_sids", [])) or 8)
            d[it["id"]] = p
            rows.append({"id": it["id"], "raw": txt.strip()[:300], "parsed": p})
        (out / "raw" / (m.replace("/", "__") + ".jsonl")).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        parsed[m] = d
        print(f"[i] {m}: 解析成功 {sum(v is not None for v in d.values())}/{len(items)}", flush=True)
        del llm
        import gc, torch; gc.collect(); torch.cuda.empty_cache()

    res = {"task": a.task, "n_items": len(items), "models": a.models,
           "prompt_versions": sorted({it.get("prompt_version") for it in items}),
           "parse_rate": {m: round(sum(v is not None for v in parsed[m].values()) / len(items), 4) for m in a.models},
           "agreement": {}}
    if a.task == "features":
        res["agreement"]["scene_type"] = agreement_categorical(
            {m: {i: (v or {}).get("scene_type") for i, v in parsed[m].items()} for m in a.models}, SCENE_TYPES)
        for c in FEATURES_BIN:
            res["agreement"][c] = agreement_categorical({m: {i: (v or {}).get(c) for i, v in parsed[m].items()} for m in a.models}, [0, 1])
        for c in FEATURES_ORD:
            res["agreement"][c] = agreement_icc({m: {i: (v or {}).get(c) for i, v in parsed[m].items()} for m in a.models})
    elif a.task == "emotion":
        for c in EMO:
            res["agreement"][c] = agreement_categorical({m: {i: (v or {}).get(c) for i, v in parsed[m].items()} for m in a.models}, [0, 1])
    else:
        k = max(len(it.get("cand_sids", [])) for it in items)
        res["agreement"]["choice"] = agreement_categorical(
            {m: {i: (v or {}).get("choice") for i, v in parsed[m].items()} for m in a.models}, list(range(0, k + 1)))
        # 多数票落盘，供本机 pipeline 读回（mentions_llm）
        maj = []
        for it in items:
            votes = [parsed[m][it["id"]]["choice"] for m in a.models if parsed[m].get(it["id"]) and parsed[m][it["id"]]["choice"] is not None]
            ch = max(set(votes), key=votes.count) if votes else None
            if ch is not None and votes.count(ch) * 2 <= len(a.models):
                ch = None   # 无多数 → 不计
            maj.append({"id": it["id"], "book": it["book"], "review_id": it["review_id"], "sent_idx": it["sent_idx"],
                        "choice": ch, "sid": it["cand_sids"][ch - 1] if ch else None, "votes": votes})
        (out / "majority.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in maj), encoding="utf-8")
    res["diagnostics"] = {"computed": list(res["agreement"].keys())}
    (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res["agreement"], ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
