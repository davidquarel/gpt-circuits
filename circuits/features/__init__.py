"""
Utility functions for computing and caching feature metrics.
"""

from dataclasses import dataclass
from pathlib import Path

import torch

from circuits.features.cache import ModelCache
from circuits.features.profiles import ModelProfile
from circuits.features.samples import ModelSampleSet
from config import Config
from data.dataloaders import DatasetShard
from models.sparsified import SparsifiedGPT


@dataclass(frozen=True)
class Feature:
    """
    Represents a feature at a specific location.
    """

    layer_idx: int
    token_idx: int
    feature_idx: int

    def as_tuple(self) -> tuple[int, int, int]:
        return self.layer_idx, self.token_idx, self.feature_idx

    def __repr__(self) -> str:
        return f"({f'{self.token_idx},': <4}{self.feature_idx: >4})"

    def __lt__(self, other: "Feature") -> bool:
        return self.as_tuple() < other.as_tuple()


def compute_metrics(checkpoint_dir: Path, shard: DatasetShard, batch_size: int = 256):
    """
    Compute and cache feature metrics for a given model and dataset.

    :param checkpoint_dir: The directory containing the model checkpoint.
    :param shard: The dataset shard to analyze.
    :param batch_size: The batch size to use for analysis.
    """
    # Load model
    defaults = Config()
    model: SparsifiedGPT = SparsifiedGPT.load(checkpoint_dir, device=defaults.device).to(defaults.device)

    # Compile if enabled
    if defaults.compile:
        model = torch.compile(model)  # type: ignore

    model_cache = ModelCache()
    model_cache.compute(model, shard, batch_size)
    model_cache.save(checkpoint_dir)

    model_profile = ModelProfile()
    model_profile.compute(model_cache)
    model_profile.save(checkpoint_dir)

    model_sample_set = ModelSampleSet()
    model_sample_set.compute(model_cache)
    model_sample_set.save(checkpoint_dir)
