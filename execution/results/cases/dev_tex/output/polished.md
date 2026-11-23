\section{Methods}
\label{sec:methods}
The model was trained on 12,000 images using the Adam optimizer \cite{kingma2015} with a learning rate of $10^{-4}$. As shown in Fig.~\ref{fig:arch}, the network consists of three convolutional blocks. Data augmentation, e.g., random cropping and flipping, was applied to all training images.

We found that the accuracy is significantly higher than that of the baseline ($p < 0.01$, Table~\ref{tab:res}), which suggests that the attention module may improve feature extraction. Training took approximately 6 hours on a single GPU, and no early stopping was used.
\begin{equation}
L = -\sum_i y_i \log \hat{y}_i
\end{equation}
% TODO: add hyperparameter table
where $y_i$ is the ground-truth label and $\hat{y}_i$ is the predicted probability.
