import numpy as np
import pytest

from app.ml.sliding_window import (
    compute_steps,
    count_patches,
    gaussian_importance_map,
    predict_sliding_window,
)


@pytest.mark.parametrize("image, patch, expected", [
    (56, 56, [0]),              # exactly one patch
    (40, 56, [0]),              # smaller than the patch: padded, one patch
    (100, 56, [0, 22, 44]),     # 50% overlap, evenly spread to reach the end
    (120, 56, [0, 21, 43, 64]),
    (300, 128, [0, 57, 115, 172]),
])
def test_compute_steps_matches_nnunet(image, patch, expected):
    steps = compute_steps(image, patch)
    assert steps == expected
    assert steps[-1] + patch >= image          # the last window reaches the edge


def test_count_patches():
    assert count_patches((55, 119), (56, 128)) == 1
    assert count_patches((120, 120), (56, 128)) == 4


def test_gaussian_is_highest_in_the_centre_and_never_zero():
    gaussian = gaussian_importance_map((56, 128))
    assert gaussian[28, 64] == gaussian.max() == 1
    assert gaussian.min() > 0


def identity_logits(patches):
    """(N, H, W) -> (N, 2, H, W): background 0, foreground = the input value."""
    return np.stack([np.zeros_like(patches), patches], axis=1)


@pytest.mark.parametrize("shape", [(56, 128), (40, 60), (150, 300)])
def test_stitched_prediction_reconstructs_the_image(shape):
    # With a pixel-wise "network", overlapping weighted windows must reproduce the
    # input exactly, whatever the image size (smaller, equal or larger than a patch).
    image = np.random.default_rng(0).normal(size=shape).astype(np.float32)
    logits = predict_sliding_window(image, (56, 128), identity_logits)
    assert logits.shape == (2, *shape)
    np.testing.assert_allclose(logits[1], image, atol=1e-5)
