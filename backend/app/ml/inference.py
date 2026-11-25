"""Run segmentation on a NIfTI volume with the nnU-Net 2D model."""

import logging
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import torch

from app.ml.metrics import calculate_metrics
from app.ml.model_loader import NnUnetModel, load_nnunet_model
from app.ml.nifti_io import read_nifti, write_nifti
from app.ml.preprocessing import normalize_ct, resize_2d
from app.ml.simulation import simulate_segmentation

logger = logging.getLogger(__name__)


class Segmenter:
    def __init__(self, model_dir: Path, num_threads: int = 1, batch_size: int = 1):
        torch.set_num_threads(num_threads)
        self._batch_size = batch_size
        self._model: NnUnetModel | None = load_nnunet_model(model_dir)
        if self._model is None:
            logger.warning("AI model not available, segmentation will be SIMULATED")

    @property
    def is_model_loaded(self) -> bool:
        return self._model is not None

    def segment(self, nifti_stream: BytesIO) -> tuple[dict, BytesIO]:
        """Return (metrics, mask as NIfTI stream) for the given scan."""
        if self._model is None:
            return simulate_segmentation(nifti_stream)
        try:
            return self._run_model(nifti_stream)
        except Exception:
            logger.exception("nnU-Net inference failed")
            return simulate_segmentation(nifti_stream)

    def _run_model(self, nifti_stream: BytesIO) -> tuple[dict, BytesIO]:
        started = time.perf_counter()
        image = read_nifti(nifti_stream)
        volume = image.get_fdata().astype(np.float32)
        normalized = normalize_ct(volume, self._model.intensity_properties)
        slice_shape, num_slices = volume.shape[:2], volume.shape[-1]

        logger.info("Running nnU-Net on volume %s (%d slices)", volume.shape, num_slices)
        patch_size = self._model.config_2d["patch_size"]
        inputs = np.stack(
            [resize_2d(normalized[:, :, i], patch_size) for i in range(num_slices)]
        ).astype(np.float32)

        # Resample probabilities (not labels) back to the original size, then threshold.
        probability = np.stack(
            [np.clip(resize_2d(p, slice_shape), 0.0, 1.0) for p in self._predict(inputs)],
            axis=-1,
        )
        mask = (probability > 0.5).astype(np.int16)

        voxel_volume_mm3 = float(np.prod(image.header.get_zooms()[:3]))
        metrics = calculate_metrics(mask, probability, voxel_volume_mm3)
        logger.info("Segmentation complete in %.1fs: %d voxels, confidence %.3f",
                    time.perf_counter() - started, metrics["voxel_count"], metrics["confidence"])
        return metrics, write_nifti(mask, image.affine)

    def _predict(self, slices: np.ndarray) -> np.ndarray:
        """Foreground probability maps for (N, H, W) preprocessed slices."""
        model = self._model
        results = []
        with torch.inference_mode():
            for start in range(0, len(slices), self._batch_size):
                batch = torch.from_numpy(slices[start:start + self._batch_size])
                logits = model.network(batch.unsqueeze(1).to(model.device))
                if logits.shape[1] == 1:
                    foreground = torch.sigmoid(logits[:, 0])
                else:
                    # Any non-background class counts as foreground.
                    foreground = 1.0 - torch.softmax(logits, dim=1)[:, 0]
                results.append(foreground.cpu().numpy())
        return np.concatenate(results)
