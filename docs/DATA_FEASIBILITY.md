# 数据可得性调研：以读者划线/评论为标注定位“打动人的桥段”

- 项目：p8-book-emotion
- 调研日期：2026-10-08
- 范围：微信读书数据的可得性与合规边界；公开替代数据；推荐的数据组合
- 方法：所有事实均通过网页检索或打开原始页面核对，来源 URL 附在每条结论后。无法打开原文、只能从二手报道或检索摘要得到的，标 `[未核实]` 或在核实状态表中注明。标注“本项目代理已核实 2026-10-08”的条目由本项目代理核对，本文直接引用。
- 未做的事：未登录任何平台，未调用微信读书、豆瓣的私有接口，未下载大文件。

---

## 0. 结论摘要

| # | 结论 |
|---|---|
| 1 | 微信读书在 2026 年 5 月推出了官方 Skill（Agent API），用户可凭本人 API Key 读取自己的划线、想法，也能读取书籍的“热门划线”和公开书评。这是目前唯一由官方提供的程序化通道，但 Key 与个人身份绑定，定位是“个人阅读助手”。本次未找到允许批量采集或商用的条款，用它做规模化获客数据源，需要先拿到腾讯书面许可。 |
| 2 | 《微信读书软件许可及服务协议》6.1.2.4、6.1.2.6 条禁止用非腾讯授权的第三方工具获取客户端与服务器的交互数据。用 cookie 调私有接口的第三方导出工具与这两条直接冲突，本项目不采用。 |
| 3 | 2025 年修订的《反不正当竞争法》（2025-10-15 施行）在第十三条第三款新增了数据条款，禁止以“避开或者破坏技术管理措施等方式”获取、使用其他经营者合法持有的数据。抓取平台聚合数据（例如“N 人划线”）的法律风险比 2019 年版时期更明确。 |
| 4 | 公开数据里，结构上最接近“段落级读者反应”的是 Qidian-Webnovel Corpus（起点段评，约 279 万条中文评论，带段落定位）。完整版受限访问，仅限高校/非营利机构做非营利研究，并须签数据转让协议。Goodreads 数据集同样只限学术用途。 |
| 5 | 建议分两条线。研究验证可用 Goodreads、起点语料、GoEmotions 和公版书文本；商用获客只能用公版文本、许可证明确允许商用的模型或数据，以及自有、经同意或经授权的读者数据。方法可以从研究线迁移到商用线，数据不能。 |

---

## 1. 微信读书

### 1.1 官方 API 与数据开放

| 项目 | 现状 | 来源 |
|---|---|---|
| 面向第三方机构的数据开放平台 | 本次检索没有找到。这是检索结果为空，不代表确定不存在。`[未核实]` | 检索 weread.qq.com、新闻，未命中 |
| 官方 Skill / Agent API | 2026 年 5 月发布。能力包括书籍搜索、书架、阅读统计、笔记划线，以及“想法、书评，以及其他读者的热门划线”。只读，不能写回。 | https://www.pingwest.com/a/313814 |
| 获取方式 | 登录后在 `weread.qq.com/r/weread-skills` 获取 API Key。页面写明“Your data is visible only to you”，并链接用户协议与腾讯隐私政策。 | https://weread.qq.com/r/weread-skills |
| 代码仓库 | `github.com/tencent/wechatreading`，Apache-2.0（覆盖 Skill 代码，不覆盖数据）。README 写明可访问本人笔记划线、其他读者热门划线、公开书评与评分；“API Key is bound to user identity”。未写调用频率或商用限制。 | https://github.com/tencent/wechatreading |
| 第三方转向官方 Key | Obsidian 微信读书插件 V2 改用官方 API Key（格式 `wrk-xxxxxxxx`），V1 的 cookie 方式保留为回退。weread2notion 的 README 写明“新版不再需要复制微信读书 Cookie”。 | https://raw.githubusercontent.com/zhaohongxuan/obsidian-weread-plugin/main/docs/weread-v2-guide.md ；https://github.com/malinkang/weread2notion |

判断：官方 Skill 让“用户本人取回自己的数据”有了合规通道，这对后面的“用户捐赠”路线是利好。但它是个人助手，不是数据开放平台。拿一个或几个 Key 去遍历大量书籍的热门划线和书评，是否在授权范围内，现有公开文本没有说明 `[未核实]`。在拿到腾讯书面确认之前，按“不允许规模化采集”处理。

### 1.2 用户自行导出笔记

| 方式 | 说明 | 时间 | 来源 |
|---|---|---|---|
| App 内导出 | 笔记页右上角“导出”按钮，勾选条目后“复制到剪贴板” | 2018-09 的文章所述版本 | https://sspai.com/post/47216 |
| 路径 | “微信读书 - 我 - 笔记”，复制后粘贴到其他工具 | 2019-09 | https://sspai.com/post/56150 |
| 直接导出到印象笔记 | 早年报道说官方只能复制到剪贴板，再手动粘贴到印象笔记；没有找到官方直连印象笔记的证据 | — | 同上；当前版本 `[未核实]` |
| 官方 Skill 导出 | README 把“notes export”列为能力之一，可配合 Markdown 类工具使用 | 2026 | https://github.com/tencent/wechatreading |

