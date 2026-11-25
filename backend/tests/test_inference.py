from pathlib import Path

import numpy as np
import pytest
import torch

from app.ml.inference import Segmenter
from app.ml.metrics import calculate_metrics
from app.ml.model_loader import NnUnetModel
from app.ml.nifti_io import read_nifti, write_nifti

FOREGROUND_LOGIT = 4.0   # softmax([0, 4])[1] = sigmoid(4) ≈ 0.982
EXPECTED_PROBABILITY = float(torch.sigmoid(torch.tensor(FOREGROUND_LOGIT)))


class LeftHalfNetwork(torch.nn.Module):
    """Stub 2-class network: confident foreground in the left half of each slice."""

    def __init__(self, empty: bool = False):
        super().__init__()
        self.empty = empty

    def forward(self, x):
        batch, _, height, width = x.shape
        foreground = torch.full((batch, height, width), -FOREGROUND_LOGIT)
        if not self.empty:
            foreground[:, :, : width // 2] = FOREGROUND_LOGIT
        background = torch.zeros_like(foreground)
        return torch.stack([background, foreground], dim=1)


def make_segmenter(network: torch.nn.Module) -> Segmenter:
    segmenter = Segmenter(Path("does-not-exist"))
    segmenter._model = NnUnetModel(
        network=network,
        plans={
            "configurations": {"2d": {"patch_size": [56, 128]}},
            "foreground_intensity_properties_per_channel": {"0": {
                "percentile_00_5": -340, "percentile_99_5": 529, "mean": -17, "std": 148,
            }},
        },
        dataset={"labels": {"background": 0, "tumor": 1}},
        device=torch.device("cpu"),
    )
    return segmenter


@pytest.fixture
def scan():
    volume = np.zeros((40, 60, 5), dtype=np.float32)
    return write_nifti(volume, np.diag([0.5, 0.5, 2.0, 1.0]))   # voxel = 0.5 mm³


def test_confidence_is_the_mean_probability_of_segmented_voxels(scan):
    metrics, mask_stream = make_segmenter(LeftHalfNetwork()).segment(scan)
    mask = read_nifti(mask_stream).get_fdata()

    assert mask.shape == (40, 60, 5)
    assert mask[:, :28, :].all() and not mask[:, 32:, :].any()   # left half segmented
    assert metrics["confidence"] == pytest.approx(EXPECTED_PROBABILITY, abs=0.02)
    assert metrics["voxel_count"] == int(mask.sum())
    assert metrics["volume_mm3"] == pytest.approx(metrics["voxel_count"] * 0.5)
    assert "simulated" not in metrics


def test_empty_prediction_reports_confidence_that_nothing_is_there(scan):
    metrics, _ = make_segmenter(LeftHalfNetwork(empty=True)).segment(scan)
    assert metrics["voxel_count"] == 0
    assert metrics["volume_mm3"] == 0
    assert metrics["confidence"] == pytest.approx(EXPECTED_PROBABILITY, abs=0.001)


def test_confidence_is_not_constant():
    mask = np.zeros((4, 4, 1), dtype=np.int16)
    mask[:2] = 1
    unsure = np.full(mask.shape, 0.55)
    sure = np.full(mask.shape, 0.99)
    assert calculate_metrics(mask, unsure, 1.0)["confidence"] == pytest.approx(0.55)
    assert calculate_metrics(mask, sure, 1.0)["confidence"] == pytest.approx(0.99)


def test_missing_model_falls_back_to_clearly_marked_simulation(scan):
    metrics, _ = Segmenter(Path("does-not-exist")).segment(scan)
    assert metrics == {"confidence": 0.0, "simulated": True}
