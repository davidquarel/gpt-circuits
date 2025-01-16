from dataclasses import dataclass, field
from enum import Enum

from config import Config, map_options
from config.gpt.models import GPTConfig, gpt_options


class SAEVariant(str, Enum):
    STANDARD = "standard"
    STANDARD_V2 = "standard_v2"
    GATED = "gated"
    GATED_V2 = "gated_v2"


@dataclass
class SAEConfig(Config):
    gpt_config: GPTConfig = field(default_factory=GPTConfig)
    n_features: tuple = ()  # Number of features in each layer
    sae_variant: SAEVariant = SAEVariant.GATED_V2

    @property
    def block_size(self) -> int:
        return self.gpt_config.block_size

    @staticmethod
    def dict_factory(fields: list) -> dict:
        """
        Only export n_features and sae_variant.
        """
        whitelisted_fields = ("n_features", "sae_variant")
        return {k: v for (k, v) in fields if k in whitelisted_fields}


# SAE configuration options
sae_options: dict[str, SAEConfig] = map_options(
    SAEConfig(
        name="standardx8.shakespeare_64x4",
        gpt_config=gpt_options["ascii_64x4"],
        n_features=tuple(64 * n for n in (8, 8, 8, 8, 8)),
        sae_variant=SAEVariant.STANDARD,
    ),
    SAEConfig(
        name="standard_v2x8.shakespeare_64x4",
        gpt_config=gpt_options["ascii_64x4"],
        n_features=tuple(64 * n for n in (8, 8, 8, 8, 8)),
        sae_variant=SAEVariant.STANDARD_V2,
    ),
    SAEConfig(
        name="gated_v2x8.shakespeare_64x4",
        gpt_config=gpt_options["ascii_64x4"],
        n_features=tuple(64 * n for n in (8, 8, 8, 8, 8)),
        sae_variant=SAEVariant.GATED_V2,
    ),
    SAEConfig(
        name="gated_v2x32.shakespeare_64x4",
        gpt_config=gpt_options["ascii_64x4"],
        n_features=tuple(64 * n for n in (32, 32, 32, 32, 32)),
        sae_variant=SAEVariant.GATED_V2,
    ),
)
