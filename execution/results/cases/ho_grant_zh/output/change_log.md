# Change log - ho-grant-zh

mode `polish` · genre `grant` · 4 edited units of 5 segments in scope · verdicts {'warn': 2, 'pass': 2}

Legend: ~~deleted~~ **inserted**. Every change has from → to, type and reason; flags are the invariant checks (I = meaning, R = record, D = document).

## [p1.s1] warn

- original: 本项目针对锂金属负极枝晶生长的问题，提出了一种全新的人工SEI膜设计策略。
- revised: 本项目针对锂金属负极枝晶生长问题，提出一种新的人工SEI膜设计策略。
- diff: 本项目针对锂金属负极枝晶生长~~的~~问题，提出~~了~~一种~~全~~新的人工SEI膜设计策略。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 生长的问题 | 生长问题 | concision | 删去冗余“的” |
| 2 | 提出了一种全新的 | 提出一种新的 | register | “全新”为宣传化表述；申请书中描述拟开展工作不用“了” |

- I09 **warn**: novelty/priority claim removed: ['全新'] -> []
- needs author confirmation: “全新”改为“新的”，如需强调创新性，请在创新点部分给出与已有策略的具体区别

## [p1.s2] pass

- original: 前期结果显示，该策略可使对称电池的循环寿命从200 h延长至800 h以上（图2）。
- revised: 前期结果显示，该策略可将对称电池的循环寿命从200 h延长至800 h以上（图2）。
- diff: 前期结果显示，该策略可~~使~~**将**对称电池的循环寿命从200 h延长至800 h以上（图2）。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 可使 | 可将 | collocation | “将……从……延长至……”搭配更规范 |


## [p1.s3] warn

- original: 这一结果国际领先，彻底解决了枝晶问题。
- revised: 这一结果优于已报道的同类工作，并明显抑制了枝晶生长。
- diff: 这一结果~~国际领先~~**优于已报道的同类工作**，~~彻底解决~~**并明显抑制**了枝晶~~问题~~**生长**。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 这一结果国际领先 | 这一结果优于已报道的同类工作 | register | “国际领先”为宣传化表述，改为可核查的比较 |
| 2 | 彻底解决了枝晶问题 | 并明显抑制了枝晶生长 | register | “彻底解决”与第4句“高电流密度下抑制效果仍不理想”矛盾，改为有材料支持的表述 |

- I06 **accepted**: booster removed (claim softened): ['彻底'] -> [] — accepted: 删除“彻底”是有意削弱，依据是本段第4句
- I09 **accepted**: novelty/priority claim removed: ['国际领先'] -> [] — accepted: 删除“国际领先”，改为比较性陈述
- I14 **accepted**: direction words changed: up [] down [] -> up [] down ['抑制'] — accepted: “解决”改为“抑制”为同向表述
- R03 **warn**: heavy rewrite (60% of tokens changed) without a restructure/sentence-split type
- needs author confirmation: “优于已报道的同类工作”需要申请人给出对比文献；“彻底解决”已削弱为“明显抑制”，请确认

## [p1.s4] pass

- original: 然而，在高电流密度（>3 mA cm-2）下，金属锂负极的枝晶抑制效果仍不理想[8]。
- revised: 然而，在高电流密度（>3 mA cm-2）下，锂金属负极的枝晶抑制效果仍不理想[8]。
- diff: 然而，在高电流密度（>3 mA cm-2）下，**锂**金属~~锂~~负极的枝晶抑制效果仍不理想[8]。

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | 金属锂负极 | 锂金属负极 | terminology | 术语表标准写法，与第1句统一 |

