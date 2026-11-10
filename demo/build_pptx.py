"""生成项目根目录的 讲解.pptx（面向基础不高的听众，按“需求 → 资料 → 方法 → 步骤 → 结果 → 成品 → 局限”顺序，带演讲者备注）。

  python demo/build_pptx.py          # 需要 python-pptx（全局 Python 已装）

数字全部从 results/*/result.json 与 showcase/data.json 读取；少数只在文档里的数字（标注了出处）直接引用 docs/EVALUATION.md。
配图：showcase/figs/ 下已有的 PNG + demo/screenshots/ 截图；示意图用 PowerPoint 原生形状画，可直接编辑。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "讲解.pptx"
FIGS = ROOT / "showcase" / "figs"
SHOTS = ROOT / "demo" / "screenshots"


def J(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


# ---------------- 数字（全部有出处） ----------------
DATA = J("showcase/data.json")
EVA = J("results/eval_align/2026-10-08_with_llm/result.json")
EVA_BASE = J("results/eval_align/2026-10-08_baselines/result.json")
EVE = J("results/eval_emotion/2026-10-08/result.json")
SIM = J("results/heat_sim/2026-10-08/result.json")
AN = J("results/analysis/2026-10-08_quoteonly_goemo/result.json")
SEG = J("results/segment/2026-10-08/result.json")
EMO = J("results/emotion/2026-10-08_quoteonly/result.json")

BOOKS = ["gatsby", "pride", "janeeyre"]
ZH = {b: DATA["books"][b]["title_zh"] for b in BOOKS}
N_REV = {b: DATA["books"][b]["n_reviews"] for b in BOOKS}
N_SC = {b: DATA["books"][b]["seg"]["n_scenes"] for b in BOOKS}
N_REV_ALL = sum(N_REV.values())
N_SC_ALL = sum(N_SC.values())
QA = EVA["quote"]["A_precision"]
QBR = EVA["quote"]["B"]["recall"]
QA_CI = QA["ci95_low"]
PLOT = EVA["plot"]
R1 = PLOT["retrieval"]["recall_at_1"]
RECOUNT = J("results/eval_align/2026-11-10_retrieval_recount/result.json")   # 由 with_llm 运行的 raw 重算（见该运行 NOTE.md）
R5 = RECOUNT["plot"]["retrieval"]["recall_at_5"]
R8 = RECOUNT["plot"]["retrieval"]["recall_at_8"]
BASE_RATE = PLOT["retrieval"]["base_rate_specific"]
T_MOCK = PLOT["test"]["mock_default"]
T_NONE = PLOT["test"]["always_none"]
T_LLM = PLOT["llm"]["Qwen__Qwen3-1.7B"]["test"]
SIMM = SIM["metrics"]
HEAT = AN["heat"]["mentions.adjusted"]
EFF = {e["feature"]: e for e in HEAT["effects"]}
APH = EFF["aphorism_n"]
FIRST = math.exp(HEAT["control_coefs"]["book_first"]["coef"])
LAST = math.exp(HEAT["control_coefs"]["book_last"]["coef"])
DISP = HEAT["pearson_dispersion"]
NCL = HEAT["n_clusters"]
BARE = {b: EMO["books"][b]["bare_quote_share"] for b in BOOKS}
PROFILE = AN["position_profile"]["quote_per_10k_words"]


def pc(x, d=0):
    return f"{x * 100:.{d}f}%"


# ---------------- 版式 ----------------
INK = RGBColor(0x15, 0x19, 0x1D)
INK2 = RGBColor(0x4A, 0x51, 0x58)
MUTED = RGBColor(0x7D, 0x84, 0x8A)
RULE = RGBColor(0xDF, 0xE2, 0xE0)
PAPER = RGBColor(0xF5, 0xF6, 0xF3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MARK = RGBColor(0xFF, 0xE3, 0x6B)
NAVY = RGBColor(0x1C, 0x24, 0x2E)
BLUE = RGBColor(0x2A, 0x78, 0xD6)
ORANGE = RGBColor(0xEB, 0x68, 0x34)
GREEN = RGBColor(0x1B, 0xAF, 0x7A)
AMBER = RGBColor(0xED, 0xA1, 0x00)
RED = RGBColor(0xD0, 0x3B, 0x3B)
TAGS = {  # 方法类型标签：颜色固定，全篇一致
    "深度学习": (BLUE, WHITE),
    "传统机器学习": (ORANGE, WHITE),
    "统计": (GREEN, WHITE),
    "规则": (AMBER, INK),
}
FONT = "Microsoft YaHei"
SERIF = "Georgia"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = 13.333, 7.5


def set_font(run, name=FONT, size=16, bold=False, color=INK, italic=False):
    f = run.font
    f.name, f.size, f.bold, f.italic = name, Pt(size), bold, italic
    f.color.rgb = color
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            rpr.append(el)
        el.set("typeface", FONT if name == SERIF and tag == "a:ea" else name)


def text(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, margin=0.0, space_after=6, line=1.15):
    """paras: list of str or (str, dict) or list-of-runs [(str, dict), ...]."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", Inches(margin))
    first = True
    for p in paras:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = align
        para.space_after = Pt(space_after)
        para.line_spacing = line
        runs = p if isinstance(p, list) else [p]
        for r in runs:
            s, o = (r, {}) if isinstance(r, str) else r
            o = dict(o)
            bullet = o.pop("bullet", False)
            hl = o.pop("hl", False)
            run = para.add_run()
            run.text = ("•  " if bullet else "") + s
            set_font(run, **o)
            if hl:  # 荧光笔：文字高亮（a:highlight 必须紧跟在 solidFill 之后）
                rpr = run._r.get_or_add_rPr()
                h = rpr.makeelement(qn("a:highlight"), {})
                c = h.makeelement(qn("a:srgbClr"), {"val": "FFE36B"})
                h.append(c)
                rpr.find(qn("a:solidFill")).addnext(h)
    return tb


