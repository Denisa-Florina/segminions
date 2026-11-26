"""Load the trained nnU-Net 2D network and its configuration files."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import torch

logger = logging.getLogger(__name__)

CHECKPOINT_FILE = "checkpoint_final.pth"
PLANS_FILE = "plans.json"
DATASET_FILE = "dataset.json"


@dataclass
class NnUnetModel:
    network: torch.nn.Module
    plans: dict
    dataset: dict
    device: torch.device
    mirroring_axes: tuple[int, ...] = ()

    @property
    def config_2d(self) -> dict:
        return self.plans["configurations"]["2d"]

    @property
    def intensity_properties(self) -> dict:
        return self.plans["foreground_intensity_properties_per_channel"]["0"]

    @property
    def patch_size(self) -> tuple[int, int]:
        return tuple(self.config_2d["patch_size"])

    @property
    def target_spacing(self) -> tuple[float, float]:
        return tuple(self.config_2d["spacing"])


def load_nnunet_model(model_dir: Path) -> NnUnetModel | None:
    """Return the loaded model, or None if the files are missing or invalid."""
    missing = [name for name in (CHECKPOINT_FILE, PLANS_FILE, DATASET_FILE)
               if not (model_dir / name).exists()]
    if missing:
        logger.warning("Model files missing in %s: %s", model_dir, ", ".join(missing))
        return None

    try:
        plans = json.loads((model_dir / PLANS_FILE).read_text())
        dataset = json.loads((model_dir / DATASET_FILE).read_text())
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        network = _build_network(plans["configurations"]["2d"], num_classes=len(dataset["labels"]))
        state_dict, mirroring_axes = _load_checkpoint(model_dir / CHECKPOINT_FILE, device)
        network.load_state_dict(state_dict)
        network.eval()
        network.to(device)
    except Exception:
        logger.exception("Failed to load nnU-Net model from %s", model_dir)
        return None

    logger.info("nnU-Net model loaded on %s (dataset %s, labels %s)",
                device, plans["dataset_name"], dataset["labels"])
    return NnUnetModel(
        network=network, plans=plans, dataset=dataset, device=device,
        mirroring_axes=mirroring_axes,
    )


def _build_network(config: dict, num_classes: int) -> torch.nn.Module:
    from dynamic_network_architectures.architectures.unet import PlainConvUNet

    arch = config["architecture"]["arch_kwargs"]
    return PlainConvUNet(
        input_channels=1,
        n_stages=arch["n_stages"],
        features_per_stage=arch["features_per_stage"],
        conv_op=torch.nn.Conv2d,
        kernel_sizes=arch["kernel_sizes"],
        strides=arch["strides"],
        n_conv_per_stage=arch["n_conv_per_stage"],
        num_classes=num_classes,
        n_conv_per_stage_decoder=arch["n_conv_per_stage_decoder"],
        conv_bias=arch["conv_bias"],
        norm_op=torch.nn.InstanceNorm2d,
        norm_op_kwargs=arch["norm_op_kwargs"],
        dropout_op=None,
        nonlin=torch.nn.LeakyReLU,
        nonlin_kwargs=arch["nonlin_kwargs"],
        deep_supervision=False,
    )


def _load_checkpoint(checkpoint_path: Path, device: torch.device) -> tuple[dict, tuple]:
    """Return (network weights, axes along which test-time mirroring is allowed)."""
    # weights_only=False is required for nnU-Net checkpoints; the file is our own.
    # mmap=True reads tensors from disk on demand, so the training-only parts of the
    # checkpoint (optimizer state, ~half the file) are never loaded into memory.
    checkpoint = torch.load(
        checkpoint_path, map_location=device, weights_only=False, mmap=True
    )
    if not isinstance(checkpoint, dict):
        return checkpoint, ()
    mirroring_axes = tuple(checkpoint.get("inference_allowed_mirroring_axes") or ())
    for key in ("network_weights", "state_dict"):
        if key in checkpoint:
            return checkpoint[key], mirroring_axes
    return checkpoint, mirroring_axes
