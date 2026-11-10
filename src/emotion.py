"""评论情绪（多标签）。编码手册见 docs/CODEBOOK.md §1。

三个打标器，输出同一套标签：
  lexicon   词典/正则基线（透明、可审计、零成本；中英双语词表，中文词表供微信读书类数据使用）
  goemo     SamLowe/roberta-base-go_emotions（MIT，GoEmotions 28 类）→ 映射到本手册的标签
  llm       按编码手册提示 LLM 输出 JSON（正式运行在 GPU 服务器，见 server/）
"""
from __future__ import annotations

import re

LABELS = ["moved", "heartbreak", "anger", "amusement", "shock", "comfort", "swoon", "suspense", "resonance", "aesthetic"]
LABEL_ZH = {"moved": "感动", "heartbreak": "意难平/心碎", "anger": "愤怒", "amusement": "好笑", "shock": "震撼/意外",
            "comfort": "治愈/释然", "swoon": "心动", "suspense": "紧张/恐惧", "resonance": "共鸣/认同",
            "aesthetic": "文笔赞叹"}

_EN = {
    "moved": r"\b(cr(y|ied|ying)|tears?|teary|tearing up|sobb?(ed|ing)?|weep|wept|moving|touching|touched me|"
             r"choked up|lump in my throat|goosebumps|so moved|emotional)\b",
    "heartbreak": r"\b(heart ?break(ing)?|heart-?broken|broke my heart|devastat(ed|ing)|tragic|tragedy|so sad|"
                  r"saddest|sad|depress(ed|ing)|poor (thing|girl|man|boy|\w+)|gutted|wrenching|haunting|"
                  r"melanchol(y|ic)|bittersweet|if only|wish(ed)? (he|she|they) had|unrequited|lonely|loneliness)\b",
    "anger": r"\b(hate[ds]?|hating|angry|anger|furious|infuriat(ed|ing)|annoy(ed|ing)|irritat(ed|ing)|"
             r"despise[ds]?|disgust(ed|ing)?|despicable|loathe?|rage|frustrat(ed|ing)|selfish|jerk|idiot|"
             r"awful (man|woman|person)|wanted to (slap|punch|strangle)|can'?t stand|insufferable|vile)\b",
    "amusement": r"\b(funny|funniest|hilarious|laugh(ed|ing)?|lol|haha+|giggl(e|ed|ing)|witty|wit|humou?r(ous)?|"
                 r"amus(ed|ing)|comic(al)?|chuckl(e|ed)|snark(y)?|sarcas(m|tic)|cracked me up)\b",
    "shock": r"\b(shock(ed|ing)?|stunn(ed|ing)|twist|didn'?t see (it|that) coming|wow|whoa|omg|mind[- ]?blow(ing|n)|"
             r"jaw[- ]?drop(ping)?|surpris(ed|ing)|unexpected|blown away|gasp(ed)?|chills|powerful|"
             r"intense|explosive|climax)\b",
    "comfort": r"\b(heart-?warming|sweet|happy ending|reliev(ed|ing)|relief|satisf(ying|ied)|uplifting|"
               r"hope(ful)?|comfort(ing)?|cozy|warm(th)?|joy(ful)?|delight(ed|ful)|finally (together|happy)|"
               r"happy for|glad|smil(e|ed|ing))\b",
    "swoon": r"\b(swoon(ed|ing|y)?|romantic|romance|chemistry|kiss(ed|es|ing)?|proposal|propos(ed|es)|"
             r"in love|fell for|crush|sigh(ed)?|my heart (melted|fluttered)|be still my heart|"
             r"ardently|book boyfriend|love story|passion(ate)?)\b",
    "suspense": r"\b(creepy|scar(y|ed)|terrif(ying|ied)|eerie|chilling|dread|tense|tension|suspense(ful)?|"
                r"edge of my seat|gothic|haunted|ominous|frighten(ing|ed)|horror|spooky|nervous|anxious)\b",
    "resonance": r"\b(so true|relatable|relate[ds]?|resonat(ed|es|ing)|i felt (that|seen)|spoke to me|"
                 r"wisdom|wise|profound|timeless|still (true|relevant)|life lesson|lesson|insight(ful)?|"
                 r"true today|universal|applies to|reminds me of (my|myself))\b",
    "aesthetic": r"\b(beautiful(ly)?|gorgeous|lyrical|poetic|prose|eloquent|exquisite|masterful|"
                 r"brilliant(ly)? written|well[- ]written|writing style|imagery|vivid|stunning (writing|prose)|"
                 r"symbolism|metaphor)\b",
}
_ZH = {
    "moved": r"(感动|泪目|哭了|流泪|眼眶|泪奔|动容|破防)",
    "heartbreak": r"(意难平|心疼|心碎|虐|难过|遗憾|悲伤|悲剧|可惜|唏嘘|惋惜)",
    "anger": r"(气死|愤怒|可恶|讨厌|恶心|渣|无语|生气|气愤)",
    "amusement": r"(哈哈|笑死|好笑|搞笑|幽默|笑出声|有趣)",
    "shock": r"(震撼|震惊|反转|没想到|卧槽|天哪|惊了|炸裂)",
    "comfort": r"(治愈|温暖|释然|欣慰|甜|幸福|暖心)",
    "swoon": r"(心动|告白|表白|求婚|浪漫|甜蜜|磕到)",
    "suspense": r"(紧张|恐怖|害怕|吓人|毛骨悚然|揪心)",
    "resonance": r"(共鸣|说得对|太真实|深有同感|扎心|人间清醒|道理)",
    "aesthetic": r"(文笔|优美|写得好|描写|意境)",
}
_RE = {k: re.compile(v, re.I) for k, v in _EN.items()}
_RE_ZH = {k: re.compile(v) for k, v in _ZH.items()}


