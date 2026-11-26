"""Read and write gzip-compressed NIfTI (`.nii.gz`) images in memory.

Files written by earlier versions of the app were uncompressed despite their `.nii.gz`
name; `read_nifti` accepts both, and `ensure_gzipped` fixes them on download.
"""

import gzip
from io import BytesIO

import nibabel as nib
import numpy as np

_GZIP_MAGIC = b"\x1f\x8b"


def is_gzipped(data: bytes) -> bool:
    return data[:2] == _GZIP_MAGIC


def ensure_gzipped(data: bytes) -> bytes:
    return data if is_gzipped(data) else gzip.compress(data, compresslevel=6)


def read_nifti(stream: BytesIO) -> nib.Nifti1Image:
    data = stream.getvalue()
    if is_gzipped(data):
        data = gzip.decompress(data)
    return nib.Nifti1Image.from_bytes(data)


def write_nifti(data: np.ndarray, affine: np.ndarray) -> BytesIO:
    raw = nib.Nifti1Image(data, affine).to_bytes()
    return BytesIO(gzip.compress(raw, compresslevel=6))
