"""Run segmentation on a NIfTI volume with the nnU-Net model (slice by slice, 2D)."""

import logging
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
    def __init__(self, model_dir: Path):
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
        model = self._model
        image = read_nifti(nifti_stream)
        volume = image.get_fdata().astype(np.float32)
        normalized = normalize_ct(volume, model.intensity_properties)
        patch_size = model.config_2d["patch_size"]

        logger.info("Running nnU-Net on volume %s (%d slices)", volume.shape, volume.shape[-1])
        with torch.no_grad():
            mask_slices = [
                self._predict_slice(normalized[:, :, i], patch_size)
                for i in range(normalized.shape[-1])
            ]
        mask = np.stack(mask_slices, axis=-1).astype(np.int16)
        logger.info("Segmentation complete: %d voxels segmented", int(np.sum(mask > 0)))

        return calculate_metrics(mask), write_nifti(mask, image.affine)

    def _predict_slice(self, slice_2d: np.ndarray, patch_size) -> np.ndarray:
        model = self._model
        resized = resize_2d(slice_2d, patch_size)
        tensor = torch.from_numpy(resized).unsqueeze(0).unsqueeze(0).to(model.device)
        output = model.network(tensor)

        if output.shape[1] == 1:
            prediction = (torch.sigmoid(output) > 0.5).long()
        else:
            prediction = torch.argmax(output, dim=1)

        prediction = prediction.squeeze().cpu().numpy().astype(np.float32)
        restored = resize_2d(prediction, slice_2d.shape)
        return (restored > 0.5).astype(np.int16)
