"""Fallback used when the nnU-Net model is unavailable: produces a placeholder mask.

The result is clearly marked as simulated and reports no confidence; it must never
be presented as a model prediction.
"""

import logging
from io import BytesIO

import numpy as np

from app.ml.nifti_io import read_nifti, write_nifti

logger = logging.getLogger(__name__)


def simulate_metrics() -> dict:
    return {"confidence": 0.0, "simulated": True}


def simulate_segmentation(nifti_stream: BytesIO) -> tuple[dict, BytesIO]:
    """Return placeholder metrics and a box-shaped mask in the centre of the volume."""
    logger.warning("Using SIMULATED segmentation, not the AI model")
    try:
        image = read_nifti(nifti_stream)
        shape = image.shape
        mask = np.zeros(shape, dtype=np.int16)
        center = np.array(shape) // 2
        half_size = np.maximum(np.array(shape) // 5, 5)
        box = tuple(
            slice(max(0, c - h), min(dim, c + h))
            for c, h, dim in zip(center, half_size, shape, strict=True)
        )
        mask[box] = 1
        return simulate_metrics(), write_nifti(mask, image.affine)
    except Exception:
        logger.exception("Simulation failed, returning an empty mask")
        return simulate_metrics(), write_nifti(np.zeros((1, 1, 1), dtype=np.int16), np.eye(4))
