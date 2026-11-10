# 第三方组件、数据与许可证

本仓库的代码（Python、HTML/CSS/JavaScript、构建脚本）由本项目编写，**没有拷贝或内嵌第三方源代码**。
演示页 `demo/demo.html` 不加载任何外部脚本、字体或图片，只用系统字体，离线可用。

## 书籍原文：Project Gutenberg（公版）

| 书 | Gutenberg 编号 | 作者 | 首次出版 |
|---|---|---|---|
| The Great Gatsby（《了不起的盖茨比》） | #64317 | F. Scott Fitzgerald | 1925 |
| Pride and Prejudice（《傲慢与偏见》） | #1342 | Jane Austen | 1813 |
| Jane Eyre（《简·爱》） | #1260 | Charlotte Brontë | 1847 |

- 三本书在美国均属公版（Project Gutenberg 按美国版权法标注）。其他国家和地区的版权状态请按当地法律自行确认。
- **仓库里不保存原文全文**。`src/fetch_gutenberg.py` 从 Project Gutenberg 下载并去掉页眉页脚；页面和结果文件里只出现被书评引用的单句和场景开头的一两句。
- `data/books/_manifest.json` 只记录下载的书目编号、文件大小和校验值，不含正文。

## 书评数据：UCSD Book Graph（Goodreads）

- 来源：Mengting Wan, Julian McAuley 等整理的 UCSD Book Graph（Goodreads 书评数据集）。
- 许可条件（数据集页面原文）：“academic use only … do not redistribute … or use for commercial purposes”。
- 因此本仓库**不包含**：书评原文、用户名或用户 ID、逐条书评级别的记录（review_id、评分、句号）、抽取出的中间文件。
  这些只在作者本机，可按 README 的“复现”一节自行下载数据后重新生成。
- 本仓库**只包含**由该数据计算出的聚合量：每个场景被引用的次数、期望次数、校正热度、情绪类别计数、
  跨 ≥2 条书评聚合的高频词，以及代理（Claude）读过代表性书评后撰写的中文摘要（不是书评原文，也不是译文）。
- 金标（`data/gold/labels/*.json`）只含条目编号和标注结果，标注者是代理，不是人工。

相关引用：

- Mengting Wan, Julian McAuley. "Item Recommendation on Monotonic Behavior Chains." RecSys 2018.
- Mengting Wan, Rishabh Misra, Ndapa Nakashole, Julian McAuley. "Fine-Grained Spoiler Detection from Large-Scale Review Corpora." ACL 2019.

## 模型（不随仓库分发，运行时由使用者从 Hugging Face 下载）

| 模型 | 用途 | 许可证 |
|---|---|---|
| BAAI/bge-m3 | 文本嵌入（场景切分、情节检索） | MIT |
| SamLowe/roberta-base-go_emotions | 读者情绪分类（GoEmotions 28 类，映射见 `docs/CODEBOOK.md`） | MIT |
| Qwen/Qwen3-1.7B | 本机 LLM 冒烟测试 | Apache-2.0 |

GoEmotions 数据集（Demszky et al., ACL 2020）本身为 Apache-2.0，本仓库未包含。

## Python 依赖（requirements.txt，不随仓库分发）

| 包 | 许可证 |
|---|---|
| numpy、pandas、scipy、scikit-learn、statsmodels、torch | BSD-3-Clause |
| matplotlib | Matplotlib License（PSF 风格） |
| rapidfuzz、pytest | MIT |
| requests、sentence-transformers、transformers、huggingface_hub | Apache-2.0 |
| python-pptx（只用于生成 `讲解.pptx`） | MIT |

## 网页字体

- `demo/demo.html`：只用系统字体，不加载网络字体。
- `showcase/index.html`：在线时从 Google Fonts 加载 Noto Serif SC、Noto Sans SC、IBM Plex Mono（均为 SIL Open Font License 1.1）；离线时退回系统字体。
