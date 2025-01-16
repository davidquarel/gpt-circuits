from typing import Optional

import torch
import torch.nn as nn

from config.sae.models import SAEConfig
from config.sae.training import LossCoefficients
from models.sae import EncoderOutput, SAELossComponents, SparseAutoencoder


class StandardSAE(nn.Module, SparseAutoencoder):
    """
    SAE technique as described in:
    https://transformer-circuits.pub/2024/april-update/index.html#training-saes
    """

    def __init__(self, layer_idx: int, config: SAEConfig, loss_coefficients: Optional[LossCoefficients]):
        super().__init__()
        F = config.n_features[layer_idx]  # SAE dictionary size.
        n_embd = config.gpt_config.n_embd  # GPT embedding size.
        self.l1_coefficient = loss_coefficients.l1[layer_idx] if loss_coefficients else None
        self.W_dec = nn.Parameter(torch.nn.init.kaiming_uniform_(torch.empty(F, n_embd)))

        self.b_enc = nn.Parameter(torch.zeros(F))
        self.b_dec = nn.Parameter(torch.zeros(n_embd))

        try:
            # NOTE: Subclass might define these properties.
            self.W_enc = nn.Parameter(torch.empty(n_embd, F))
            self.W_enc.data = self.W_dec.data.T.detach().clone()  # initialize W_enc from W_dec
        except KeyError:
            pass

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: GPT model activations (batch_size, n_embd)
        """
        return nn.ReLU()((x - self.b_dec) @ self.W_enc + self.b_enc)

    def decode(self, feature_magnitudes: torch.Tensor) -> torch.Tensor:
        """
        feature_magnitudes: SAE activations (batch_size, F)
        """
        return feature_magnitudes @ self.W_dec + self.b_dec

    def forward(self, x: torch.Tensor) -> EncoderOutput:
        """
        Returns a reconstruction of GPT model activations and feature magnitudes.
        Also return loss components if loss coefficients are provided.

        x: GPT model activations (batch_size, n_embd)
        """
        feature_magnitudes = self.encode(x)
        x_reconstructed = self.decode(feature_magnitudes)
        output = EncoderOutput(x_reconstructed, feature_magnitudes)

        if self.l1_coefficient:
            decoder_norm = torch.norm(self.W_dec, p=2, dim=1)  # L2 norm
            sparsity_loss = (feature_magnitudes * decoder_norm).sum(dim=-1).mean() * self.l1_coefficient
            output.loss = SAELossComponents(x, x_reconstructed, feature_magnitudes, sparsity_loss)

        return output


class StandardSAE_V2(StandardSAE):
    """
    Experimental Sparse Autoencoder module that ties the encoder and decoder weights to avoid feature absorption.
    Reference: https://www.lesswrong.com/posts/kcg58WhRxFA9hv9vN
    """

    @property
    def W_enc(self):
        """
        Tying encoder weights to decoder weights.
        """
        return self.W_dec.t()
