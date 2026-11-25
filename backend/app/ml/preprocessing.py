"""Image preprocessing based on the nnU-Net plans."""

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


def resize_2d(image: np.ndarray, target_size) -> np.ndarray:
    """Bilinear resize of a 2D array to `target_size` = [height, width]."""
    factors = [target_size[0] / image.shape[0], target_size[1] / image.shape[1]]
    return zoom(image, factors, order=1)
