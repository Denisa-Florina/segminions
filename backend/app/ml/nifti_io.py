"""Read and write gzip-compressed NIfTI (`.nii.gz`) images in memory."""

import gzip
from io import BytesIO

import nibabel as nib
import numpy as np


def read_nifti(stream: BytesIO) -> nib.Nifti1Image:
    return nib.Nifti1Image.from_bytes(gzip.decompress(stream.getvalue()))


def write_nifti(data: np.ndarray, affine: np.ndarray) -> BytesIO:
    raw = nib.Nifti1Image(data, affine).to_bytes()
    return BytesIO(gzip.compress(raw, compresslevel=6))
