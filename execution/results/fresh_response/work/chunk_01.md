# chunk 01 (5 segments) - mode polish, genre response

Keep: numbers/units, citation markers, Fig./Table/Eq. references, math, hedges, negation, quantifiers, conditions.

[p1.s1] **Comment 2.1:** The authors should explain why the capacity drops after 200 cycles.
    keep: nums 2.1 200

[p2.s1] **Response:** Thanks for the comment.

[p2.s2] We think the capacity drop is mainly caused by the cracking of particles, as shown in the new Fig. S5.
    keep: xref figs5; hedge:moderate=mainly; causal=caused

[p2.s3] We have add a discussion in Section 3.4.
    keep: xref sec3.4

[p2.s4] However, we don't agree that the electrolyte decomposition is the main reason, because the impedance only increase by 12% after 200 cycles (Table S2).
    keep: nums 12 200; xref table2; negation=don't; q:exclusive=only; causal=because
    hint EN01 (register): "don't" - contraction in academic prose; write the full form (do not, cannot, it is)
