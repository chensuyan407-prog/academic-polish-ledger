# chunk 01 (5 segments) - mode polish, genre grant

Keep: numbers/units, citation markers, Fig./Table/Eq. references, math, hedges, negation, quantifiers, conditions.

[p1.s1] 本项目针对锂金属负极枝晶生长的问题，提出了一种全新的人工SEI膜设计策略。
    keep: novelty=全新
    hint ZH02 (register): "全新" - 宣传化/夸大表述; 改为中性描述；若为基金申请书中的创新性陈述，保留事实部分并标注需人工确认

[p1.s2] 前期结果显示，该策略可使对称电池的循环寿命从200 h延长至800 h以上（图2）。
    keep: nums 200 800; xref 图2; approximator=以上

[p1.s3] 这一结果国际领先，彻底解决了枝晶问题。
    keep: booster=彻底; novelty=国际领先
    hint ZH02 (register): "国际领先" - 宣传化/夸大表述; 改为中性描述；若为基金申请书中的创新性陈述，保留事实部分并标注需人工确认
    hint ZH03 (register): "彻底解决" - 绝对化表述; 仅在材料支持时保留；修改会削弱结论，需记录

[p1.s4] 然而，在高电流密度（>3 mA cm-2）下，金属锂负极的枝晶抑制效果仍不理想[8]。
    keep: nums 3 2; citation [8]; negation=不; conditional=在高电流密度（>3 ma cm-2）下
    hint TERM (terminology): "金属锂负极" is a termbase variant; use "锂金属负极"
    hint TERM (terminology): "锂负极" is a termbase variant; use "锂金属负极"

[p1.s5] 因此，本项目拟进一步研究SEI膜组成与锂沉积形貌之间的关系，以期为高能量密度电池的开发提供指导。
    keep: hedge:weak=以期; hedge:moderate=拟; causal=因此
