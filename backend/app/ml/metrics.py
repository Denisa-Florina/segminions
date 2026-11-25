"""Summary metrics for a predicted segmentation."""

import numpy as np

ARTERY_MIN_VOXELS = 50


def calculate_metrics(
    mask: np.ndarray, foreground_probability: np.ndarray, voxel_volume_mm3: float
) -> dict:
    """Metrics for a binary mask and the model's per-voxel foreground probability.

    `confidence` is the mean predicted probability over the segmented voxels: how sure
    the model is about what it marked. When nothing is segmented it is 1 minus the
    highest foreground probability: how sure the model is that nothing is there.
    These are raw softmax probabilities, not calibrated uncertainty estimates.
    """
    segmented = mask > 0
    voxel_count = int(segmented.sum())

    if voxel_count:
        confidence = float(foreground_probability[segmented].mean())
    else:
        confidence = 1.0 - float(foreground_probability.max())

    return {
        "confidence": round(confidence, 4),
        "voxel_count": voxel_count,
        "volume_mm3": round(voxel_count * voxel_volume_mm3, 1),
        "coverage": round(voxel_count / mask.size, 4),
        "artery_detected": voxel_count > ARTERY_MIN_VOXELS,
    }
