"""LLM 后端统一接口。

  get_backend("mock")                       -> None（调用方走规则/词典分支）
  get_backend("hf:Qwen/Qwen3-1.7B")         -> 本机 transformers，bf16，贪心解码（显存预算 <= 4GB，只用于冒烟）
  get_backend("vllm:Qwen/Qwen2.5-7B-Instruct") -> GPU 服务器 vLLM（正式运行；见 server/llm_annotate.py）

所有后端都实现 generate(prompts: list[str], max_tokens: int) -> list[str]，temperature=0，可复现。
原始输出由调用方逐条写入 raw/*.jsonl。
"""
from __future__ import annotations

import json
import re


class HFBackend:
    def __init__(self, model: str, max_vram_gb: float = 4.0, batch_size: int = 1):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.name = f"hf:{model}"
        self.model_id = model
        self.tok = AutoTokenizer.from_pretrained(model)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(model, dtype=torch.bfloat16).to("cuda")
        self.model.eval()
        self.batch_size = batch_size
        self.max_vram_gb = max_vram_gb
        self.torch = torch
        torch.cuda.reset_peak_memory_stats()

    def _chat(self, p: str) -> str:
        kw = {"enable_thinking": False} if "Qwen3" in self.model_id else {}
        return self.tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False,
                                            add_generation_prompt=True, **kw)

    def generate(self, prompts: list[str], max_tokens: int = 64) -> list[str]:
        outs = []
        torch = self.torch
        for i in range(0, len(prompts), self.batch_size):
            chunk = [self._chat(p) for p in prompts[i:i + self.batch_size]]
            enc = self.tok(chunk, return_tensors="pt", padding=True).to("cuda")
            with torch.no_grad():
                g = self.model.generate(**enc, max_new_tokens=max_tokens, do_sample=False,
                                        pad_token_id=self.tok.pad_token_id)
            for row in g[:, enc["input_ids"].shape[1]:]:
                outs.append(self.tok.decode(row, skip_special_tokens=True))
            peak = torch.cuda.max_memory_allocated() / 2**30
            if peak > self.max_vram_gb:
                raise RuntimeError(f"显存峰值 {peak:.2f} GB 超出预算 {self.max_vram_gb} GB；减小 batch 或换小模型")
        return outs

    def peak_vram_gb(self) -> float:
        return round(self.torch.cuda.max_memory_allocated() / 2**30, 3)

    def close(self):
        import gc
        del self.model
        gc.collect(); self.torch.cuda.empty_cache()


class VLLMBackend:
    def __init__(self, model: str, gpu_util: float = 0.85, max_model_len: int = 8192):
        from transformers import AutoTokenizer
        from vllm import LLM
        self.name = f"vllm:{model}"
        self.model_id = model
        self.tok = AutoTokenizer.from_pretrained(model)
        self.llm = LLM(model=model, gpu_memory_utilization=gpu_util, max_model_len=max_model_len,
                       enforce_eager=True, disable_log_stats=True, trust_remote_code=True)

    def generate(self, prompts: list[str], max_tokens: int = 64) -> list[str]:
        from vllm import SamplingParams
        kw = {"enable_thinking": False} if "Qwen3" in self.model_id else {}
        chats = [self.tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False,
                                              add_generation_prompt=True, **kw) for p in prompts]
        outs = self.llm.generate(chats, SamplingParams(temperature=0.0, max_tokens=max_tokens))
        return [o.outputs[0].text for o in outs]

    def peak_vram_gb(self):
        return None

    def close(self):
        import gc, torch
        del self.llm
        gc.collect(); torch.cuda.empty_cache()


def get_backend(spec: str):
    if spec in (None, "", "mock"):
        return None
    kind, _, model = spec.partition(":")
    if kind == "hf":
        return HFBackend(model)
    if kind == "vllm":
        return VLLMBackend(model)
    raise ValueError(spec)


def parse_json_obj(s: str):
    """从模型输出里抠出第一个 JSON 对象；失败返回 None（记为缺失，不是 0）。"""
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        return None
    txt = m.group(0)
    for cand in (txt, txt[: txt.rfind("}") + 1]):
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


def parse_int(s: str, lo: int, hi: int):
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    for t in re.findall(r"-?\d+", s):
        v = int(t)
        if lo <= v <= hi:
            return v
    return None
