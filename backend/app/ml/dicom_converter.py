"""Convert a series of uploaded DICOM slices into a single NIfTI volume in Hounsfield units.

The volume follows the NIfTI voxel convention: axis 0 = columns (x), axis 1 = rows (y),
axis 2 = slices (z). This is the same layout as any `.nii.gz` file, so scans converted
here and scans saved by other tools are handled identically downstream.
"""

import logging
from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pydicom
from pydicom.pixel_data_handlers.util import apply_modality_lut

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
        affine = _build_affine(slices)
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
    logger.info("Converted %d slice(s) to NIfTI (%.2f KB)", len(slices), size / 1024)
    return NiftiScan(stream=stream, filename=filename, size=size)


def _read_slices(files) -> tuple[list, list[str]]:
    slices, filenames, skipped = [], [], 0
    for file in files:
        filename = getattr(file, "filename", None) or "scan.dcm"
        if not filename.lower().endswith(".dcm"):
            skipped += 1
            continue
        file.seek(0)
        slices.append(pydicom.dcmread(BytesIO(file.read())))
        filenames.append(filename)

    if skipped:
        logger.warning("Skipped %d uploaded file(s) without a .dcm extension", skipped)
    if not slices:
        raise DicomConversionError("No valid DICOM files found. Please upload .dcm files.")

    if len(slices) > 1:
        try:
            slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
        except (AttributeError, IndexError):
            logger.warning("Could not sort slices by ImagePositionPatient")
    return slices, filenames


def _to_hounsfield(dicom_slice) -> np.ndarray:
    """Stored pixel values -> HU using RescaleSlope / RescaleIntercept (modality LUT)."""
    return apply_modality_lut(dicom_slice.pixel_array, dicom_slice).astype(np.float32)


def _stack_slices(slices) -> np.ndarray:
    """Return a (columns, rows, slices) volume in HU."""
    # pixel_array is (rows, columns); transpose to NIfTI's (x, y).
    planes = [_to_hounsfield(s).T for s in slices]
    if any(plane.ndim != 2 for plane in planes):
        raise DicomConversionError("Multi-frame DICOM files are not supported.")
    return np.stack(planes, axis=-1)


def _slice_spacing(slices) -> float:
    """Distance between slice centres; falls back to SliceThickness for a single slice."""
    if len(slices) > 1:
        try:
            positions = [float(s.ImagePositionPatient[2]) for s in slices]
            spacing = float(np.median(np.abs(np.diff(positions))))
            if spacing > 0:
                return spacing
        except (AttributeError, IndexError):
            pass
    return float(getattr(slices[0], "SliceThickness", 1.0) or 1.0)


def _build_affine(slices) -> np.ndarray:
    # PixelSpacing is [row spacing (y), column spacing (x)].
    row_spacing, column_spacing = (float(v) for v in slices[0].PixelSpacing)
    return np.diag([column_spacing, row_spacing, _slice_spacing(slices), 1.0])