def rect(slide, x, y, w, h, fill=PAPER, line=None, shape=MSO_SHAPE.RECTANGLE, radius=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def box(slide, x, y, w, h, paras, fill=PAPER, line=None, pad=0.15, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, rounded=True, space_after=4):
    rect(slide, x, y, w, h, fill, line, MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE, 0.06 if rounded else None)
    return text(slide, x + pad, y + pad, w - 2 * pad, h - 2 * pad, paras, anchor=anchor, align=align, space_after=space_after)


def arrow(slide, x1, y1, x2, y2, color=MUTED, width=2):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def tags(slide, labels, y=0.55):
    x = SW - 0.6
    for lab in reversed(labels):
        bg, fg = TAGS[lab]
        w = 0.32 + 0.2 * len(lab)
        x -= w
        rect(slide, x, y, w, 0.38, bg, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
        text(slide, x, y, w, 0.38, [(lab, {"size": 12, "bold": True, "color": fg})], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
        x -= 0.12


def title(slide, t, sub=None, tag_list=None):
    text(slide, 0.6, 0.42, 9.6 if tag_list else 12.1, 0.75, [(t, {"size": 32, "bold": True})], anchor=MSO_ANCHOR.MIDDLE)
    if sub:
        text(slide, 0.6, 1.15, 12.1, 0.45, [(sub, {"size": 15, "color": INK2})])
    if tag_list:
        tags(slide, tag_list)


def stat(slide, x, y, w, num, label, size=40, sub=None):
    # 荧光笔：数字下方一条黄色划线（全篇唯一的强调手段）
    rect(slide, x, y + size / 72 * 0.62, min(w, 0.32 * len(num) * size / 40 + 0.3), size / 72 * 0.42, MARK)
    text(slide, x, y, w, size / 72 * 1.25, [(num, {"size": size, "bold": True, "name": "Arial"})])
    text(slide, x, y + size / 72 * 1.25, w, 0.7, [(label, {"size": 15, "color": INK2})])
    if sub:
        text(slide, x, y + size / 72 * 1.25 + 0.42, w, 0.4, [(sub, {"size": 13, "color": MUTED})])


def footer(slide, src):
    text(slide, 0.6, 7.0, 12.1, 0.3, [(src, {"size": 10, "color": MUTED})])


def new(dark=False):
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY if dark else WHITE
    return s


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def pic(slide, path, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)

def table(slide, x, y, col_w, rows, size=15, row_h=0.55, head_size=None, wrap_first_bold=False):
    tb = slide.shapes.add_table(len(rows), len(col_w), Inches(x), Inches(y), Inches(sum(col_w)), Inches(row_h * len(rows))).table
    for j, w in enumerate(col_w):
        tb.columns[j].width = Inches(w)
    for i, r in enumerate(rows):
        tb.rows[i].height = Inches(row_h)
        for j, v in enumerate(r):
            c = tb.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = NAVY if i == 0 else (PAPER if i % 2 else WHITE)
            c.margin_left = c.margin_right = Inches(0.1)
            c.margin_top = c.margin_bottom = Inches(0.05)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame
            tf.word_wrap = True
            runs = v if isinstance(v, list) else [(v, {})]
            p = tf.paragraphs[0]
            for t, o in runs:
                run = p.add_run()
                run.text = t
                o = dict(o)
                col = o.pop("color", WHITE if i == 0 else INK)
                set_font(run, size=(head_size or size) if i == 0 else size, bold=(i == 0) or (wrap_first_bold and j == 0) or o.pop("bold", False), color=col)
    return tb


def tagcell(lab):
    return [(lab, {"color": TAGS[lab][0] if lab != "规则" else RGBColor(0xB0, 0x76, 0x00), "bold": True})]


def bullets(slide, x, y, w, h, items, size=20, gap=12):
    text(slide, x, y, w, h, [[(t, {"bullet": True, "size": size})] if isinstance(t, str) else t for t in items], space_after=gap)


LIGHT = RGBColor(0xDD, 0xE1, 0xE4)
DIM = RGBColor(0xB9, 0xBF, 0xC3)
PEAK = {b: DATA["books"][b]["highlights"][0] for b in BOOKS}

# =============== ① 封面 ===============
s = new(dark=True)
text(s, 0.8, 1.7, 11.8, 1.6, [("读者评论 → 桥段热度与情绪地图 · 讲解", {"size": 40, "bold": True, "color": WHITE})])
text(s, 0.8, 3.3, 11.5, 0.6, [("读者在书评里引用的句子，能不能告诉我们：哪一段最打动人？", {"size": 22, "color": LIGHT})])
text(s, 0.8, 4.3, 11.5, 0.5, [("p8-book-emotion · AI 教学演示案例", {"size": 16, "color": DIM})])
text(s, 0.8, 6.4, 11.5, 0.4, [("Shuyao Gao · aSSIST University · 2026-11", {"size": 14, "color": DIM})])
notes(s, "开场。今天讲一个小项目：用读者留下的书评，找出一本书里最打动人的段落，看这些段落引起什么情绪，再变成宣传素材。"
         "先讲最初的需求，再讲我们手上有什么、用了什么方法、一步步怎么做、结果如何，最后看做出来的东西和还没做到的地方。")

# =============== ② 最初的需求 ===============
s = new()
title(s, "最初的需求")
rect(s, 0.9, 1.6, 11.5, 4.3, PAPER, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.04)
text(s, 1.15, 1.45, 1.0, 1.0, [("“", {"size": 72, "bold": True, "color": AMBER, "name": SERIF})])
text(s, 1.6, 1.95, 10.4, 3.9, [
    ("拿微信读书来说，读者翻看书以后会留下对应的评论，这些评论的多少和评论内容，相当于是对这本书很好的标注。", {"size": 20}),
    ("这部分数据有没有机会拿到？或者有没有类似的公开数据？", {"size": 20}),
    ("或者我们去找相关的书评，看看读者对哪一个桥段、环节印象最深刻，然后尝试用大语言模型把这些桥段和环节记录下来，看什么样的桥段会让人产生什么样的情绪，进而用于获客。", {"size": 20}),
], space_after=12, line=1.25)
text(s, 0.9, 6.15, 11.5, 0.5, [("用户原话（语音转写后整理）", {"size": 14, "color": MUTED})])
notes(s, "这是用户最初的原话，语音转写后做了整理，没有改意思。"
         "里面其实有好几个要求：数据能不能拿到、有没有替代数据、找出印象最深的桥段、用大语言模型记录桥段、看桥段和情绪的关系、最后用于获客。下一页逐条拆开。")

# =============== ③ 需求拆解（两页） ===============
OK_, PART, NO_ = GREEN, RGBColor(0xB0, 0x76, 0x00), RED
H3 = ["原话里的要求", "我们理解成什么问题", "做成了什么 / 没做到什么（原因）"]
rows1 = [
    H3,
    ["评论的多少和内容 = 很好的标注", "读者引用一句原文，算不算给这句话投了一票？",
     [("做到：", {"color": OK_, "bold": True}), ("把书评里的引用当作“投票”，算出每段的热度", {})]],
    ["微信读书的数据能不能拿到", "有没有合法、公开的拿法？",
     [("没用：", {"color": NO_, "bold": True}), ("没有公开数据接口；用工具批量抓违反用户协议，2025 年新《反不正当竞争法》也明确禁止。只做了“读用户本人导出文件”的小工具", {})]],
    ["有没有类似的公开数据", "找一份能合法用来做研究的书评数据",
     [("做到：", {"color": OK_, "bold": True}), (f"改用 Goodreads 英文书评 {N_REV_ALL:,} 条（仅限学术研究）+ 公版原文 3 本", {})]],
]
rows2 = [
    H3,
    ["对哪个桥段印象最深", "每一段被多少读者提到？扣掉位置的影响后谁最热？",
     [("做到：", {"color": OK_, "bold": True}), (f"三本书 {N_SC_ALL} 个段落的热度地图，每本书 10 个高光段落", {})]],
    ["用大语言模型把桥段记录下来", "读者没直接引用、只描述情节时，让模型判断他说的是哪一段",
     [("没做到：", {"color": NO_, "bold": True}), ("本机只能跑小模型，准确度太低；需要大模型的 GPU 服务器连不上", {})]],
    ["什么桥段让人产生什么情绪", "读者情绪分几类？什么特点的段落更常被引用？",
     [("部分做到：", {"color": PART, "bold": True}), ("“像格言的句子”更常被引用；但读者引用时很少写感受，情绪信号太少", {})]],
    ["进而用于获客", "能不能变成宣传素材？",
     [("部分做到：", {"color": PART, "bold": True}), ("做出了金句卡（每本 12 张）和短视频切入点清单；没有上线、没测转化；这批数据不能商用", {})]],
]
for k, rows in enumerate((rows1, rows2)):
    s = new()
    title(s, f"需求拆解（{k + 1}/2）")
    table(s, 0.6, 1.5, [3.0, 3.9, 5.2], rows, size=15, row_h=1.15 if k == 0 else 1.0, head_size=15)
    if k == 0:
        notes(s, "第一页拆前三条。第一条“评论就是标注”：标注就像给照片贴标签，我们把读者引用一句原文，看成给这句话投了一票。"
                 "第二条，微信读书的数据为什么没用：它没有对外开放数据的接口；用别人写的工具拿登录信息去批量抓，违反微信读书用户协议 6.1.2.4 和 6.1.2.6 条；"
                 "2025 年修订的反不正当竞争法第十三条第三款也禁止绕开技术措施拿别家的数据。所以我们不抓。只写了一个小工具，读用户自己导出的笔记文件。"
                 f"第三条，替代数据：用了 Goodreads 这个外国读书网站的书评，加州大学圣地亚哥分校整理成了研究数据集，三本书一共 {N_REV_ALL:,} 条，只能做学术研究。")
    else:
        notes(s, "第二页拆后四条。找桥段：做成了热度地图。用大语言模型记录桥段：这一条没做到。读者如果直接引用原文，用普通的文字比对就能找到；"
                 "但如果他只说“盖茨比死的时候我哭了”，就得让大模型去理解。本机显卡只够跑 17 亿参数的小模型，判断得很差；更大的模型要在 GPU 服务器上跑，服务器一直连不上。"
                 "情绪：发现像格言的句子更常被引用，但读者很少写感受。获客：做出了金句卡和切入点清单，这是素材，还没有拿去投放、也没测效果；而且这批数据只能做研究，商用要换数据。")

# =============== ④ 我们手上有什么 ===============
s = new()
title(s, "我们手上有什么")
rows = [
    ["资料", "从哪来", "多少", "真实还是合成"],
    ["读者书评（英文）", "Goodreads 研究数据集（加州大学圣地亚哥分校整理）", f"{N_REV_ALL:,} 条", "真实；仅限学术"],
    ["小说原文", "古登堡计划（Project Gutenberg）", "3 本", "真实；公版，可展示"],
    ["“标准答案”", "从书评里抽样，由本项目 AI 代理逐条判对错", "对齐 240 条 + 情绪 90 条", "真实书评；代理标注，未经人工复核"],
    ["模拟读者", "我们自己写程序生成", "3 本 × 250 段 × 4,000 人", [("合成", {"color": RED, "bold": True}), ("：只用来检验方法", {})]],
    ["数据合规调研", "公开网页、协议、法规、判例", "49 条来源（19 条未核实）", "真实资料"],
]
table(s, 0.6, 1.5, [2.3, 4.6, 2.6, 2.6], rows, size=15, row_h=0.85)
notes(s, "手上的东西分五类。"
         f"一是书评：Goodreads 上三本书全部英文版本下的 {N_REV_ALL:,} 条书评。"
         "二是原文：古登堡计划的公版电子书，可以放心引用。"
         "三是“标准答案”，也叫金标，就像考试的参考答案卷：我们抽了 240 条对齐、90 条情绪，让 AI 代理逐条判对错，用来给方法打分。注意它不是人工标的，会偏乐观。"
         "四是模拟读者：自己生成的假数据，因为知道正确答案，可以检验方法灵不灵。它不是发现。"
         "五是数据合规调研，49 条来源，其中 19 条没能找到原文核实。")

# =============== ⑤ 方法总览 ===============
s = new()
title(s, "我们用了哪些方法")
rows = [
    ["方法", "类型", "一句大白话"],
    ["文本切段（TextTiling + bge-m3 句向量）", [("深度学习", {"color": BLUE, "bold": True}), (" + 普通算法", {})], "话题一转弯，就在那里切一刀"],
    ["引文比对（5 词片段 + 模糊匹配）", [("普通算法", {"bold": True})], "像查重软件：抄错几个字也认得出"],
    ["情节检索 + 大模型确认（bge-m3 + Qwen3-1.7B）", [("深度学习", {"color": BLUE, "bold": True})], "先按意思找相近段落，再让 AI 判断是不是这段"],
    ["位置校正（观测/期望 + 经验贝叶斯）", [("统计", {"color": GREEN, "bold": True})], "扣掉“排在开头结尾”的天然优势"],
    ["模拟读者检验", [("仿真", {"color": RGBColor(0x0E, 0x8A, 0x9E), "bold": True})], "造一批知道答案的假数据，考考方法"],
    ["情绪：词典 + GoEmotions 模型", [("规则", {"color": RGBColor(0xB0, 0x76, 0x00), "bold": True}), (" + ", {}), ("深度学习", {"color": BLUE, "bold": True})], "查情绪词表；再请一个读过 5.8 万条评论的模型判断"],
    ["段落特征（词表）+ 泊松回归", [("规则", {"color": RGBColor(0xB0, 0x76, 0x00), "bold": True}), (" + ", {}), ("统计", {"color": GREEN, "bold": True})], "给段落打特点分，再算哪个特点让引用变多"],
]
table(s, 0.6, 1.45, [4.9, 2.4, 4.8], rows, size=15, row_h=0.66)
text(s, 0.6, 6.85, 12.1, 0.4, [("本项目没有用到强化学习和传统机器学习。", {"size": 14, "color": MUTED})])
notes(s, "一页看全所有方法。类型分得很清楚：深度学习是用大量数据训练出来的神经网络模型；统计是用概率和回归做比较；普通算法和规则是人写死的步骤，不需要训练；仿真是自己造数据做实验。"
         "值得注意：最靠谱的一步，引文比对，用的是最朴素的普通算法；反而需要深度学习的情节对齐，现在效果最差。"
         "后面按数据流动的顺序，一步一页讲。")

# =============== ⑥ 一步一步 ===============
def step(n, t, tag_list, items, note, pic_path=None, right=None, size=20):
    s = new()
    title(s, f"第 {n} 步：{t}", tag_list=tag_list)
    if pic_path:
        bullets(s, 0.6, 1.6, 5.6, 5.2, items, size=size)
        pic(s, pic_path, 6.5, 1.6, w=6.2)
    elif right:
        bullets(s, 0.6, 1.6, 6.4, 5.2, items, size=size)
        right(s)
    else:
        bullets(s, 0.6, 1.6, 12.1, 5.2, items, size=size)
    notes(s, note)
    return s


TAGS.update({"普通算法": (RGBColor(0x5B, 0x67, 0x70), WHITE), "仿真": (RGBColor(0x0E, 0x8A, 0x9E), WHITE)})

seg_v = SEG["validation"]


def seg_right(s):
    rows = [["书", "错误率", "瞎猜"]]
    for b in BOOKS:
        rows.append([f"《{ZH[b]}》", f"{seg_v[b]['pk']:.2f}", f"{seg_v[b]['random_baseline']['pk']:.2f}"])
    text(s, 7.3, 1.6, 5.4, 0.5, [("检验：能不能找回作者自己分的章？", {"size": 17, "bold": True})])
    table(s, 7.3, 2.25, [2.3, 2.1, 1.0], rows, size=16, row_h=0.6)
    text(s, 7.3, 4.85, 5.4, 1.2, [("错误率越低越好：都比瞎猜好，但远不完美。段落只当统计单位用。", {"size": 16, "color": INK2})])


step(1, "把书切成段落", ["深度学习", "普通算法"], [
    "整章太粗、一句太细，切成约 500 词一段",
    "句向量：给每段话一个“地图坐标”",
    "两边坐标突然离远 = 话题转弯，就切",
    f"三本书一共切出 {N_SC_ALL} 段",
], "热度总要算在某个单位上。整章太粗，一句太细，所以切成平均 500 词左右的段落。"
   "方法叫 TextTiling，文本瓦片法。在每个可能的切点两边各取约 300 词，用 bge-m3 模型变成句向量，比较两边的相似度；相似度突然下降，就说明话题变了。"
   "公式：相似度 = 两个向量的余弦值 cos(a,b) = a·b / (|a||b|)。"
   "检验方法：把整本书连起来、不告诉算法章节在哪，看它能不能找回作者自己的分章。错误率指标叫 Pk，越低越好，三本书都比瞎猜好。", right=seg_right)


def quote_right(s):
    stat(s, 7.3, 1.7, 2.6, f"{QA['k']}/{QA['n']}", "判为引用的，全对", size=44)
    stat(s, 10.1, 1.7, 2.6, f"{QBR['k']}/{QBR['n']}", "真正的引用，找回", size=44)
    box(s, 7.3, 4.0, 5.4, 2.4, [
        ("示意（虚构）", {"size": 13, "color": MUTED}),
        [("书评：", {"size": 16, "color": MUTED}), ("…boats against the ", {"size": 16, "name": SERIF}), ("currents", {"size": 16, "name": SERIF, "bold": True, "color": RED}), ("…", {"size": 16, "name": SERIF})],
        [("原文：", {"size": 16, "color": MUTED}), ("…boats against the ", {"size": 16, "name": SERIF}), ("current", {"size": 16, "name": SERIF, "bold": True, "color": GREEN}), ("…", {"size": 16, "name": SERIF})],
        ("抄错一个字，照样认出来", {"size": 16, "bold": True}),
    ], fill=PAPER, pad=0.25, space_after=8)


step(2, "找到书评引用的是哪一段", ["普通算法"], [
    "书评里常有引号括起来的原文",
    "读者会抄错、漏字，不能要求一字不差",
    "像查重软件：抄错几个字也能对上",
    "这一步不用 AI，又快又准",
], f"引文比对。读者引一句原文，我们要找到它在书里的哪一段。读者会抄错，所以用模糊匹配，就像论文查重软件。"
   "具体两条规则，满足一条就算：一，书评和原文共享在全书都很少见的连续 5 个词的片段，合起来覆盖至少 7 个词；二，引号里的片段和段落的相似度在 88 分以上（满分 100，用 rapidfuzz 的 partial_ratio）。同时对上 3 段以上的套话不算。"
   f"效果：随机抽 {QA['n']} 条判为引用的，全对；真正的引用 {QBR['n']} 条，找回 {QBR['k']} 条。提醒：标准答案是 AI 代理标的，会偏乐观。右边书评是虚构示意。", right=quote_right)


def plot_right(s):
    cd = CategoryChartData()
    cd.categories = ["什么都不判", "规则", "小模型 1.7B"]
    cd.add_series("综合得分 F1", (T_NONE["f1"], T_MOCK["f1"], T_LLM["f1"]))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(7.3), Inches(1.6), Inches(5.4), Inches(4.3), cd)
    ch = gf.chart
    ch.font.size = Pt(14)
    ch.font.name = FONT
    d = ch._chartSpace.find(".//" + qn("a:defRPr"))
    for t in ("a:ea", "a:cs"):
        d.append(d.makeelement(qn(t), {"typeface": FONT}))
    ch.has_legend = False
    ch.has_title = True
    ch.chart_title.text_frame.text = "找“描述情节”的书评：综合得分"
    tr = ch.chart_title.text_frame.paragraphs[0].runs[0]
    set_font(tr, size=15, bold=True)
    va = ch.value_axis
    va.maximum_scale = 1.0
    va.minimum_scale = 0
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RULE
    va.tick_labels.number_format = "0.0"
    va.tick_labels.number_format_is_linked = False
    ser = ch.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = BLUE
    ser.data_labels.show_value = True
    ser.data_labels.number_format = "0.00"
    ser.data_labels.number_format_is_linked = False
    ser.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    text(s, 7.3, 6.05, 5.4, 0.5, [("满分是 1.00。两种方法都只有约 0.11。", {"size": 15, "color": INK2})])


step(3, "没引原文的书评，指的是哪一段", ["深度学习"], [
    "“盖茨比死的时候我哭了”——没有原文可比",
    "先按意思找最像的 8 段，再请 AI 判断",
    "本机只能跑小模型，判断力不够",
    f"正确段落排第一的只有 {R1['k']}/{R1['n']}",
    "结论：这一步现在不能用，后面只用引文",
], "情节对齐。很多书评不引原文，只描述情节。没有共同的字，只能比意思。"
   "第一步，用 bge-m3 句向量从全书几千个窗口里挑出意思最像的 8 个；第二步，让确认器判断到底是不是在说这一段，或者根本没法定位。确认器试了两种：人写的规则，和 17 亿参数的 Qwen3 小模型。"
   f"右图是综合得分 F1，F1 是“找得准”和“找得全”的平均，满分 1。两种方法都只有 0.11 左右。连“什么都不判”的准确率都有 {pc(T_NONE['accuracy']['value'])}，比它们高。"
   f"原因：真正指向具体段落的句子本来就少（{BASE_RATE['k']}/{BASE_RATE['n']}）；检索就没找准；模型太小，至少要 70 亿参数的模型；同一批人物反复出场，段落彼此很像。"
   "F1 公式：F1 = 2 × 精确率 × 召回率 ÷ (精确率 + 召回率)。", right=plot_right)

step(4, "扣掉“位置”的影响", ["统计"], [
    "幸存者偏差：越往后读的人越少",
    "书评更怪：开头和结尾都被提得特别多",
    "所以先算“按位置本该被提几次”",
    "热度 = 实际次数 ÷ 本该次数",
    "次数太少的段落，往平均拉一拉",
], "这一步最关键。读者越往后越少，后面的段落天然吃亏，这叫幸存者偏差，就像马拉松后半程观众看到的人越来越少，不代表后半程不精彩。"
   f"书评的形状不一样，是 U 形：右图是三本书合计，每一万词被引用的次数，开头一档 {PROFILE[0]:.1f}、结尾一档 {PROFILE[-1]:.1f}，中间最低 {min(PROFILE):.1f}。"
   "做法：先用泊松回归按位置和长度估计每段“本该被提几次”，再用实际次数除以它。"
   "次数很少的段落，比值会乱跳，比如本该 0.5 次、实际 3 次就是 6 倍。所以再用经验贝叶斯往全书平均拉一拉，就像新开的店只有两条好评，不能直接说它比老店好。"
   "公式：热度 = (实际 + α) ÷ (期望 + α)，α 是从数据里估出来的收缩强度。", pic_path=FIGS / "position_profile.png")


def sim_right(s):
    stat(s, 7.3, 1.7, 2.6, f"{SIMM['mentions']['spearman']['mean']:.2f}", "直接数次数", size=44)
    stat(s, 10.1, 1.7, 2.6, f"{SIMM['oe_eb']['spearman']['mean']:.2f}", "校正以后", size=44)
    text(s, 7.3, 3.5, 5.4, 0.6, [("和“真实好看程度”的一致度（满分 1）", {"size": 15, "color": INK2})])
    box(s, 7.3, 4.3, 5.4, 1.9, [
        (f"前 10 名猜中：{pc(SIMM['mentions']['top10_recall']['mean'])} → {pc(SIMM['oe_eb']['top10_recall']['mean'])}", {"size": 17, "bold": True}),
        ("这是模拟数据，只证明方法有用，不是对真实读者的发现", {"size": 15, "color": RED}),
    ], fill=PAPER, pad=0.25, space_after=10)


p_ = SIM["params"]
step(5, "用模拟读者检验校正有没有用", ["仿真"], [
    "真实数据里，谁也不知道哪段“真的好看”",
    "自己造：定好每段多好看，再模拟读者",
    f"{p_['n_books']} 本书 × {p_['n_scenes']} 段 × {p_['n_readers']:,} 名读者，重复 {p_['reps']} 次",
    "看哪种算法最能猜回我们定好的答案",
], "怎么证明位置校正有用？真实数据没有标准答案，我们就造一批知道答案的数据。"
   f"每本书 {p_['n_scenes']} 段，每段先定一个“真实好看程度”，再模拟 {p_['n_readers']:,} 名读者从头读、中途有人放弃（读完率 {pc(p_['finish_rate'])}），读到好段落就划线。"
   f"结果：直接数次数，和真实好看程度的一致度（秩相关）只有 {SIMM['mentions']['spearman']['mean']:.2f}；校正后升到 {SIMM['oe_eb']['spearman']['mean']:.2f}。"
   f"前 10 名猜中的比例从 {pc(SIMM['mentions']['top10_recall']['mean'])} 升到 {pc(SIMM['oe_eb']['top10_recall']['mean'])}。再强调：这是模拟，只检验方法。", right=sim_right)


def emo_right(s):
    text(s, 7.3, 1.6, 5.4, 0.5, [("只贴原句、不写感受的比例", {"size": 17, "bold": True})])
    for i, b in enumerate(BOOKS):
        stat(s, 7.3 + i * 1.8, 2.3, 1.75, pc(BARE[b]), {"gatsby": "盖茨比", "pride": "傲慢与偏见", "janeeyre": "简·爱"}[b], size=36)
    box(s, 7.3, 4.3, 5.4, 1.4, [
        ("随便抽一些写了话的，只有 18% 表达了情绪", {"size": 16, "bold": True}),
        ("表达了的，一半是在夸文笔", {"size": 16}),
    ], fill=PAPER, pad=0.25, space_after=10)


step(6, "读出读者的情绪", ["规则", "深度学习"], [
    "分 10 类：感动、心碎、好笑、共鸣、夸文笔……",
    "先删掉书评里引用的原文，只读读者自己的话",
    "不删的话，原文的“爱”“死”会算到读者头上",
    "两种读法：情绪词表 + 现成的 AI 模型",
], "情绪分析最容易犯的错，是把原文的情绪算到读者头上。读者引用“他死了”，不代表读者悲伤。所以先删掉引号里的原文，只读读者自己的话。"
   "删之前，“治愈”在盖茨比的引用旁边占 12.5%，删之后只剩 2.0%（数字见 docs/EVALUATION.md 第 4 节）。"
   f"两种方法：一是情绪词表，属于规则；二是 GoEmotions 模型，它在 5.8 万条网友评论上训练过，属于深度学习。在 {EVE['n']} 条标准答案上，两者判断“有没有情绪”的精确率都在六成左右。"
   "右边是最重要的发现：读者引用时很少写感受。", right=emo_right)


def feat_right(s):
    box(s, 7.3, 1.6, 5.4, 3.3, [
        ("“像格言的句子”怎么判", {"size": 18, "bold": True}),
        ("8 到 45 个词", {"size": 16, "bullet": True}),
        ("说的是“人生、爱、人们”这种大词", {"size": 16, "bullet": True}),
        ("用现在时，不提具体人名", {"size": 16, "bullet": True}),
        ("例：“It is a truth universally acknowledged …”", {"size": 15, "name": SERIF, "italic": True}),
    ], fill=PAPER, pad=0.3, space_after=12)


step(7, "给每个段落打“特点分”", ["规则"], [
    "把“这段为什么好看”拆成能数的东西",
    "对话、爱情、离别、反转、冲突、幽默……",
    "每个特点一张词表，数一数出现多少",
    "规则透明便宜，但读不懂氛围和反讽",
], "要回答“为什么这段被引用”，先把段落拆成能数的特点。一共 11 个：对话占比、爱情、死亡离别、重逢、揭示反转、冲突、悬疑、幽默、感官描写、感叹号、像格言的句子。"
   "现在全部用词表和规则算。好处是每个数都说得清来历；坏处是测不准氛围、反讽。"
   "让大模型按编码手册打分的提示词已经写好，等 GPU 服务器恢复再跑。右边的例句是《傲慢与偏见》开篇第一句，公版原文。", right=feat_right)

# =============== ⑦ 结果 ===============
s = new()
title(s, "结果一：每本书最热的段落（扣掉位置以后）")
for i, b in enumerate(BOOKS):
    h = PEAK[b]
    x = 0.6 + i * 4.1
    rect(s, x, 1.6, 3.8, 4.9, PAPER, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.04)
    text(s, x + 0.3, 1.8, 3.2, 0.5, [(f"《{ZH[b]}》", {"size": 20, "bold": True})])
    stat(s, x + 0.3, 2.45, 3.2, f"×{h['heat_oe_eb']:.1f}", f"第 {h['chapter']} 章", size=40, sub=f"实际 {h['mentions']:g} 次，按位置本该 {h['expected']:.1f} 次")
    q = h["top_quote"]
    q = q if len(q) <= 120 else q[:117].rsplit(" ", 1)[0] + " …"
    text(s, x + 0.3, 4.3, 3.2, 2.1, [(f"“{q}”", {"size": 14, "name": SERIF, "italic": True})])
text(s, 0.6, 6.7, 12.1, 0.4, [("“×6.6”= 比按位置本该有的次数多 6.6 倍。引文都是公版原文。", {"size": 14, "color": MUTED})])
notes(s, "结果一：位置校正以后，每本书最热的段落。"
         f"盖茨比是第 {PEAK['gatsby']['chapter']} 章，叙述者说自己“身在其中又置身其外”那一句；傲慢与偏见还是开篇第一句，连扣掉位置优势都还是最热；"
         f"简·爱是第 {PEAK['janeeyre']['chapter']} 章“女人和男人一样有感受”那段，本该只被提 {PEAK['janeeyre']['expected']} 次，实际 {PEAK['janeeyre']['mentions']:g} 次。"
         "注意：本该次数很小时倍数会很大，所以要结合实际次数一起看。")

s = new()
title(s, "结果二：什么样的段落更常被引用")
pic(s, FIGS / "heat_forest.png", 0.6, 1.5, w=6.9)
stat(s, 7.9, 1.6, 4.8, f"×{APH['ratio']:.2f}", "“像格言的句子”多一档，被引用次数就乘以这个数", size=48)
bullets(s, 7.9, 3.6, 4.8, 3.2, [
    f"可信范围 {APH['ci_low']:.2f}–{APH['ci_high']:.2f}，没有跨过 1",
    "其他 10 个特点：都说不准",
    f"全书第一段：一般段落的 {FIRST:.1f} 倍",
], size=17)
notes(s, "结果二用统计里的泊松回归：比较的是“被引用次数”，同时控制位置、长度、章首章末和书与书的差别。就像比较两家店的客流，要先扣掉地段的影响。"
         f"左图每一行是一个特点，点是效应大小，横线是可信范围；横线全在 1 右边才算有把握。只有“像格言的句子”做到了：每多一个标准差，引用次数乘以 {APH['ratio']:.2f}，95% 可信范围 {APH['ci_low']:.2f} 到 {APH['ci_high']:.2f}，多重比较校正后 q = {APH['q_bh']:.3f}，刚好在 0.05 边上，所以说“有证据”而不是“确定”。"
         "公式：log(期望引用数) = 书 + 位置曲线 + log(词数) + 各特点 × 系数；IRR = e^系数。"
         f"控制项里，全书第一段被提的次数是一般段落的 {FIRST:.1f} 倍，说明位置偏差有多大。")

s = new()
title(s, "结果三：变成获客素材，做到了哪一步")
cols = [
    (GREEN, "做出来了", ["每本书 10 个高光段落", "每本书 12 张金句卡", "每个高光配短视频切入点"]),
    (AMBER, "怎么用", ["名句做流量入口", "中段高光做差异化", "卡片只用公版原文"]),
    (RED, "还没做", ["没上线、没测转化", "这批书评不能商用", "商用数据等用户决定"]),
]
for i, (col, h, items) in enumerate(cols):
    x = 0.6 + i * 4.1
    rect(s, x, 1.6, 3.8, 3.4, PAPER, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.04)
    rect(s, x + 0.3, 1.92, 0.34, 0.34, col, shape=MSO_SHAPE.OVAL)
    text(s, x + 0.8, 1.82, 2.8, 0.55, [(h, {"size": 22, "bold": True})], anchor=MSO_ANCHOR.MIDDLE)
    bullets(s, x + 0.3, 2.7, 3.25, 3.7, items, size=17, gap=14)
notes(s, "回到需求里的“用于获客”。做出来的是素材：每本书 10 个高光段落、12 张金句卡，每个高光配了短视频切入点的建议。"
         "用法：名句天然热，适合做流量入口；扣掉位置后冒出来的中段高光，别人不常讲，适合做差异化内容。"
         "还没做的：没有真正投放、没测效果；更关键的是这批 Goodreads 数据只能做研究。商用要换成用户自己捐赠的导出、和腾讯合作，或者自建读书社群的数据，这需要用户拍板。")

# =============== ⑧ 做出来的东西 ===============
s = new()
title(s, "做出来的东西长什么样")
pic(s, SHOTS / "02_corrected_peak_gatsby.png", 0.6, 1.45, w=7.6)
box(s, 8.6, 1.45, 4.1, 2.0, [
    ("双击", {"size": 18, "color": INK2}),
    ("启动演示.bat", {"size": 26, "bold": True, "hl": True}),
    ("离线打开，自动讲解 16 步", {"size": 16, "color": INK2}),
], fill=PAPER, pad=0.3, space_after=6)
bullets(s, 8.6, 3.8, 4.1, 3.0, [
    "热度时间线从左往右长出来",
    "书评里的引文“飞”回原文并划线",
    "三本书轮流切换，金句卡轮播",
    "空格暂停，← → 翻步，F 全屏",
], size=16, gap=10)
notes(s, "这是配套的演示页。项目根目录双击“启动演示.bat”，浏览器离线打开，自己就会动起来。"
         "上面是热度时间线，每根柱子是一段，颜色是读者情绪；中间左边是书评里的引用，飞到中间的原文位置并划线；右边是读者反应的汇总。"
         "页面上不显示任何书评原文和用户名，只有统计数字、公版原文、高频词和 AI 代理写的中文摘要。演示顺序见 DEMO_GUIDE.md。")

# =============== ⑨ 局限与下一步 ===============
s = new(dark=True)
text(s, 0.6, 0.5, 12.1, 0.8, [("局限与下一步", {"size": 32, "bold": True, "color": WHITE})])
cols = [
    ("局限", ["“标准答案”是 AI 代理标的，会偏乐观", "没引原文的书评还对不上", "只有三本英文书", "英文书评 ≠ 中文划线"]),
    ("下一步", ["请两位同学独立复标 330 条", "GPU 服务器恢复后，用 70 亿参数以上的多个模型投票", "用户决定：商用数据从哪来", "决定要不要做中文书"]),
]
for i, (h, items) in enumerate(cols):
    x = 0.6 + i * 6.15
    rect(s, x, 1.6, 5.9, 4.6, RGBColor(0x26, 0x30, 0x3C), shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.04)
    text(s, x + 0.35, 1.85, 5.2, 0.6, [(h, {"size": 24, "bold": True, "color": WHITE})])
    text(s, x + 0.35, 2.7, 5.2, 3.4, [[(t, {"bullet": True, "size": 19, "color": LIGHT})] for t in items], space_after=14)
text(s, 0.6, 6.5, 12.1, 0.6, [("完整数字和出处：docs/EVALUATION.md", {"size": 14, "color": DIM})])
notes(s, "局限：标准答案是 AI 代理标的，设计方法的和打分的是同一方，会偏乐观；没引原文的书评还对不上，所以结论偏向“名句和文笔”；只有三本英文书；英文书评的规律不一定适用于中文划线。"
         "下一步：请两位同学独立复标 330 条标准答案并算一致性；GPU 服务器恢复后用 70 亿参数以上的多个模型做情节对齐和打分；商用数据来源和要不要做中文书，需要用户决定。"
         "课堂讨论：如果你拿到自己导出的微信读书划线，划线的位置偏差会是什么形状？")

prs.core_properties.title = "读者评论 → 桥段热度与情绪地图 · 讲解"
prs.core_properties.author = "Shuyao Gao"
prs.save(OUT)
print(f"wrote {OUT} ({len(prs.slides)} slides)")