当前（2026-10）App 内导出入口和格式是否有变化，本次没有核实 `[未核实]`。

### 1.3 热门划线、想法、书评的形态

| 形态 | 描述 | 来源 / 状态 |
|---|---|---|
| 热门划线 | 社区里划线次数最多的句段，按章节分组，标“🔥 N 人划线”。插件同步时每本书最多取 20 条。 | 插件文档（第三方对官方接口的描述），已核实 |
| 想法 | 可以在划线上写想法，也可以发独立想法；协议 2.1 条提到可浏览好友的“读书想法” | https://www.woshipm.com/evaluating/5237152.html ；https://weread.qq.com/web/copyright |
| 书评与评分 | 读完可以打分、写书评；Skill 可读取“公开书评与评分” | https://www.woshipm.com/evaluating/5237152.html ；https://github.com/tencent/wechatreading |
| 推荐 / 一般 / 不行 三档与“推荐值” | 没有找到可核对的公开文本 | `[未核实]` |

对本项目的意义：“N 人划线”本身就是一个段落级的聚合热度标签，正好是本项目想要的标注。但有两点要分开看。第一，划线的文字是书的原文，著作权属于作者或出版方，不属于微信读书，也不属于划线用户。第二，“N”是平台基于用户行为算出来的数据，按淘宝诉美景、腾讯诉聚客通等案的思路，平台对这类聚合数据可能享有竞争性权益（见 1.5）。

### 1.4 第三方导出工具

GitHub 上有不少用用户自己的 cookie 调网页私有接口的工具。上面提到的两个主流项目已经改用官方 API Key，旧版 cookie 方式仍作为回退存在。本项目不采用 cookie 方式，原因有三：
1. 与协议 6.1.2.4（禁止用“非经腾讯授权的第三方工具/服务”获取交互数据）、6.1.2.6（禁止通过非腾讯授权的第三方软件登录或使用）直接冲突；
2. 即使只取本人数据，也属于灰色地带；
3. 一旦扩展到他人数据或批量书目，就可能落入《反不正当竞争法》第十三条第三款甚至刑法第二百八十五条第二款的讨论范围。

### 1.5 服务条款与法律风险

**服务条款**（《微信读书软件许可及服务协议》，https://weread.qq.com/web/copyright ，页面没有标注生效日期）

| 条款 | 要点（摘录） |
|---|---|
| 6.1.2.3 | 不得对腾讯拥有知识产权的内容进行使用、复制、转载、汇编、建立镜像站点等 |
| 6.1.2.4 | 不得对客户端与服务器端的交互数据进行获取、复制……“形式包括但不限于使用插件、外挂或非经腾讯授权的第三方工具/服务接入” |
| 6.1.2.6 | 不得通过非腾讯开发、授权的第三方软件、插件、外挂、系统登录或使用本软件及服务 |
| 8.1 | 本软件及相关信息内容的知识产权归腾讯 |
| 用户内容 | 本次抓取的协议文本里，没有找到用户发布的想法、书评、划线的著作权归属或对腾讯授权的专门条款 `[未核实：可能见于其他协议]` |

协议用的是“除非法律允许或经腾讯书面许可”的句式，所以平台合作这条路需要拿到书面许可。

**法律框架**

| 规范 | 条文要点 | 与本项目的关系 | 来源 |
|---|---|---|---|
| 《反不正当竞争法》（2019 修正）第十二条 | 互联网专条：不得利用技术手段妨碍、破坏其他经营者网络产品或服务的正常运行（四项） | 2025-10-15 前判例的主要依据，另一依据是第二条 | https://fgk.chinatax.gov.cn/zcfgk/c100009/c5211782/content.html （检索核实） |
| 《反不正当竞争法》（2025 修订）第二条 | 诚信原则与商业道德；不正当竞争行为的定义 | 一般条款，法院常用来认定数据抓取 | https://www.news.cn/legal/20250627/4b6ec78bc9be4ea9a2968a9d34abd724/c.html |
| 同上 第十三条 | 原第十二条的互联网专条移到这里，并加上“数据和算法、技术、平台规则”。第三款：“经营者不得以欺诈、胁迫、避开或者破坏技术管理措施等方式，获取、使用其他经营者合法持有的数据，损害其合法权益。” | 直接覆盖“绕过反爬抓取平台聚合数据” | 同上；2025-06-27 通过，2025-10-15 施行 |
| 《个人信息保护法》第四条 | 个人信息不包括匿名化处理后的信息 | 捐赠数据要做去标识化，达到匿名化才可脱离 PIPL 适用 | https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm |
| 同上 第十三条第一款第（六）项 | 可在合理范围内处理个人自行公开或已合法公开的个人信息 | 公开书评、想法带昵称，属于个人信息 | 同上 |
| 同上 第二十七条 | 可在合理范围内处理已公开个人信息，个人明确拒绝的除外；对个人权益有重大影响的，应取得同意 | 用于商业获客、画像，风险高于学术统计 | 同上 |
| 同上 第七十三条 | “去标识化”和“匿名化”的定义 | 捐赠方案的技术标准 | 同上 |
| 《数据安全法》第三十二条第一款 | 收集数据应当采取合法、正当的方式，不得窃取或者以其他非法方式获取 | 一般性义务 | https://www.cac.gov.cn/2021-06/11/c_1624994566919140.htm |
| 刑法第二百八十五条第二款 | 违反国家规定，侵入或采用其他技术手段获取计算机信息系统数据，情节严重的，处三年以下有期徒刑或拘役等 | 绕过技术措施、规模化抓取的极端情形 | https://www.court.gov.cn/shenpan/xiangqing/283891.html （检索核实） |
| 《著作权法》（2020 修正）第二十四条第一款第（一）（六）项 | 合理使用：个人学习、研究；为科学研究少量复制已发表作品，但不得出版发行 | 研究阶段使用书籍原文的依据；商用短视频大段引用原文不在这个范围内 | https://www.elawcn.com/rule/2020/1115/721.html |