def lexicon(text: str) -> dict[str, int]:
    return {k: int(bool(_RE[k].search(text) or _RE_ZH[k].search(text))) for k in LABELS}


# GoEmotions 28 类 → 本手册。未映射的（neutral/curiosity/confusion/pride/embarrassment/love/nervousness 等）不贡献标签。
GOEMO_MAP = {
    "amusement": "amusement",
    "anger": "anger", "annoyance": "anger", "disgust": "anger", "disapproval": "anger",
    "sadness": "heartbreak", "grief": "heartbreak", "remorse": "heartbreak", "disappointment": "heartbreak",
    "surprise": "shock", "excitement": "shock",
    "fear": "suspense", "nervousness": "suspense",
    "joy": "comfort", "relief": "comfort", "gratitude": "comfort", "optimism": "comfort", "caring": "comfort",
    "desire": "swoon",
    "approval": "resonance", "realization": "resonance",
    "admiration": "aesthetic",
}
GOEMO_MODEL = "SamLowe/roberta-base-go_emotions"


class GoEmo:
    def __init__(self, threshold: float = 0.5, batch_size: int = 64):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(GOEMO_MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(GOEMO_MODEL).half().cuda().eval()
        self.id2label = self.model.config.id2label
        self.th = threshold
        self.bs = batch_size
        self.torch = torch

    def probs(self, texts: list[str]):
        import numpy as np
        out = []
        for i in range(0, len(texts), self.bs):
            enc = self.tok(texts[i:i + self.bs], truncation=True, max_length=256, padding=True, return_tensors="pt").to("cuda")
            with self.torch.no_grad():
                p = self.torch.sigmoid(self.model(**enc).logits.float()).cpu().numpy()
            out.append(p)
        return np.concatenate(out) if out else np.zeros((0, len(self.id2label)))

    def label(self, texts: list[str]) -> tuple[list[dict], list[dict]]:
        P = self.probs(texts)
        labs, raw = [], []
        for row in P:
            d = {k: 0 for k in LABELS}
            fired = {}
            for j, p in enumerate(row):
                name = self.id2label[j]
                if p >= self.th:
                    fired[name] = round(float(p), 3)
                    if name in GOEMO_MAP:
                        d[GOEMO_MAP[name]] = 1
            labs.append(d); raw.append(fired)
        return labs, raw


EMO_PROMPT_VER = "emotion_v1"
EMO_PROMPT = """You annotate the EMOTIONS a reader expresses about a moment in the novel "{title}".
Only the reader's OWN words count. Text the reader quotes from the novel does not count: an emotional word inside a quotation is the character's, not the reader's.
Codebook (multi-label; mark 1 only if the reader clearly expresses it):
- moved: touched, tears, deeply moved
- heartbreak: sadness, grief, lingering regret ("if only"), pity for a character
- anger: anger/annoyance/disgust at a character or event
- amusement: finds it funny or witty
- shock: surprise, a twist, stunned, "wow", intense impact
- comfort: warmth, relief, joy, satisfaction, heart-warming
- swoon: romantic attraction, swooning over a couple or a love declaration
- suspense: fear, dread, tension, creepiness
- resonance: finds it true/wise/relatable, applies it to life
- aesthetic: admires the writing itself (beautiful prose, imagery)

Reader text: "{text}"

Reply ONLY with JSON using exactly these keys and 0/1 values:
{{"moved":0,"heartbreak":0,"anger":0,"amusement":0,"shock":0,"comfort":0,"swoon":0,"suspense":0,"resonance":0,"aesthetic":0}}"""
