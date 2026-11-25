"""Read and write NIfTI images from in-memory streams."""

from io import BytesIO

import nibabel as nib
import numpy as np


def read_nifti(stream: BytesIO) -> nib.Nifti1Image:
    stream.seek(0)
    holder = nib.FileHolder(fileobj=stream)
    return nib.Nifti1Image.from_file_map({"image": holder, "header": holder})


def write_nifti(data: np.ndarray, affine: np.ndarray) -> BytesIO:
    image = nib.Nifti1Image(data, affine)
    stream = BytesIO()
    image.to_file_map(image.make_file_map({"image": stream, "header": stream}))
    stream.seek(0)
    return stream
