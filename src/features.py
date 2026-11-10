"""桥段（场景）特征。编码手册见 docs/CODEBOOK.md §2。

rule_features(scene)  规则/词典基线：透明、零成本，是 mock 标注器，也是 LLM 标注的对照。
FEATURE_PROMPT        LLM 按编码手册标注（正式运行在 GPU 服务器，多模型 + 一致性）。
"""
from __future__ import annotations

import re

FEATURES_BIN = ["reversal", "death_parting", "reunion", "romance", "aphorism", "humor"]
FEATURES_ORD = ["conflict", "sensory", "suspense"]          # 0/1/2
SCENE_TYPES = ["dialogue", "action", "description", "introspection", "summary", "letter"]

_LEX = {
    "death_parting": r"\b(die[ds]?|dying|dead|death|killed|kill|murder(ed)?|funeral|grave|corpse|buried|"
                     r"farewell|good-?bye|adieu|parted|parting|depart(ed|ure)|leave you|left (him|her|me)|"
                     r"never see (him|her|you) again|gone forever)\b",
    "reunion": r"\b(met again|meet again|see (you|him|her) again|returned|came back|come back|recogni[sz]ed|"
               r"reunion|reunited|once more|after (all these|so many|five) years|at last)\b",
    "reversal": r"\b(discover(ed|y)|secret|truth|confess(ed|ion)?|reveal(ed)?|learn(ed|t) that|found out|"
                r"astonish(ed|ment)|amaze(d|ment)|surprise[d]?|could not believe|mistaken|deceiv(ed|e)|"
                r"lie[ds]?|in fact|it was (he|she|him|her)|impossible)\b",
    "conflict": r"\b(angr(y|ily)|anger|quarrel|accus(e|ed|ation)|refuse[ds]?|insult(ed)?|shout(ed)?|cr(y|ied) out|"
                r"fight|fought|struck|strike|hit|furious|resent(ment)?|reproach|indignant|indignation|"
                r"how dare|contempt|threat(en(ed)?)?|violen(t|ce)|scream(ed)?)\b",
    "romance": r"\b(love[ds]?|loving|lover|marr(y|ied|iage)|propos(e|al|ed)|kiss(ed|es)?|heart|ardent(ly)?|"
               r"admire|admiration|affection|darling|dearest|embrace[d]?|tender(ly|ness)?|passion)\b",
    "sensory": r"\b(red|blue|green|gold(en)?|white|black|grey|gray|yellow|silver|pale|bright|dark|shadow|light|"
               r"sound|noise|voice|music|whisper(ed)?|silence|smell|scent|odou?r|perfume|taste|sweet|bitter|"
               r"cold|warm|hot|wet|soft|rough|wind|rain|snow|sun|moon|fire|flame|glow|glitter)\b",
    "suspense": r"\b(fear|afraid|terror|terrified|dread|horror|ghost|strange|mysterious|darkness|scream|"
                r"trembl(e|ed|ing)|shudder(ed)?|danger|alarm(ed)?|startled|creep|silent|midnight|blood)\b",
    "humor": r"\b(laugh(ed|ing|ter)?|smil(e|ed)|joke|jest|ridiculous|absurd|droll|comic|amus(ed|ing)|merr(y|iment))\b",
}
_RE = {k: re.compile(v, re.I) for k, v in _LEX.items()}

GENERIC_TERMS = re.compile(r"\b(man|men|woman|women|people|person|life|love|world|nothing|everything|everybody|"
                           r"nobody|one|all|every|always|never|human|nature|happiness|heart|mind|truth|"
                           r"society|marriage|money|time|past|future)\b", re.I)
PRESENT = re.compile(r"\b(is|are|has|have|can|cannot|can't|must|will|does|do|seems?|makes?)\b", re.I)
PERSONAL = re.compile(r"\b(he|she|him|her|his|hers|i|me|my|mine|we|us|our|you|your|said|cried|replied|"
                      r"was|were|had|did)\b", re.I)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])[\"”’]?\s+", text) if s.strip()]


def aphorisms(text: str, names: list[str]) -> list[str]:
    """格言式句子：一般性陈述（泛指名词 + 现在时），不含人名与人称代词，8–45 词。"""
    out = []
    for s in sentences(text):
        core = s.strip("“”\"' ")
        n = len(core.split())
        if not (8 <= n <= 45):
            continue
        if any(re.search(r"\b" + re.escape(x) + r"\b", core) for x in names):
            continue
        if PERSONAL.search(core) or core.endswith("?"):
            continue
        if GENERIC_TERMS.search(core) and PRESENT.search(core):
            out.append(core)
    return out


