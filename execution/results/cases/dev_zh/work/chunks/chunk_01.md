# chunk 01 (7 segments) - mode polish, genre thesis

Keep: numbers/units, citation markers, Fig./Table/Eq. references, math, hedges, negation, quantifiers, conditions.

[h1] (heading) 2.3 样品表征
    keep: nums 2.3

[p1.s1] 通过X光衍射（XRD）分析，使样品的晶体结构得到了确认。
    keep: booster=确认
    hint ZH04 (grammar): "通过X光衍射（XRD）分析，使" - 介词结构开头导致主语缺失（"通过……使……"）; 删去介词或补出主语
    hint TERM (terminology): "X光衍射" is a termbase variant; use "X射线衍射" (abbr XRD)

[p1.s2] 样品的形貌采用扫描电镜进行观察，结果如图2所示。
    keep: xref 图2
    hint ZH05 (concision): "进行观察" - 冗余名词化（"进行了分析"）; 直接用动词（"分析了"）
    hint TERM (terminology): "扫描电镜" is a termbase variant; use "扫描电子显微镜" (abbr SEM)

[p1.s3] 从图中可以看出，掺杂后颗粒尺寸由约50 nm减小到30 nm左右，这可能与氧缺陷的形成有关[12]。
    keep: nums 50 30; citation [12]; hedge:weak=可能; approximator=左右/约; correlational=有关
    hint ZH15 (concision): "从图中可以看出" - 口语化引导语; “由图N可见”“图N表明”；补出具体图表号
    hint TERM (terminology): "氧缺陷" is a termbase variant; use "氧空位"

[p1.s4] 我们对不同温度下煅烧的样品进行了系统的分析，发现当煅烧温度高于600 ℃时，大部分样品出现了明显的团聚现象。
    keep: nums 600; q:majority=大部分; conditional=当煅烧温度高于600 ℃时
    hint ZH05 (concision): "进行了系统的分析" - 冗余名词化（"进行了分析"）; 直接用动词（"分析了"）
    hint ZH14 (register): "我们" - 学位论文/期刊中文稿使用第一人称; 学位论文通常用“本文”“本研究”；按目标文体决定

[p1.s5] XPS结果表明，Ce3+的比例随掺杂量增加而升高（表3）,说明氧空位浓度提高了。
    keep: xref 表3; hedge:moderate=表明
    hint ZH07 (punctuation): "）," - 中文语境使用半角标点; 改为全角，。；：？！

[p1.s6] 该方法非常简单，并且完全解决了传统方法中团聚的问题。
    keep: booster=完全
    hint ZH01 (register): "非常" - 口语化表达; 改为书面语（大量、显著、本文认为）；不改变数量或强度
    hint ZH03 (register): "完全解决" - 绝对化表述; 仅在材料支持时保留；修改会削弱结论，需记录