**判例（只列已核实的）**

| 案件 | 法院 / 案号 | 要点 | 状态 | 来源 |
|---|---|---|---|---|
| 新浪微博诉脉脉 | 北京知识产权法院，（2016）京73民终588号，2016-12-30 二审维持原判，判赔 200 万元 | 第三方通过开放平台获取用户信息，应坚持“用户授权”+“平台授权”+“用户授权”（三重授权） | 已核实（案号见界面新闻引述；法院、日期、金额、三重授权见钛媒体） | https://www.jiemian.com/article/1541062.html ；https://www.tmtpost.com/2557736.html |
| 大众点评诉百度 | 一审上海市浦东新区人民法院，2016-05-26；二审上海知识产权法院驳回上诉、维持原判 | 百度地图大量全文使用点评网的点评（餐饮 1055 家商户，86,286 条），法院认为超出必要限度，构成不正当竞争；判赔 300 万元及合理费用 23 万元 | 事实已核实；二审案号（2016）沪73民终242号 `[未核实]` | https://www.elawcn.com/news/2016/0604/417.html ；https://www.yicai.com/news/5340378.html |
| 淘宝诉美景 | 杭州铁路运输法院，（2017）浙8601民初4034号 | 数据产品开发者享有“竞争性财产权益”；判赔 200 万元 | 已核实 | https://www.elawcn.com/ecommerce/2021/0805/895.html |
| 腾讯诉聚客通群控软件 | 2020-06-02 判决，判赔 260 万元。杭州日报网报道为“杭州互联网法院”，中伦文章写作 Hangzhou Railway Transport Court | 平台对数据资源整体享有竞争性权益；对单一用户数据只享有有限使用权，依附于用户信息权益和与用户的约定 | 事实已核实；案号（2019）浙8601民初1987号只见于检索结果标题，原页无法打开 `[未核实]` | https://hznews.hangzhou.com.cn/shehui/content/2020-06/02/content_7747527.htm ；https://www.zhonglun.com/research/articles/9092.html |
| 抖音诉刷宝 | 北京市海淀区人民法院一审 | 刷宝获取抖音短视频 5 万余条及评论内容并展示，构成不正当竞争；判赔 500 万元（诉请 4000 万元） | 事实已核实；案号 `[未核实]` | https://www.elawcn.com/copyright/2021/0130/744.html |

**对本项目的含义**：用户评论和用户行为产生的聚合指标（点评、评论、划线热度）在国内司法实践中多次被认定为平台的竞争性权益。把这类数据搬到自己的产品里，用来和平台争夺同一批用户，是判例里最典型的“实质性替代”。书单号、拆书号正好与微信读书争夺阅读注意力，风险不能按“只是引用几个数字”来低估。

### 1.6 合规可行方式

| 方式 | 做法 | 可行性 | 主要风险 | 成本 |
|---|---|---|---|---|
| A. 用户本人导出并自愿捐赠 | 招募读者，用 App 的“复制到剪贴板”或官方 Skill 导出本人划线和想法后提交；签知情同意书（说明用途含商业内容生产）；去掉昵称、ID、时间戳等，按 PIPL 第七十三条做去标识化 | 中。数据合法性最好，但规模受招募能力限制，几百到几千人量级比较现实 | 捐赠者导出的“热门划线”属于平台聚合数据，不在本人授权范围内，应只收本人数据；书籍原文著作权另行处理 | 中：招募激励、同意书、清洗 |
| B. 小规模人工记录公开聚合数字 | 研究者在正常阅读中人工记下少量书目某段的“N 人划线” | 低到中。几十本书做探索性验证可以；作为长期数据源不可行 | 单次少量记录风险较低，但持续、系统地复制后用于竞争性产品，有可能被认定为第二条、第十三条下的不正当竞争；不能用自动化工具 | 低，但人工耗时 |
| C. 官方 Skill，限于本人 Key 和本人书架 | 研究者用自己的 Key 读取已读书籍的热门划线，做方法验证 | 中。技术门槛低 | 授权边界不清 `[未核实]`；结果只宜留在内部研究，不宜对外发布或商用 | 低 |
| D. 与平台合作 | 向微信读书或出版方申请研究或商业数据合作，拿到书面许可 | 低到中。取决于对方意愿；以出版方为切入口（以带货回流为交换）可能更现实 | 谈判周期长，可能附带排他或署名条件 | 高：商务时间 |
| E. 抓取或 cookie 调接口 | — | 不采用 | 协议 6.1.2.4/6.1.2.6；反不正当竞争法第十三条第三款；极端情况下刑法第二百八十五条 | — |

