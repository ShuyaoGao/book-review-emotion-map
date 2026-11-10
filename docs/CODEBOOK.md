# 编码手册（v1，2026-10-08）

本手册定义两套标签：读者情绪（标在“评论语境”上）和桥段特征（标在“场景”上）。
规则基线（`src/emotion.py`、`src/features.py`）和 LLM 提示词（`EMO_PROMPT`、`FEATURE_PROMPT`）都按本手册实现。
改动任何定义都要升版本号（`emotion_v1` / `features_v1`），并重跑全部打标器，否则前后结果不可比。

## 1. 读者情绪（多标签，评论语境层）

**标注单位**：一条被对齐到某个场景的评论句，连同它在同一条书评里的前一句和后一句（最多约 1,200 字符）。
**判定原则**：只标读者自己明确表达的情绪，不标书中人物的情绪。比如“Darcy 很生气”不算 anger，“Darcy 气得我想摔书”算。
可以同时标多个；没有明显情绪时全部为 0。

| 代码 | 中文 | 定义 | 典型线索（英 / 中） | 反例（不算） |
|---|---|---|---|---|
| `moved` | 感动 | 被打动、流泪、动容 | cried, tears, moving, touching / 泪目、破防、动容 | “这一段很重要”（只是判断） |
| `heartbreak` | 意难平 / 心碎 | 悲伤、惋惜、心疼角色、“要是……就好了” | heartbreaking, so sad, poor X, if only / 意难平、心疼、唏嘘 | 角色悲伤但读者没表态 |
| `anger` | 愤怒 | 对角色或情节生气、厌恶、不耐烦 | hate, infuriating, despise / 气死、渣、恶心 | 只是“不喜欢这本书”（整体评价） |
| `amusement` | 好笑 | 觉得好笑、机智、讽刺有趣 | funny, hilarious, witty, lol / 笑死、哈哈 | “ironic”只作术语用 |
| `shock` | 震撼 / 意外 | 惊讶、反转、冲击力强 | twist, didn't see it coming, wow, powerful / 震撼、反转、没想到 | 平铺直叙的情节复述 |
| `comfort` | 治愈 / 释然 | 温暖、欣慰、终于圆满、松一口气 | heartwarming, relief, happy ending / 治愈、温暖、欣慰 | — |
| `swoon` | 心动 | 对爱情桥段或角色心动、嗑 CP | swoon, romantic, chemistry, proposal / 心动、表白、磕到 | 泛泛的“love this book” |
| `suspense` | 紧张 / 恐惧 | 害怕、紧张、毛骨悚然 | creepy, eerie, tense, dread / 紧张、吓人、揪心 | — |
| `resonance` | 共鸣 / 认同 | 觉得说得对、贴近自己、可用于人生 | so true, relatable, wise, timeless / 共鸣、扎心、太真实 | 只是复述金句不表态（按 0） |
| `aesthetic` | 文笔赞叹 | 赞美写法本身（语言、意象、结构） | beautiful prose, lyrical, imagery / 文笔、优美 | “beautiful”指情节或人物时按语境判断 |

**GoEmotions 映射**（`SamLowe/roberta-base-go_emotions`，阈值 0.5，模型卡给出的默认值）：

| 本手册 | GoEmotions 类别 |
|---|---|
| amusement | amusement |
| anger | anger, annoyance, disgust, disapproval |
| heartbreak | sadness, grief, remorse, disappointment |
| shock | surprise, excitement |
| suspense | fear, nervousness |
| comfort | joy, relief, gratitude, optimism, caring |
| swoon | desire |
| resonance | approval, realization |
| aesthetic | admiration |
| moved | **无对应类别**，只有词典和 LLM 能标 |

未映射：neutral, curiosity, confusion, pride, embarrassment, love。`love` 在 GoEmotions 里多是“I love this book”这类泛泛好评，不映射到 swoon。
映射是多对一的近似，`aesthetic ← admiration` 尤其粗糙（admiration 也覆盖“佩服角色”）。

## 2. 桥段特征（场景层）

**标注单位**：一个场景（`src/segment.py` 切出的桥段，中位数约 500 词）。LLM 标注时最多给前 900 词。

| 代码 | 取值 | 定义 | 规则基线怎么近似 |
|---|---|---|---|
| `scene_type` | dialogue / action / description / introspection / summary / letter | 主导叙述方式 | 对话占比 ≥ 0.5 → dialogue；否则感官词密度 ≥ P75 → description；否则 summary（规则分不出 action / introspection / letter） |
| `conflict` | 0 / 1 / 2 | 0 无；1 有张力或分歧；2 公开冲突、争吵或暴力 | 冲突词密度：> 0 且 ≥ P50 → 1，≥ P85 → 2 |
| `reversal` | 0 / 1 | 揭示、发现、坦白、反转，改变了人物或读者原来的认知 | 揭示类词密度 ≥ P80 |
| `death_parting` | 0 / 1 | 死亡、致命事故，或重要的分离、告别（发生或得知） | 死亡/告别词密度 ≥ P80 |
| `reunion` | 0 / 1 | 分离的人重逢，或身份被认出 | 重逢词密度 ≥ P80 |
| `romance` | 0 / 1 | 表白、求婚、亲吻或明确的浪漫时刻 | 爱情词密度 ≥ P80 |
| `aphorism` | 0 / 1 | 含可单独引用的格言式一般性陈述 | 句子 8–45 词，含泛指名词（life, love, man, people…）和现在时，不含人名、人称代词、过去时、问号 |
| `sensory` | 0 / 1 / 2 | 感官描写（颜色、声音、气味、触感）的浓度 | 感官词密度 P50 / P85 |
| `humor` | 0 / 1 | 明显的喜剧或机智 | 笑/玩笑类词密度 ≥ P80 |
| `suspense` | 0 / 1 / 2 | 不安、恐惧、紧张 | 恐惧类词密度 P50 / P85 |

另有连续量，不需要标注：`dialogue_ratio`（引号内字符占比）、`exclaim_per1k`、`question_per1k`、各词表的每千词密度、`aphorism_n`。

**混杂量**（建模时作控制变量，不当特征解读）：场景词数（越长越容易被提及）、在书中的位置（幸存者偏差、首尾效应）、是否章首/章末、是否全书第一个/最后一个场景。

## 3. 对齐判定（金标用）

| 类型 | 判为“正确” |
|---|---|
| 引文（A/B 类） | 评论里的引文确实出自该段落（允许标点、大小写和个别词的差异；只取原文中某一句的局部也算） |
| 情节（C 类） | 评论句指向的具体情节发生在该场景；如果一个情节跨相邻两个场景，两者都算对（宽松口径另报“同章”命中） |
| 情节 NONE | 评论句只是总体评价、泛泛的人物评价、主题讨论，或指向的情节无法唯一定位 |
