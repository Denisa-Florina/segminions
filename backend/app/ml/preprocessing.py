"""Image preprocessing that mirrors nnU-Net's 2D pipeline."""

import numpy as np
from scipy.ndimage import zoom


def normalize_ct(image: np.ndarray, intensity_properties: dict) -> np.ndarray:
    """Clip to the dataset's 0.5–99.5 percentiles and apply z-score normalisation."""
    clipped = np.clip(
        image,
        intensity_properties["percentile_00_5"],
        intensity_properties["percentile_99_5"],
    )
    return (clipped - intensity_properties["mean"]) / (intensity_properties["std"] + 1e-8)


def resize_2d(image: np.ndarray, target_shape, order: int = 1) -> np.ndarray:
    """Resize a 2D array (or the last two axes of a 3D array) to `target_shape`.

    mode="nearest" extends the edges instead of padding with zeros, which would
    otherwise blend the border pixels with 0 and drop the last row/column of a mask.
    """
    target_shape = tuple(int(s) for s in target_shape)
    if image.shape[-2:] == target_shape:
        return image
    factors = [target_shape[0] / image.shape[-2], target_shape[1] / image.shape[-1]]
    if image.ndim == 3:
        factors = [1.0, *factors]
    return zoom(image, factors, order=order, mode="nearest")


def resampled_shape(shape, spacing, target_spacing) -> tuple[int, int]:
    """Shape of a 2D slice after resampling from `spacing` to `target_spacing` (mm)."""
    return tuple(
        max(1, round(size * current / target))
        for size, current, target in zip(shape, spacing, target_spacing, strict=True)
    )