---

## 2. 公开替代数据

### 2.1 读者评论与反应类

| 数据集 | 规模与粒度 | 许可 / 使用条件 | 能否商用 | 来源 |
|---|---|---|---|---|
| UCSD Book Graph / Goodreads（本项目代理已核实 2026-10-08） | 完整去重书评约 15.7M 条；spoiler 子集约 1,378,033 条书评、25,475 本书、18,892 个用户、17,672,655 个句子，3.22% 为剧透句，句级剧透标签由评论作者自标 | “We collected these datasets for academic use only. Please do not redistribute them or use for commercial purposes.” | 否 | https://mcauleylab.ucsd.edu/public_datasets/gdrive/goodreads/UCSD%20Book%20Graph.html ；https://aclanthology.org/P19-1248 |
| GitHub MengtingWan/goodreads | 只有代码样例（下载、读取、统计 notebook），数据在官方页面下载；2017 年末采集 | 仓库代码 Apache-2.0；README 重申数据 academic use only | 代码可以，数据不可以 | https://github.com/MengtingWan/goodreads |
| Amazon Reviews 2018 | 233.1M 条评论（1996-05 至 2018-10）；Books 类 51,311,621 条、2,935,525 个商品 | 页面没有写明许可证；完整数据需填表申请 `[未核实]` | 不明，按不可商用处理 | https://nijianmo.github.io/amazon/index.html |
| Amazon Reviews 2023 | 571.54M 条评论，54.51M 用户，48.19M 商品（至 2023-09）；Books 类 10.3M 用户、4.4M 商品、29.5M 条评分 | 官网和 HF 数据卡都没有写明许可证（HF API 的 license 字段为空）`[未核实]` | 不明，按不可商用处理 | https://amazon-reviews-2023.github.io/ ；https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023 |
| Qidian-Webnovel Corpus 110 | 110 部网文；起点中文评论 2,791,837 条、Webnovel 英文评论 237,958 条（快照 2024-09-01）；评论按书、章、段三级组织，带段落定位 | 论文（JOHD 2025）CC BY 4.0。数据在 DataverseNL 受限访问：只允许高校或非营利研究机构做“not-for-profit scientific research”，须签 Data Transfer Agreement，不得向第三方披露或为自身利益使用 | 否 | https://reference-global.com/article/10.5334/johd.368 ；https://doi.org/10.34894/GQXX3K （元数据经 DataverseNL API 读取） |
| 起点 / 晋江官方公开的“本章说 / 段评”数据集 | 除上一条学术语料外，本次没有找到平台官方或其他公开的段评数据集 | — | — | 检索结果为空 `[未核实]` |
| 豆瓣：RecoHut-Datasets/douban | 音乐、电影、图书推荐数据；README 只有一句描述 | 没有 LICENSE 文件（GitHub API 返回 Not Found），默认保留所有权利；原始来源未说明 | 否 | https://github.com/RecoHut-Datasets/douban |
| 豆瓣：Jiashuo-Sun/DoubanBookList | 书名、作者、ISBN、均分、评论数（书级元数据，没有评论正文），爬虫采集 | 没有 LICENSE 文件 | 否 | https://github.com/Jiashuo-Sun/DoubanBookList |
| 豆瓣与 Goodreads 经典书平行数据（Zenodo） | Goodreads 144 本、豆瓣 141 本经典书的书级指标（评论数、均分、URL），CSV 137.5 kB | CC BY 4.0 | 书级元数据可以商用（需署名），但不含评论文本，对本项目价值有限 | https://zenodo.org/records/15252768 |
| Kaggle“Douban Movie Short Comments” | 电影短评，不是图书 | 页面没有渲染出来，许可证 `[未核实]` | 不明 | https://www.kaggle.com/datasets/utmhikari/doubanmovieshortcomments |

另外，Apify 上有多个第三方豆瓣抓取服务。它们属于“代为抓取”，合规风险由使用者承担，本项目不采用。

### 2.2 名句 / 摘录类（Goodreads quotes）

