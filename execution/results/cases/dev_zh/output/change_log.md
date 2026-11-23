# Change log - dev-zh-thesis

mode `polish` · genre `thesis` · 6 edited units of 7 segments in scope · verdicts {'pass': 6}

Legend: ~~deleted~~ **inserted**. Every change has from → to, type and reason; flags are the invariant checks (I = meaning, R = record, D = document).

## [p1.s1] pass

- original: 通过X光衍射（XRD）分析，使样品的晶体结构得到了确认。
- revised: X射线衍射（XRD）分析确认了样品的晶体结构。
- diff: ~~通过~~X~~光~~**射线**衍射（XRD）分析~~，使~~**确认了**样品的晶体结构~~得到了确认~~。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 通过X光衍射（XRD）分析，使样品的晶体结构得到了确认 | X射线衍射（XRD）分析确认了样品的晶体结构 | grammar | “通过……使……”导致主语缺失，改为以分析方法作主语 |
| 2 | X光衍射 | X射线衍射 | terminology | 术语表标准写法 |


## [p1.s2] pass

- original: 样品的形貌采用扫描电镜进行观察，结果如图2所示。
- revised: 采用扫描电子显微镜（SEM）观察样品形貌，结果如图2所示。
- diff: ~~样品的形貌~~采用扫描电**子显微**镜~~进行~~**（SEM）**观察**样品形貌**，结果如图2所示。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 样品的形貌采用扫描电镜进行观察 | 采用扫描电子显微镜（SEM）观察样品形貌 | concision | 去掉“进行”名词化；语序调整为方法在前 |
| 2 | 扫描电镜 | 扫描电子显微镜（SEM） | terminology | 术语表标准写法，首次出现给出缩写 |


## [p1.s3] pass

- original: 从图中可以看出，掺杂后颗粒尺寸由约50 nm减小到30 nm左右，这可能与氧缺陷的形成有关[12]。
- revised: 由图2可见，掺杂后颗粒尺寸由约50 nm减小到约30 nm，这可能与氧空位的形成有关[12]。
- diff: ~~从~~**由**图~~中~~**2**可~~以看出~~**见**，掺杂后颗粒尺寸由约50 nm减小到**约**30 nm~~左右~~，这可能与氧~~缺陷~~**空位**的形成有关[12]。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 从图中可以看出 | 由图2可见 | concision | 口语化引导语改为书面语，并明确图号 |
| 2 | 30 nm左右 | 约30 nm | concision | 与前一数值的概数写法统一；概数词数量不变 |
| 3 | 氧缺陷 | 氧空位 | terminology | 术语表标准写法 |

- I03 **accepted**: figure/table/equation references changed: missing [], added ['fig:2'] — accepted: “从图中”指的就是上一句的图2，补出图号不改变指向

## [p1.s4] pass

- original: 我们对不同温度下煅烧的样品进行了系统的分析，发现当煅烧温度高于600 ℃时，大部分样品出现了明显的团聚现象。
- revised: 本文系统分析了在不同温度下煅烧的样品，发现当煅烧温度高于600 ℃时，大部分样品出现明显团聚。
- diff: ~~我们对~~**本文系统分析了在**不同温度下煅烧的样品~~进行了系统的分析~~，发现当煅烧温度高于600 ℃时，大部分样品出现~~了~~明显~~的~~团聚~~现象~~。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 我们对不同温度下煅烧的样品进行了系统的分析 | 本文系统分析了在不同温度下煅烧的样品 | register | 学位论文用“本文”替代第一人称；去掉“进行了……的分析”名词化 |
| 2 | 出现了明显的团聚现象 | 出现明显团聚 | concision | “团聚现象”冗余 |


## [p1.s5] pass

- original: XPS结果表明，Ce3+的比例随掺杂量增加而升高（表3）,说明氧空位浓度提高了。
- revised: XPS结果表明，Ce3+的比例随掺杂量增加而升高（表3），说明氧空位浓度提高。
- diff: XPS结果表明，Ce3+的比例随掺杂量增加而升高（表3）~~,~~**，**说明氧空位浓度提高~~了~~。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | ）, | ）， | punctuation | 中文语境使用全角逗号 |
| 2 | 提高了 | 提高 | concision | 删去句末冗余“了” |

- needs author confirmation: XPS 缩写在本节首次出现时未给出全称（X射线光电子能谱），请确认前文是否已定义

## [p1.s6] pass

- original: 该方法非常简单，并且完全解决了传统方法中团聚的问题。
- revised: 该方法操作简便，并且有效抑制了传统方法中的团聚问题。
- diff: 该方法~~非常~~**操作**简~~单~~**便**，并且~~完全解决~~**有效抑制**了传统方法中**的**团聚~~的~~问题。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 非常简单 | 操作简便 | register | 口语化表述改为书面语 |
| 2 | 完全解决了传统方法中团聚的问题 | 有效抑制了传统方法中的团聚问题 | register | 绝对化表述；上一句仅报告大部分样品的团聚情况，材料不支持“完全解决” |

- I06 **accepted**: booster removed (claim softened): ['完全'] -> [] — accepted: 删除绝对化“完全”是有意削弱，依据是同节第4句“大部分样品出现明显团聚”
- I14 **accepted**: direction words changed: up [] down [] -> up [] down ['抑制'] — accepted: “解决”改为“抑制”属同向表述，未翻转方向
- needs author confirmation: “完全解决”改为“有效抑制”削弱了原结论，请作者确认
