"""Summary metrics for a predicted segmentation mask."""

import numpy as np

ARTERY_MIN_VOXELS = 50


def calculate_metrics(mask: np.ndarray) -> dict:
    voxel_count = int(np.sum(mask > 0))
    total_voxels = int(np.prod(mask.shape))
    coverage = voxel_count / total_voxels if total_voxels else 0.0

    # Placeholder confidence carried over from the original implementation;
    # to be replaced by the mean softmax probability over predicted foreground.
    if voxel_count > 0:
        confidence = 0.6
    else:
        confidence = round(0.3 + np.random.random() * 0.15, 2)

    return {
        "confidence": round(float(confidence), 2),
        "voxel_count": voxel_count,
        "coverage": round(float(coverage), 4),
        "artery_detected": voxel_count > ARTERY_MIN_VOXELS,
    }