| 数据集 | 规模 | 许可 | 备注 | 来源 |
|---|---|---|---|---|
| Abirate/english_quotes | 2,508 条（quote、author、tags），抓取自 Goodreads Quotes | 数据卡声明 CC BY 4.0 | 上传者的许可声明不能覆盖 Goodreads 的条款和原作者的著作权；没有点赞数 | https://huggingface.co/datasets/Abirate/english_quotes |
| jstet/quotes-500k | 499,709 条（quote、author、category），来自 Goel et al. 2018 | 未见许可证 | 默认保留权利 | https://huggingface.co/datasets/jstet/quotes-500k |
| EhsanShahbazi/goodreads-quotes | 10 万到 100 万条，744 MB，访问需同意条款 | 页面显示 MIT，HF API 标签为 license:other，两处不一致 | 以不可商用处理 | https://huggingface.co/datasets/EhsanShahbazi/goodreads-quotes |

名句数据集可以近似当作“书中哪些句子被读者认可”的弱标签，但它是句级、脱离上下文的，大量条目不是出自书籍。用来定位桥段，效果不如划线或段评。

### 2.3 情绪标注类（训练情绪分类器）

| 数据集 | 规模与标签 | 许可 / 获取 | 能否商用 | 来源 |
|---|---|---|---|---|
| GoEmotions（Demszky et al., ACL 2020, arXiv 2005.00547） | 约 58k 条 Reddit 英文评论，27 类情绪加 Neutral | HF 数据卡 Apache-2.0 | 许可证本身允许商用；Reddit 原文的权利问题另行评估 `[未核实]` | https://github.com/google-research/google-research/tree/master/goemotions ；https://huggingface.co/datasets/google-research-datasets/go_emotions |
| SMP2020-EWECT | 通用微博：训练 27,768、验证 2,000、测试 5,000；疫情微博：8,606 / 2,000 / 3,000；六类（无情绪、积极、愤怒、悲伤、恐惧、惊奇）；中文信息学会社会媒体处理专委会主办，哈工大 SCIR 承办 | 官方页给的是百度网盘下载链接，没有写明许可证 `[未核实]`；HF 镜像 hecongqing/EWECT_weibo_senti 标注 license: unknown | 不明，按研究用途 | https://smp2020ewect.github.io/ |
| NLPCC 2013 微博情绪 | 七类（happiness、sadness、like、anger、disgust、fear、surprise）；有情绪微博训练集 4,338 条、测试集 2,172 条（据 Lai et al. 论文表 1）；原下载地址 tcci.ccf.org.cn/conference/2013/dldoc/evdata02.zip | 许可证 `[未核实]`；原链接现在能否访问未核实 | 不明，按研究用途 | https://arxiv.org/abs/1912.02545 |

中文情绪数据都来自微博短文本，与小说叙事文体差别较大，只能当作初始化或弱监督。更稳的做法是在 GPU 服务器上用 7B 以上的本地模型对段落做情绪打分，再用小规模人工标注校准（对照 ICC 和退化守卫流程）。

### 2.4 公版书文本

| 来源 | 要点 | 来源 |
|---|---|---|
| Project Gutenberg | 绝大多数作品“in the public domain in the United States”；“Project Gutenberg”是注册商标，保留商标再分发须遵守许可，商用须支付毛利 20% 的版税；去掉许可和全部 Gutenberg 字样后不受该限制；对美国以外的版权状态不作保证 | https://www.gutenberg.org/policy/license.html |
| Gutenberg 自动化访问 | 网站“intended for human users only”，检测到自动化访问会封 IP；批量获取请用镜像或 `robot/harvest` 接口，目录数据属公有领域 | https://www.gutenberg.org/policy/robot_access.html |
| 维基文库（中文） | 贡献内容采用 CC BY-SA 4.0 和 GFDL 双许可；明确区分公有领域原文与编者添加的标点、注释、排版；在中国大陆等地，作者署名权等人身权永久存续 | https://zh.wikisource.org/wiki/Wikisource:版权信息 ；https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use |
| 中国著作权保护期 | 《著作权法》（2020 修正，2021-06-01 施行）第二十三条第一款：自然人作品的发表权及第十条第一款第（五）至（十七）项权利，保护期为作者终生及死亡后五十年，截止于第五十年的 12 月 31 日；第二十二条：署名权、修改权、保护作品完整权不受限制 | https://www.elawcn.com/rule/2020/1115/721.html |

对本项目的含义：
- 项目 `data/books/` 已有 18 个 Gutenberg 文本（`pg*.txt`）。若要商用，应去掉 Gutenberg 许可头尾和全部商标字样，并按中国法自行确认这些作品在中国已进入公有领域。
- 按第二十三条推算：截至 2026 年，作者在 1975 年或更早去世的作品，财产权已经到期，但署名权等仍须尊重。译本的译者另享著作权，需按译者去世时间单独判断 `[未核实：译作相关条号本次未核对]`。
- 维基文库上的整理本：原文进入公有领域，但编者的标点、校勘、注释可能构成独创性贡献，复用时按 CC BY-SA 4.0 署名并以相同方式共享。只取原文、自行标点，可以避开 SA 义务，但工作量会增加。

---

## 3. 结论：推荐的数据组合

### 3.1 研究验证用（论文、内部方法验证，不对外商用）

