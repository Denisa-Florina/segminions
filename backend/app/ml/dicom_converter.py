"""Convert a series of uploaded DICOM slices into a single NIfTI volume."""

import logging
from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pydicom

from app.ml.nifti_io import write_nifti

logger = logging.getLogger(__name__)


class DicomConversionError(Exception):
    pass


@dataclass
class NiftiScan:
    stream: BytesIO
    filename: str
    size: int


def convert_dicom_series(files) -> NiftiScan:
    """Convert uploaded `.dcm` files (objects with `.filename` and `.read()`) to NIfTI."""
    try:
        slices, filenames = _read_slices(files)
        volume = _stack_slices(slices)
        affine = _build_affine(slices[0])
    except DicomConversionError:
        raise
    except Exception as error:
        logger.exception("DICOM conversion failed")
        raise DicomConversionError(
            "DICOM conversion failed. Please ensure files are valid .dcm files."
        ) from error

    stream = write_nifti(volume, affine)
    size = len(stream.getbuffer())
    base_name = filenames[0].rsplit(".", 1)[0]
    filename = f"{base_name}_{len(slices)}slices.nii.gz"
    logger.info("Converted %d slice(s) to %s (%.2f KB)", len(slices), filename, size / 1024)
    return NiftiScan(stream=stream, filename=filename, size=size)


def _read_slices(files) -> tuple[list, list[str]]:
    slices, filenames = [], []
    for file in files:
        filename = getattr(file, "filename", None) or "scan.dcm"
        if not filename.lower().endswith(".dcm"):
            logger.warning("Skipping %s: not a .dcm file", filename)
            continue
        file.seek(0)
        slices.append(pydicom.dcmread(BytesIO(file.read())))
        filenames.append(filename)

    if not slices:
        raise DicomConversionError("No valid DICOM files found. Please upload .dcm files.")

    if len(slices) > 1:
        try:
            slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
        except (AttributeError, IndexError):
            logger.warning("Could not sort slices by ImagePositionPatient")
    return slices, filenames


def _stack_slices(slices) -> np.ndarray:
    if len(slices) == 1:
        volume = slices[0].pixel_array
        if volume.ndim == 2:
            volume = volume[np.newaxis, :, :]
    else:
        volume = np.stack([s.pixel_array for s in slices], axis=-1)
    return volume.astype(np.float32)


def _build_affine(reference_slice) -> np.ndarray:
    pixel_spacing = reference_slice.PixelSpacing
    slice_thickness = float(getattr(reference_slice, "SliceThickness", 1.0))
    affine = np.eye(4)
    affine[0, 0] = pixel_spacing[0]
    affine[1, 1] = pixel_spacing[1]
    affine[2, 2] = slice_thickness
    return affine
