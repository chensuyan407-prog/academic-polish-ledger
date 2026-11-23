# Change log - dev-tex-methods

mode `polish` · genre `journal` · 6 edited units of 7 segments in scope · verdicts {'pass': 6}

Legend: ~~deleted~~ **inserted**. Every change has from → to, type and reason; flags are the invariant checks (I = meaning, R = record, D = document).

## [p1.s1] pass

- original: The model were trained on 12,000 images using the Adam optimizer \cite{kingma2015} with a learning rate of $10^{-4}$.
- revised: The model was trained on 12,000 images using the Adam optimizer \cite{kingma2015} with a learning rate of $10^{-4}$.
- diff: The model ~~were~~**was** trained on 12,000 images using the Adam optimizer \cite{kingma2015} with a learning rate of $10^{-4}$.

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | were | was | agreement | singular subject 'model' |


## [p1.s2] pass

- original: As shown in Fig.~\ref{fig:arch}, the network consist of three convolutional block.
- revised: As shown in Fig.~\ref{fig:arch}, the network consists of three convolutional blocks.
- diff: As shown in Fig.~\ref{fig:arch}, the network ~~consist~~**consists** of three convolutional ~~block~~**blocks**.

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | consist | consists | agreement | singular subject 'network' |
| 2 | block | blocks | number-agreement | plural after 'three' |


## [p1.s3] pass

- original: Data augmentation, e.g random cropping and flipping, was applied to all the training images.
- revised: Data augmentation, e.g., random cropping and flipping, was applied to all training images.
- diff: Data augmentation, e.g**.,** random cropping and flipping, was applied to all ~~the ~~training images.

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | e.g | e.g., | punctuation | abbreviation needs full stop and comma |
| 2 | all the training | all training | concision | article not needed |


## [p2.s1] pass

- original: We find that the accuracy is significantly higher than the baseline ($p < 0.01$, Table~\ref{tab:res}), which suggest the attention module may improve feature extraction.
- revised: We found that the accuracy is significantly higher than that of the baseline ($p < 0.01$, Table~\ref{tab:res}), which suggests that the attention module may improve feature extraction.
- diff: We ~~find~~**found** that the accuracy is significantly higher than** that of** the baseline ($p < 0.01$, Table~\ref{tab:res}), which ~~suggest~~**suggests that** the attention module may improve feature extraction.

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | find | found | tense | past tense for completed experiments |
| 2 | the baseline | that of the baseline | clarity | compare accuracy with accuracy |
| 3 | suggest the | suggests that the | agreement | relative clause refers to the whole finding (singular); 'that' added for clarity |


## [p2.s2] pass

- original: The training takes approximately 6 hours on a single GPU, and no early stopping were used.
- revised: Training took approximately 6 hours on a single GPU, and no early stopping was used.
- diff: ~~The~~**Training** ~~training takes~~**took** approximately 6 hours on a single GPU, and no early stopping ~~were~~**was** used.

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | The training takes | Training took | tense | past tense for the completed procedure; generic noun without article |
| 2 | were | was | agreement | 'early stopping' is singular |


## [p3.s1] pass

- original: Where $y_i$ is the ground-truth label and $\hat{y}_i$ the predicted probability.
- revised: where $y_i$ is the ground-truth label and $\hat{y}_i$ is the predicted probability.
- diff: ~~Where~~**where** $y_i$ is the ground-truth label and $\hat{y}_i$ **is **the predicted probability.

| # | from | to | type | reason |
|---|---|---|---|---|
| 1 | Where | where | format | continuation of the sentence ending with the equation |
| 2 | and $\hat{y}_i$ the | and $\hat{y}_i$ is the | grammar | verb added for parallel structure |

