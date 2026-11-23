# chunk 01 (7 segments) - mode polish, genre journal

Keep: numbers/units, citation markers, Fig./Table/Eq. references, math, hedges, negation, quantifiers, conditions.

[h1] (heading) Methods

[p1.s1] The model were trained on 12,000 images using the Adam optimizer \cite{kingma2015} with a learning rate of $10^{-4}$.
    keep: nums 12,000; citation \cite{kingma2015}; math $10^{-4}$
    hint EN13 (grammar): "The model were" - subject-verb agreement (singular subject, plural verb)?; is / was / has / shows

[p1.s2] As shown in Fig.~\ref{fig:arch}, the network consist of three convolutional block.
    keep: nums three; xref \ref{fig:arch}
    hint EN11 (number-agreement): "three convolutional block" - plural determiner with singular noun; use the plural noun
    hint EN13 (grammar): "the network consist" - subject-verb agreement (singular subject, plural verb)?; is / was / has / shows

[p1.s3] Data augmentation, e.g random cropping and flipping, was applied to all the training images.
    keep: q:universal=all
    hint EN18 (punctuation): "e.g" - abbreviation without its full stop; e.g., i.e., et al., etc.

[p2.s1] We find that the accuracy is significantly higher than the baseline ($p < 0.01$, Table~\ref{tab:res}), which suggest the attention module may improve feature extraction.
    keep: xref \ref{tab:res}; math $p<0.01$; hedge:weak=may; hedge:moderate=suggest; significance=significantly
    hint EN28 (agreement): ", which suggest" - 'which' referring to the preceding clause takes a singular verb; which suggests / which indicates

[p2.s2] The training takes approximately 6 hours on a single GPU, and no early stopping were used.
    keep: nums 6; approximator=approximately; negation=no

[p3.s1] Where $y_i$ is the ground-truth label and $\hat{y}_i$ the predicted probability.
    keep: math $y_i$ $\hat{y}_i$
    hint TEX01 (format): "Where $" - 'Where' after a display equation usually continues the sentence; lower-case 'where' (no paragraph break before it)
