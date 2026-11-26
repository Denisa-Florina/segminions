"""Run segmentation on a NIfTI volume with the nnU-Net 2D model.

Mirrors nnU-Net's 2D inference:
1. slices are taken along the volume's last axis (z) and transposed from NIfTI's
   (x, y) to nnU-Net's (y, x) order (nnU-Net reads images with SimpleITK, whose arrays
   are indexed z, y, x — the reverse of nibabel's x, y, z);
2. CT normalisation with the dataset's intensity statistics;
3. each slice is resampled to the training spacing (0.4 mm);
4. sliding-window prediction with Gaussian weighting (optionally with mirroring);
5. logits are resampled back to the original slice size, then converted to
   probabilities and thresholded.
"""

import itertools
import logging
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
import torch

from app.ml.errors import InvalidScanError
from app.ml.metrics import calculate_metrics
from app.ml.model_loader import NnUnetModel, load_nnunet_model
from app.ml.nifti_io import read_nifti, write_nifti
from app.ml.preprocessing import normalize_ct, resampled_shape, resize_2d
from app.ml.simulation import simulate_segmentation
from app.ml.sliding_window import count_patches, predict_sliding_window

logger = logging.getLogger(__name__)


@dataclass
class _ScanPlan:
    image: object               # nibabel image
    volume: np.ndarray          # (x, y, z)
    zooms: tuple[float, float, float]
    slice_shape: tuple[int, int]   # one slice in nnU-Net order (y, x)
    work_shape: tuple[int, int]    # the same slice at the training spacing


class Segmenter:
    def __init__(
        self,
        model_dir: Path,
        num_threads: int = 1,
        batch_size: int = 1,
        allow_simulation: bool = True,
        use_mirroring: bool = False,
        max_patches: int = 500,
    ):
        torch.set_num_threads(num_threads)
        self._batch_size = batch_size
        self._use_mirroring = use_mirroring
        self._max_patches = max_patches
        self._model: NnUnetModel | None = load_nnunet_model(model_dir)

        if self._model is None:
            if not allow_simulation:
                raise RuntimeError(
                    f"nnU-Net model could not be loaded from {model_dir}. "
                    "Set ALLOW_SIMULATION=true to run with placeholder masks instead."
                )
            logger.warning("AI model not available, segmentation will be SIMULATED")

    @property
    def is_model_loaded(self) -> bool:
        return self._model is not None

    def check_scan(self, nifti_stream: BytesIO) -> None:
        """Raise InvalidScanError if the scan cannot be segmented (checked up front, so
        the user gets the error immediately instead of after queueing)."""
        if self._model is not None:
            self._plan(nifti_stream)

    def segment(self, nifti_stream: BytesIO) -> tuple[dict, BytesIO]:
        """Return (metrics, mask as NIfTI stream). Inference errors are raised, never
        replaced by a placeholder mask."""
        if self._model is None:
            return simulate_segmentation(nifti_stream)
        return self._run_model(nifti_stream)

    # --- pipeline ----------------------------------------------------------

    def _plan(self, nifti_stream: BytesIO) -> _ScanPlan:
        image = read_nifti(nifti_stream)
        volume = self._as_3d(image.get_fdata(dtype=np.float32))
        zooms = tuple(float(z) for z in image.header.get_zooms()[:3])
        zooms += (1.0,) * (3 - len(zooms))

        # One 2D slice in nnU-Net order: (rows = y, columns = x).
        slice_shape = (volume.shape[1], volume.shape[0])
        slice_spacing = (zooms[1], zooms[0])
        work_shape = resampled_shape(slice_shape, slice_spacing, self._model.target_spacing)
        self._check_size(work_shape, volume.shape[2])
        return _ScanPlan(image, volume, zooms, slice_shape, work_shape)

    def _run_model(self, nifti_stream: BytesIO) -> tuple[dict, BytesIO]:
        started = time.perf_counter()
        model = self._model
        plan = self._plan(nifti_stream)
        image, volume, zooms = plan.image, plan.volume, plan.zooms
        slice_shape, work_shape = plan.slice_shape, plan.work_shape

        logger.info("Running nnU-Net on volume %s, spacing %s mm -> slices resampled to %s",
                    volume.shape, zooms, work_shape)
        normalized = normalize_ct(volume, model.intensity_properties)
        probability = np.empty(volume.shape, dtype=np.float32)
        for k in range(volume.shape[2]):
            slice_yx = resize_2d(normalized[:, :, k].T, work_shape, order=3)
            logits = predict_sliding_window(
                slice_yx, model.patch_size, self._predict_patches, self._batch_size
            )
            logits = resize_2d(logits, slice_shape, order=1)
            probability[:, :, k] = _foreground_probability(logits).T

        mask = (probability > 0.5).astype(np.int16)
        metrics = calculate_metrics(mask, probability, float(np.prod(zooms)))
        logger.info("Segmentation complete in %.1fs: %d voxels, confidence %.3f",
                    time.perf_counter() - started, metrics["voxel_count"], metrics["confidence"])
        return metrics, write_nifti(mask, image.affine)

    @staticmethod
    def _as_3d(volume: np.ndarray) -> np.ndarray:
        if volume.ndim == 2:
            return volume[:, :, np.newaxis]
        if volume.ndim != 3:
            raise InvalidScanError(f"Expected a 3D scan, got {volume.ndim} dimensions")
        return volume

    def _mirror_variants(self) -> list[tuple[int, ...]]:
        axes = self._model.mirroring_axes if self._use_mirroring else ()
        return [c for r in range(len(axes) + 1) for c in itertools.combinations(axes, r)]

    def _check_size(self, work_shape, num_slices: int) -> None:
        passes = (count_patches(work_shape, self._model.patch_size)
                  * num_slices * len(self._mirror_variants()))
        if passes > self._max_patches:
            raise InvalidScanError(
                f"Scan too large for this server: {passes} model passes needed, the limit "
                f"is {self._max_patches}. Upload fewer slices or a cropped region of interest."
            )

    def _predict_patches(self, patches: np.ndarray) -> np.ndarray:
        """(N, H, W) normalised patches -> (N, classes, H, W) logits, averaged over the
        allowed mirror flips when mirroring is enabled."""
        model = self._model
        inputs = torch.from_numpy(np.ascontiguousarray(patches)).unsqueeze(1).to(model.device)
        variants = self._mirror_variants()
        with torch.inference_mode():
            logits = None
            for axes in variants:
                dims = [axis + 2 for axis in axes]   # skip batch and channel dims
                flipped = torch.flip(inputs, dims) if dims else inputs
                output = model.network(flipped)
                output = torch.flip(output, dims) if dims else output
                logits = output if logits is None else logits + output
        return (logits / len(variants)).cpu().numpy()


def _foreground_probability(logits: np.ndarray) -> np.ndarray:
    """(classes, H, W) logits -> probability that a pixel is not background."""
    if logits.shape[0] == 1:
        return 1.0 / (1.0 + np.exp(-logits[0]))
    shifted = np.exp(logits - logits.max(axis=0, keepdims=True))
    return 1.0 - shifted[0] / shifted.sum(axis=0)
