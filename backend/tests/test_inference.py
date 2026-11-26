from pathlib import Path

import numpy as np
import pytest
import torch

from app.ml.inference import Segmenter
from app.ml.metrics import calculate_metrics
from app.ml.model_loader import NnUnetModel
from app.ml.nifti_io import read_nifti, write_nifti

INTENSITY = {"percentile_00_5": -340, "percentile_99_5": 529, "mean": -17, "std": 148}
BACKGROUND_HU, BRIGHT_HU = -300, 300   # normalise to about -1.9 and +2.1


class PixelwiseNetwork(torch.nn.Module):
    """Stub 2-class network: a pixel is foreground when its normalised value is positive.

    Being pixel-wise, it is unaffected by patch position or mirroring, so any change in
    the output mask comes from the pipeline (orientation, resampling, stitching)."""

    def __init__(self):
        super().__init__()
        self.calls = 0
        self.input_shapes = []

    def forward(self, x):
        self.calls += 1
        self.input_shapes.append(tuple(x.shape))
        foreground = 5.0 * x[:, 0]
        return torch.stack([torch.zeros_like(foreground), foreground], dim=1)


class FailingNetwork(torch.nn.Module):
    def forward(self, x):
        raise RuntimeError("boom")


def make_segmenter(network, **kwargs) -> Segmenter:
    segmenter = Segmenter(Path("does-not-exist"), **kwargs)
    segmenter._model = NnUnetModel(
        network=network,
        plans={
            "configurations": {"2d": {"patch_size": [56, 128], "spacing": [0.4, 0.4]}},
            "foreground_intensity_properties_per_channel": {"0": INTENSITY},
        },
        dataset={"labels": {"background": 0, "tumor": 1}},
        device=torch.device("cpu"),
        mirroring_axes=(0, 1),
    )
    return segmenter


def scan_with_bright_block(shape, spacing, block):
    """NIfTI (x, y, z) volume with a bright box at `block` = (x slice, y slice)."""
    volume = np.full(shape, BACKGROUND_HU, dtype=np.float32)
    volume[block[0], block[1], :] = BRIGHT_HU
    return write_nifti(volume, np.diag([*spacing, 1.0])), volume


def segment(segmenter, stream):
    metrics, mask_stream = segmenter.segment(stream)
    return metrics, read_nifti(mask_stream).get_fdata()


# --- orientation -----------------------------------------------------------

def test_slices_enter_the_model_in_nnunet_orientation():
    # A training-like crop: 119 voxels along x, 55 along y, at 0.4 mm.
    # nnU-Net sees it as a (y=55, x=119) image, which fits in ONE 56x128 patch.
    # With x and y swapped it would need 4 patches per slice.
    network = PixelwiseNetwork()
    stream, _ = scan_with_bright_block((119, 55, 3), (0.4, 0.4, 0.4), (slice(0, 1), slice(0, 1)))
    segment(make_segmenter(network), stream)
    assert network.calls == 3                       # one patch per slice
    assert network.input_shapes[0] == (1, 1, 56, 128)


def test_mask_is_returned_in_the_scan_orientation():
    block = (slice(10, 30), slice(5, 20))           # x 10-29, y 5-19
    stream, volume = scan_with_bright_block((60, 40, 2), (0.4, 0.4, 2.0), block)
    metrics, mask = segment(make_segmenter(PixelwiseNetwork()), stream)

    expected = (volume == BRIGHT_HU).astype(float)
    assert mask.shape == volume.shape
    assert np.array_equal(mask, expected)
    assert metrics["voxel_count"] == 20 * 15 * 2
    assert metrics["volume_mm3"] == pytest.approx(600 * 0.4 * 0.4 * 2.0)
    assert metrics["confidence"] > 0.99


# --- resampling and sliding window ----------------------------------------

def test_slices_are_resampled_to_the_training_spacing():
    # 0.8 mm pixels -> resampled to 0.4 mm, i.e. twice the size, before prediction.
    network = PixelwiseNetwork()
    block = (slice(20, 40), slice(20, 40))
    stream, volume = scan_with_bright_block((60, 60, 1), (0.8, 0.8, 1.0), block)
    _, mask = segment(make_segmenter(network), stream)

    # Resampled slice is 120x120: 4 windows along y (56) x 1 along x (128, padded).
    assert network.calls == 4
    assert mask.shape == volume.shape
    assert mask[22:38, 22:38, 0].all()              # block interior found
    assert not mask[:15, :, 0].any() and not mask[45:, :, 0].any()


# --- confidence ------------------------------------------------------------


def test_confidence_is_the_mean_probability_of_segmented_voxels():
    mask = np.zeros((4, 4, 1), dtype=np.int16)
    mask[:2] = 1
    for probability in (0.55, 0.99):
        metrics = calculate_metrics(mask, np.full(mask.shape, probability), 1.0)
        assert metrics["confidence"] == pytest.approx(probability)


# --- no silent fake results -----------------------------------------------

def test_inference_errors_are_raised_not_replaced_by_a_fake_mask():
    stream, _ = scan_with_bright_block((60, 40, 1), (0.4, 0.4, 1.0), (slice(0, 1), slice(0, 1)))
    with pytest.raises(RuntimeError, match="boom"):
        make_segmenter(FailingNetwork()).segment(stream)


def test_missing_model_is_fatal_unless_simulation_is_allowed():
    with pytest.raises(RuntimeError, match="ALLOW_SIMULATION"):
        Segmenter(Path("does-not-exist"), allow_simulation=False)