| 数据 | 角色 | 理由 |
|---|---|---|
| Qidian-Webnovel Corpus 110（申请受限版） | 主标注：段落级读者反应 | 唯一公开的“段落定位 + 读者评论”中文语料，与目标任务同构；须以高校身份申请 |
| Goodreads spoiler / dedup reviews | 辅助：英文书评中的情节与情绪信号 | 规模大，句级标注；仅限学术 |
| Gutenberg 和维基文库公版文本 | 被分析对象 | 文本合法可得 |
| GoEmotions + SMP2020-EWECT / NLPCC 2013 | 情绪分类器训练与评测 | 有现成标签；中文数据的许可不明，只在研究阶段使用 |
| 本人或少量志愿者导出的微信读书划线（方式 A、C） | 小样本对照：检验模型选出的桥段与真实划线是否一致 | 规模小但真实，仅内部使用 |

### 3.2 商用落地用（获客内容生产）

| 数据 | 角色 | 理由 |
|---|---|---|
| 公版文本（去掉 Gutenberg 商标；维基文库原文自行整理或遵守 CC BY-SA） | 内容来源 | 法律上最干净 |
| 用研究线验证过的方法，加上本地开源模型打分 | 在没有读者标注的书上预测“打动人的桥段” | 方法可以迁移；模型权重的许可证需逐个确认 |
| 自有数据：自建小程序或社群里读者的划线、投票（带知情同意），以及自有短视频账号的完播、点赞等表现 | 持续标注与校准 | 权属清楚；自有账号后台数据的使用条款另行核对 `[未核实]` |
| 用户捐赠数据（方式 A，同意书写明商业用途） | 补充标注 | 合法，规模有限 |
| 平台或出版方授权数据（方式 D） | 有版权书目的划线热度和原文使用许可 | 有版权的新书必须走这条线，否则既缺数据权，也缺原文的著作权许可 |

Goodreads、Amazon、Qidian 语料、名句数据集、豆瓣无许可证仓库，都不能进入商用线。这一点对获客目标的直接含义是：用 Goodreads 等学术数据训练、验证出来的选段方法，可以作为研究成果或内部方法论保留；面向用户发布的内容、以及支撑商用产品的标注数据，都必须换成自有、经同意或经授权的数据。“用学术数据训练的模型能否商用”在许可文本中没有明确，稳妥的做法是商用模型只用可商用数据重新训练或校准 `[未核实：属法律解释问题，建议咨询律师]`。

### 3.3 各路线对比

| 路线 | 可行性 | 法律 / 合规风险 | 成本 | 适用阶段 |
|---|---|---|---|---|
| 抓取微信读书或 cookie 调接口 | 技术可行 | 高：协议 6.1.2.4/6.1.2.6；反不正当竞争法第十三条第三款；刑法第二百八十五条 | 低 | 不采用 |
| 官方 Skill，本人 Key 小规模 | 高 | 中：授权边界未明 | 低 | 研究 |
| 人工记录“N 人划线” | 中 | 低到中：规模化、持续化后上升 | 人工时间 | 研究探索 |
| 用户捐赠 + 知情同意 + 去标识化 | 中 | 低 | 中 | 研究、商用 |
| 平台或出版方合作 | 低到中 | 低 | 高 | 商用 |
| Goodreads、Amazon、Qidian 学术语料 | 高（Qidian 需申请） | 研究用途内低，商用不允许 | 低到中 | 研究 |
| 公版文本 + 开源模型 + 自有反馈数据 | 高 | 低 | 中（需要 GPU 服务器算力） | 商用 |

---

## 来源清单

