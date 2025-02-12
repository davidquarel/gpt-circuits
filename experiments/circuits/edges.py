"""
Find and export all circuit edges between two layers needed to reconstruct the output logits of a model to within a
certain KL divergence threshold.

$ python -m experiments.circuits.edges --circuit=train.0.0.51 --upstream_layer=0
"""

import argparse
import json
from pathlib import Path

import torch

from circuits import Edge, Node
from circuits.features.cache import ModelCache
from circuits.features.profiles import ModelProfile
from circuits.search.ablation import ResampleAblator, ZeroAblator  # noqa: F401
from circuits.search.edges import EdgeSearch
from config import Config, TrainingConfig
from data.dataloaders import DatasetShard
from models.sparsified import SparsifiedGPT


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="e2e.jumprelu.shakespeare_64x4", help="Model to analyze")
    parser.add_argument("--circuit", type=str, default="train.0.0.51", help="Circuit directory name")
    parser.add_argument("--upstream_layer", type=int, default=0, help="Find edges from this layer")
    parser.add_argument("--threshold", type=float, default=0.1, help="Max threshold for KL divergence")
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()
    threshold = args.threshold

    # Set paths
    checkpoint_dir = TrainingConfig.checkpoints_dir / args.model
    circuit_dir = Path("exports") / args.model / "circuits" / args.circuit
    upstream_path = circuit_dir / f"nodes.{args.upstream_layer}.json"
    downstream_path = circuit_dir / f"nodes.{args.upstream_layer + 1}.json"

    # Load model
    defaults = Config()
    model: SparsifiedGPT = SparsifiedGPT.load(checkpoint_dir, device=defaults.device).to(defaults.device)
    model.eval()

    # Compile if enabled
    if defaults.compile:
        model = torch.compile(model)  # type: ignore

    # Load cached metrics and feature magnitudes
    model_profile = ModelProfile(checkpoint_dir)
    model_cache = ModelCache(checkpoint_dir)

    # Set feature ablation strategy
    # ablator = ZeroAblator()
    k_nearest = 128  # How many nearest neighbors to consider in resampling
    num_samples = 128  # Number of samples to use for estimating KL divergence
    positional_coefficient = 2.0  # How important is the position of a feature
    ablator = ResampleAblator(
        model_profile,
        model_cache,
        k_nearest=k_nearest,
        positional_coefficient=positional_coefficient,
    )

    # Load sequence args
    with open(upstream_path) as f:
        upstream_json = json.load(f)
        data_dir = upstream_json["data_dir"]
        split = upstream_json["split"]
        shard_idx = upstream_json["shard_idx"]
        sequence_idx = upstream_json["sequence_idx"]
        target_token_idx = upstream_json["token_idx"]
        layer_idx = upstream_json["layer_idx"]

    # Load shard
    shard = DatasetShard(dir_path=data_dir, split=split, shard_idx=shard_idx)

    # Get token sequence
    tokenizer = model.gpt.config.tokenizer
    tokens: list[int] = shard.tokens[sequence_idx : sequence_idx + model.config.block_size].tolist()
    decoded_tokens = tokenizer.decode_sequence(tokens)
    decoded_target = tokenizer.decode_token(tokens[target_token_idx])
    print(f'Using sequence: "{decoded_tokens.replace("\n", "\\n")}"')
    print(f"Target token: `{decoded_target}` at index {target_token_idx}")
    print(f"Target layer: {layer_idx}")
    print(f"Target threshold: {threshold}")

    # Load nodes
    upstream_nodes = set()
    with open(upstream_path) as f:
        data = json.load(f)
        for token_idx, feature_idxs in data["nodes"].items():
            for feature_idx in feature_idxs:
                upstream_nodes.add(Node(layer_idx, int(token_idx), feature_idx))
    downstream_nodes = set()
    with open(downstream_path) as f:
        data = json.load(f)
        for token_idx, feature_idxs in data["nodes"].items():
            for feature_idx in feature_idxs:
                downstream_nodes.add(Node(layer_idx + 1, int(token_idx), feature_idx))

    # Start search
    edge_search = EdgeSearch(model, ablator, num_samples)
    circuit_edges: frozenset[Edge] = edge_search.search(tokens, upstream_nodes, downstream_nodes, threshold)
