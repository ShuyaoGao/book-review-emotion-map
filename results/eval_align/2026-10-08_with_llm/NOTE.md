# 说明（2026-11-10 补记，原 result.json 未改）

本运行 `result.json` 中 `plot.retrieval.recall_at_5` 的**键名有误**：当时的代码对全部检索候选计数，而本运行的候选数是 TOPK = 8（见 `raw/plot_C.jsonl`，每条 8 个 `cand_sids`），所以该值 24/36 = 66.7% 实际是 **recall@8**。

正确的 top-1 / top-5 / top-8 召回（8/36、19/36、24/36）由 `src/recompute_retrieval.py` 从本目录 `raw/plot_C.jsonl` 重算，没有重新检索，结果在 `../2026-11-10_retrieval_recount/result.json`。

`2026-10-08_baselines` 运行时 TOPK = 5，那里的 `recall_at_5`（19/36）键名正确。