1. https://mcauleylab.ucsd.edu/public_datasets/gdrive/goodreads/UCSD%20Book%20Graph.html （本项目代理已核实）
2. https://aclanthology.org/P19-1248 （本项目代理已核实）
3. https://github.com/MengtingWan/goodreads
4. https://www.pingwest.com/a/313814
5. https://weread.qq.com/r/weread-skills
6. https://github.com/tencent/wechatreading
7. https://www.skills.sh/tencent/wechatreading/weread-skills
8. https://raw.githubusercontent.com/zhaohongxuan/obsidian-weread-plugin/main/docs/weread-v2-guide.md
9. https://github.com/malinkang/weread2notion
10. https://sspai.com/post/47216
11. https://sspai.com/post/56150
12. https://www.woshipm.com/evaluating/5237152.html
13. https://weread.qq.com/web/copyright
14. https://www.news.cn/legal/20250627/4b6ec78bc9be4ea9a2968a9d34abd724/c.html
15. https://fgk.chinatax.gov.cn/zcfgk/c100009/c5211782/content.html
16. https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm
17. https://www.cac.gov.cn/2021-06/11/c_1624994566919140.htm
18. https://www.court.gov.cn/shenpan/xiangqing/283891.html
19. https://www.elawcn.com/rule/2020/1115/721.html
20. https://www.jiemian.com/article/1541062.html
21. https://www.tmtpost.com/2557736.html
22. https://www.elawcn.com/news/2016/0604/417.html
23. https://www.yicai.com/news/5340378.html
24. https://www.elawcn.com/ecommerce/2021/0805/895.html
25. https://hznews.hangzhou.com.cn/shehui/content/2020-06/02/content_7747527.htm
26. https://www.zhonglun.com/research/articles/9092.html
27. https://rouse.com/insights/news/2020/news-cases-from-china-june-2020/
28. https://www.elawcn.com/copyright/2021/0130/744.html
29. https://nijianmo.github.io/amazon/index.html
30. https://amazon-reviews-2023.github.io/
31. https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
32. https://reference-global.com/article/10.5334/johd.368
33. https://doi.org/10.34894/GQXX3K （DataverseNL）
34. https://github.com/RecoHut-Datasets/douban
35. https://github.com/Jiashuo-Sun/DoubanBookList
36. https://zenodo.org/records/15252768
37. https://www.kaggle.com/datasets/utmhikari/doubanmovieshortcomments
38. https://huggingface.co/datasets/Abirate/english_quotes
39. https://huggingface.co/datasets/jstet/quotes-500k
40. https://huggingface.co/datasets/EhsanShahbazi/goodreads-quotes
41. https://github.com/google-research/google-research/tree/master/goemotions
42. https://huggingface.co/datasets/google-research-datasets/go_emotions
43. https://smp2020ewect.github.io/
44. https://huggingface.co/datasets/hecongqing/EWECT_weibo_senti
45. https://arxiv.org/abs/1912.02545
46. https://www.gutenberg.org/policy/license.html
47. https://www.gutenberg.org/policy/robot_access.html
48. https://zh.wikisource.org/wiki/Wikisource:版权信息
49. https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use

## 核实状态表

| # | 内容 | 来源 | 状态 |
|---|---|---|---|
| 1 | Goodreads 数据仅限学术用途、不得再分发或商用 | 1 | 已核实（本项目代理 2026-10-08） |
| 2 | Goodreads spoiler 子集与 dedup 的规模、剧透标签自标 | 1, 2 | 已核实（本项目代理 2026-10-08） |
| 3 | MengtingWan/goodreads 仓库为 Apache-2.0 代码，数据 academic only | 3 | 已核实 |
| 4 | 微信读书官方 Skill 于 2026-05 发布，可读本人划线、热门划线、书评 | 4, 5, 6, 7 | 已核实 |
| 5 | Skill API Key 与身份绑定；没有写明频率或商用限制 | 5, 6 | 已核实 |
| 6 | 官方 Skill 是否允许批量采集或商用 | — | [未核实] |
| 7 | 面向第三方的微信读书数据开放平台不存在 | 检索为空 | [未核实] |
| 8 | App 笔记“导出”→“复制到剪贴板”（2018 版本） | 10, 11 | 已核实 |
| 9 | 当前版本导出入口与格式；官方直连印象笔记 | — | [未核实] |
| 10 | 热门划线以“🔥 N 人划线”展示，插件每书最多 20 条 | 8 | 已核实 |
| 11 | 划线写想法、评分与书评功能 | 12, 13 | 已核实 |
| 12 | 推荐 / 一般 / 不行三档与“推荐值” | — | [未核实] |
| 13 | 主流第三方工具由 cookie 转向官方 API Key | 8, 9 | 已核实 |
| 14 | 用户协议 6.1.2.3/6.1.2.4/6.1.2.6/8.1 条文 | 13 | 已核实 |
| 15 | 用户协议中没有 UGC 权属或授权条款 | 13 | [未核实]（仅限本次抓取文本） |
| 16 | 反不正当竞争法 2025 修订：通过和施行日期，第二条，第十三条（含第三款数据条款） | 14 | 已核实 |
| 17 | 反不正当竞争法 2019 修正第十二条（互联网专条） | 15 | 已核实（检索） |
| 18 | PIPL 第四条、第十三条第一款第（六）项、第二十七条、第七十三条 | 16 | 已核实 |
| 19 | 数据安全法第三十二条第一款 | 17 | 已核实 |
| 20 | 刑法第二百八十五条第二款 | 18 | 已核实（检索） |
| 21 | 著作权法第二十二条、第二十三条第一款、第二十四条第一款第（一）（六）项 | 19 | 已核实 |
| 22 | 微博诉脉脉：案号、法院、日期、200 万元、三重授权 | 20, 21 | 已核实 |
| 23 | 大众点评诉百度：一审、二审结果、金额、条数 | 22, 23 | 已核实 |
| 24 | 大众点评诉百度二审案号（2016）沪73民终242号 | — | [未核实] |
| 25 | 淘宝诉美景：案号、法院、200 万元、竞争性财产权益 | 24 | 已核实 |
| 26 | 腾讯诉聚客通：日期、260 万元、数据权益二分（法院名称两个来源说法不一） | 25, 26, 27 | 已核实 |
| 27 | 腾讯诉聚客通案号（2019）浙8601民初1987号 | 只见于检索结果标题 | [未核实] |
| 28 | 抖音诉刷宝：海淀法院、5 万余条、500 万元 | 28 | 已核实 |
| 29 | 抖音诉刷宝案号 | — | [未核实] |
| 30 | Amazon 2018 规模（233.1M；Books 51,311,621） | 29 | 已核实 |
| 31 | Amazon 2018 许可证 | 29 | [未核实]（页面没有写明） |
| 32 | Amazon 2023 规模（571.54M；Books 29.5M 评分） | 30, 31 | 已核实 |
| 33 | Amazon 2023 许可证 | 30, 31 | [未核实]（没有写明） |
| 34 | Qidian-Webnovel Corpus 规模、段落级、论文 CC BY 4.0 | 32 | 已核实 |
| 35 | Qidian 语料受限访问、仅非营利研究、须签 DTA | 33 | 已核实 |
| 36 | 平台官方公开的起点或晋江段评数据集 | 检索为空 | [未核实] |
| 37 | RecoHut-Datasets/douban、Jiashuo-Sun/DoubanBookList 没有 LICENSE | 34, 35 | 已核实 |
| 38 | Zenodo 豆瓣与 Goodreads 平行数据：CC BY 4.0，书级 | 36 | 已核实 |
| 39 | Kaggle 豆瓣电影短评的许可证 | 37 | [未核实] |
| 40 | Abirate/english_quotes：2,508 条，CC BY 4.0，源自 Goodreads | 38 | 已核实 |
| 41 | quotes-500k：499,709 条，没有许可证 | 39 | 已核实 |
| 42 | EhsanShahbazi/goodreads-quotes 许可证（MIT 与 other 不一致） | 40 | [未核实]（来源冲突） |
| 43 | GoEmotions：58k、27 类加 Neutral、Apache-2.0（HF） | 41, 42 | 已核实 |
| 44 | GoEmotions 底层 Reddit 内容的商用权利 | — | [未核实] |
| 45 | SMP2020-EWECT：规模、六类、主办方、网盘获取 | 43 | 已核实 |
| 46 | SMP2020-EWECT 许可证 | 43, 44 | [未核实]（官方未声明，镜像为 unknown） |
| 47 | NLPCC 2013：七类、4,338 / 2,172 条 | 45 | 已核实（二手：论文引用） |
| 48 | NLPCC 2013 许可证与原链接是否可用 | — | [未核实] |
| 49 | Gutenberg：美国公版、商标、20% 版税、不保证美国以外的版权状态 | 46 | 已核实 |
| 50 | Gutenberg 禁止自动化访问，提供镜像和 harvest 接口 | 47 | 已核实 |
| 51 | 维基文库 CC BY-SA 4.0 与 GFDL 双许可、人身权永久 | 48, 49 | 已核实 |
| 52 | 译作著作权单独计算的条号 | — | [未核实] |
| 53 | 学术数据训练的模型能否商用 | — | [未核实]（法律解释问题） |
| 54 | 自有短视频账号后台数据的使用条款 | — | [未核实] |

