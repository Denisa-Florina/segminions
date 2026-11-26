"""Sliding-window inference over a 2D image, following nnU-Net's scheme.

The image is covered by overlapping patches of the training patch size (50% overlap).
Each patch prediction is weighted by a Gaussian that favours the patch centre, where
the network has the most context, and the weighted logits are averaged.
"""

import itertools
import math
from collections.abc import Callable

import numpy as np
from scipy.ndimage import gaussian_filter

STEP_SIZE = 0.5          # fraction of the patch size between two windows
GAUSSIAN_SIGMA_SCALE = 1 / 8


def compute_steps(image_size: int, patch_size: int, step_size: float = STEP_SIZE) -> list[int]:
    """Start offsets of the windows along one axis (same formula as nnU-Net)."""
    if image_size <= patch_size:
        return [0]
    target_step = patch_size * step_size
    num_steps = math.ceil((image_size - patch_size) / target_step) + 1
    actual_step = (image_size - patch_size) / (num_steps - 1)
    return [round(actual_step * i) for i in range(num_steps)]


def count_patches(image_shape, patch_size) -> int:
    padded = [max(s, p) for s, p in zip(image_shape, patch_size, strict=True)]
    return math.prod(len(compute_steps(s, p)) for s, p in zip(padded, patch_size, strict=True))


def gaussian_importance_map(patch_size) -> np.ndarray:
    impulse = np.zeros(patch_size, dtype=np.float32)
    impulse[tuple(p // 2 for p in patch_size)] = 1
    sigmas = [p * GAUSSIAN_SIGMA_SCALE for p in patch_size]
    gaussian = gaussian_filter(impulse, sigmas, mode="constant", cval=0)
    gaussian /= gaussian.max()
    # Avoid zero weights at the borders, which would leave pixels without a prediction.
    gaussian[gaussian == 0] = gaussian[gaussian != 0].min()
    return gaussian


def predict_sliding_window(
    image: np.ndarray,
    patch_size,
    predict_patches: Callable[[np.ndarray], np.ndarray],
    batch_size: int = 1,
) -> np.ndarray:
    """Return (classes, H, W) logits for a 2D `image`.

    `predict_patches` maps a (N, H_patch, W_patch) array to (N, classes, H_patch, W_patch).
    """
    patch_size = tuple(int(p) for p in patch_size)
    padded, crop = _pad_to_patch_size(image, patch_size)
    gaussian = gaussian_importance_map(patch_size)

    windows = [
        (slice(y, y + patch_size[0]), slice(x, x + patch_size[1]))
        for y, x in itertools.product(
            compute_steps(padded.shape[0], patch_size[0]),
            compute_steps(padded.shape[1], patch_size[1]),
        )
    ]

    logits_sum = None
    weight_sum = np.zeros(padded.shape, dtype=np.float32)
    for start in range(0, len(windows), batch_size):
        batch_windows = windows[start:start + batch_size]
        logits = predict_patches(np.stack([padded[w] for w in batch_windows]))
        if logits_sum is None:
            logits_sum = np.zeros((logits.shape[1], *padded.shape), dtype=np.float32)
        for window, patch_logits in zip(batch_windows, logits, strict=True):
            logits_sum[(slice(None), *window)] += patch_logits * gaussian
            weight_sum[window] += gaussian

    return (logits_sum / weight_sum)[(slice(None), *crop)]


def _pad_to_patch_size(image: np.ndarray, patch_size) -> tuple[np.ndarray, tuple[slice, ...]]:
    """Zero-pad (in normalised space) so each side is at least the patch size."""
    padding, crop = [], []
    for size, patch in zip(image.shape, patch_size, strict=True):
        total = max(0, patch - size)
        before = total // 2
        padding.append((before, total - before))
        crop.append(slice(before, before + size))
    return np.pad(image, padding, mode="constant", constant_values=0), tuple(crop)