def rule_features(scene: dict, names: list[str]) -> dict:
    t = scene["text"]
    w = max(1, scene["n_words"])
    per_k = lambda c: round(1000.0 * c / w, 3)
    f = {k + "_per1k": per_k(len(_RE[k].findall(t))) for k in _LEX}
    aph = aphorisms(t, names)
    f.update({
        "aphorism_n": len(aph),
        "aphorism_any": int(len(aph) > 0),
        "dialogue_ratio": scene["dialogue_ratio"],
        "exclaim_per1k": per_k(t.count("!")),
        "question_per1k": per_k(t.count("?")),
        "n_names": len({x for x in names if re.search(r"\b" + re.escape(x) + r"\b", t)}),
    })
    return f, aph


CODE_RULE = {  # 代码 -> (连续特征, 类型)。阈值 = 全部场景上的分位数：二值取 P80；有序取 P50/P85。事先规定，不按结果调。
    "conflict": ("conflict_per1k", "ord"), "reversal": ("reversal_per1k", "bin"),
    "death_parting": ("death_parting_per1k", "bin"), "reunion": ("reunion_per1k", "bin"),
    "romance": ("romance_per1k", "bin"), "sensory": ("sensory_per1k", "ord"),
    "humor": ("humor_per1k", "bin"), "suspense": ("suspense_per1k", "ord"),
}


def code_thresholds(feature_rows: list[dict]) -> dict:
    import numpy as np
    thr = {}
    for code, (col, kind) in CODE_RULE.items():
        v = np.array([r[col] for r in feature_rows], float)
        thr[code] = [float(np.percentile(v, 80))] if kind == "bin" else [float(np.percentile(v, 50)), float(np.percentile(v, 85))]
    thr["description_sensory"] = float(np.percentile([r["sensory_per1k"] for r in feature_rows], 75))
    return thr


def rule_codes(f: dict, scene: dict, thr: dict) -> dict:
    """把连续的规则特征离散成与 LLM 编码手册同形的代码（mock 标注器）。"""
    codes = {}
    for code, (col, kind) in CODE_RULE.items():
        t = thr[code]
        x = f[col]
        if kind == "bin":
            codes[code] = int(x > 0 and x >= t[0])
        else:
            codes[code] = 0 if (x == 0 or x < t[0]) else (1 if x < t[1] else 2)
    codes["aphorism"] = f["aphorism_any"]
    dr = scene["dialogue_ratio"]
    codes["scene_type"] = "dialogue" if dr >= 0.5 else ("description" if f["sensory_per1k"] >= thr["description_sensory"] else "summary")
    return codes


FEATURE_PROMPT_VER = "features_v1"
FEATURE_PROMPT = """You are a literary annotator. Code the following scene from the novel "{title}" ({author}) using the codebook.

Codebook:
- scene_type: the dominant mode, one of "dialogue", "action", "description", "introspection", "summary", "letter"
- conflict: 0 = none, 1 = mild tension/disagreement, 2 = open confrontation, quarrel or violence
- reversal: 1 if a revelation, discovery, confession or plot twist changes what a character (or the reader) believes; else 0
- death_parting: 1 if a death, a fatal accident, or a significant separation/farewell happens or is learned of; else 0
- reunion: 1 if characters who were separated meet again or someone is recognized; else 0
- romance: 1 if there is a love declaration, proposal, kiss, or an explicitly romantic moment; else 0
- aphorism: 1 if the scene contains a quotable, maxim-like general statement about life/people; else 0
- sensory: 0 = little, 1 = some, 2 = rich sensory imagery (colour, sound, smell, touch)
- humor: 1 if the scene is clearly comic or witty; else 0
- suspense: 0 = none, 1 = some unease, 2 = strong fear/dread/tension

Scene:
\"\"\"{text}\"\"\"

Reply ONLY with JSON:
{{"scene_type":"...","conflict":0,"reversal":0,"death_parting":0,"reunion":0,"romance":0,"aphorism":0,"sensory":0,"humor":0,"suspense":0}}"""


def build_feature_prompt(book: dict, scene: dict, max_words: int = 900) -> str:
    words = scene["text"].split()
    text = " ".join(words[:max_words]) + (" [...]" if len(words) > max_words else "")
    return FEATURE_PROMPT.format(title=book["title"], author=book["author"], text=text)


def validate_codes(j) -> dict | None:
    if not isinstance(j, dict):
        return None
    out = {}
    st = j.get("scene_type")
    out["scene_type"] = st if st in SCENE_TYPES else None
    for k in FEATURES_BIN:
        v = j.get(k)
        out[k] = int(v) if v in (0, 1, "0", "1", True, False) else None
    for k in FEATURES_ORD:
        try:
            v = int(j.get(k))
            out[k] = v if v in (0, 1, 2) else None
        except Exception:
            out[k] = None
    return out