统计：共 54 条，已核实 35 条（其中 2 条为本项目代理核实，3 条依据检索结果或二手引用），[未核实] 19 条。

---

## 附：本项目实际用到的数据（2026-10-08 实测）

| 项 | 实测 |
|---|---|
| 下载来源 | `https://mcauleylab.ucsd.edu/public_datasets/gdrive/goodreads/`（页面上的 Google Drive 直链已 404，镜像可用）；`goodreads_reviews_spoiler.json.gz` 620,197,603 字节、`goodreads_reviews_dedup.json.gz` 5,343,667,350 字节、`goodreads_books.json.gz` 2,083,197,934 字节、`goodreads_book_works.json.gz` 75,397,299 字节 |
| 剧透子集规模 | 1,378,033 条书评、25,475 本书，与论文一致；其中 20,029 个 book_id 能对上 works 表的 best_book_id |
| 选中书目的评论 | 剧透子集：盖茨比 986、傲慢与偏见 773、简·爱 593 条；完整去重书评（同作品全部英文版本）：6,273 / 5,858 / 4,111 条 |
| 存放 | `data/raw/ucsd/`（gitignore，只在本机）；抽取结果 `data/interim/`（gitignore） |
| 使用边界 | 仅学术研究；仓库、展示页、幻灯片只出现聚合量、公版原文、跨多条评论聚合的高频词，以及代理撰写的中文摘要，不出现评论原文与任何用户标识 |
| 微信读书官方 Skill | 本项目代理另行打开 `https://github.com/tencent/wechatreading` 核对：README 写明可访问“划线内容、个人想法、热门划线”与“公开点评浏览与筛选”，Key 在 `weread.qq.com/r/weread-skills` 获取、“API Key 绑定用户身份”，代码许可证 Apache-2.0；README 未写调用频率与商用限制 |
| 用户导出的适配器 | `src/adapters/weread_export.py`：只读用户本人导出的文本或 Skill 返回的 JSON（字段名 [未核实]），中文用字符 6-gram 对齐原文，输出每段划线数并可按读完率做逆留存加权；不访问任何接口 |
