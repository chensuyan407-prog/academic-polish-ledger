# chunk 01 (5 segments) - mode translate_zh_en, genre grant

Keep: numbers/units, citation markers, Fig./Table/Eq. references, math, hedges, negation, quantifiers, conditions.

[p1.s1] 本项目拟以钠离子电池硬碳负极为研究对象，揭示其储钠机制。
    keep: hedge:moderate=拟

[p1.s2] 前期研究表明，硬碳的首次库伦效率仅为75%左右，严重制约了其实际应用[3]。
    keep: nums 75; citation [3]; hedge:moderate=表明; approximator=左右; q:exclusive=仅

[p1.s3] 申请人团队在前期工作中发现，引入适量的硫掺杂可以将可逆容量提高到约320 mAh g-1（图1）。
    keep: nums 320 1; xref 图1; approximator=约

[p1.s4] 然而，掺杂对首次库伦效率的影响尚不清楚。
    keep: negation=不

[p1.s5] 本项目将重点研究缺陷结构与储钠行为之间的关系，有望为高性能负极材料的设计提供理论依据。
    keep: hedge:weak=有望
