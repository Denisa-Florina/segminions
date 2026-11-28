from io import BytesIO

import nibabel as nib
import numpy as np
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.ml.dicom_converter import convert_dicom_series
from app.ml.nifti_io import read_nifti

ROWS, COLUMNS = 24, 32


class UploadedFile(BytesIO):
    def __init__(self, filename: str, content: bytes = b""):
        super().__init__(content)
        self.filename = filename


def make_dicom_slice(
    z: float,
    pixels: np.ndarray | None = None,
    slope: float = 1.0,
    intercept: float = 0.0,
    pixel_spacing=(0.8, 0.8),
    thickness: float = 2.5,
) -> UploadedFile:
    """A minimal CT slice at height `z`. `pixels` is (rows, columns) of stored values."""
    if pixels is None:
        pixels = np.zeros((ROWS, COLUMNS), dtype=np.uint16)
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    meta.MediaStorageSOPInstanceUID = generate_uid()

    ds = Dataset()
    ds.file_meta = meta
    ds.is_little_endian, ds.is_implicit_VR = True, False
    ds.Modality = "CT"
    ds.Rows, ds.Columns = pixels.shape
    ds.BitsAllocated = ds.BitsStored = 16
    ds.HighBit, ds.PixelRepresentation, ds.SamplesPerPixel = 15, 0, 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelSpacing, ds.SliceThickness = list(pixel_spacing), thickness
    ds.ImagePositionPatient = [0, 0, z]
    ds.RescaleSlope, ds.RescaleIntercept = slope, intercept
    ds.PixelData = pixels.astype(np.uint16).tobytes()

    buffer = BytesIO()
    ds.save_as(buffer, write_like_original=False)
    return UploadedFile(f"slice{z}.dcm", buffer.getvalue())


def convert(files):
    scan = convert_dicom_series(files)
    image = read_nifti(scan.stream)
    return scan, image.get_fdata(), image.header.get_zooms()


def test_stored_values_are_converted_to_hounsfield_units():
    stored = np.full((ROWS, COLUMNS), 1024, dtype=np.uint16)   # typical CT encoding
    _, volume, _ = convert([make_dicom_slice(0, stored, slope=1, intercept=-1024)])
    assert np.all(volume == 0)                                # 1024 * 1 - 1024 = 0 HU (water)


def test_volume_uses_nifti_axis_order():
    # Pixel value = column index, so the column axis is easy to recognise.
    stored = np.tile(np.arange(COLUMNS, dtype=np.uint16), (ROWS, 1))
    _, volume, _ = convert([make_dicom_slice(0, stored)])
    assert volume.shape == (COLUMNS, ROWS, 1)                 # (x, y, z)
    assert volume[:, 0, 0].tolist() == list(range(COLUMNS))   # axis 0 runs along columns


def test_spacing_comes_from_pixel_spacing_and_slice_positions():
    files = [make_dicom_slice(z, pixel_spacing=(0.5, 0.7), thickness=5.0) for z in (0, 2, 4)]
    _, _, zooms = convert(files)
    # x = column spacing, y = row spacing, z = distance between slices (not thickness).
    assert zooms == pytest.approx((0.7, 0.5, 2.0))


def test_converted_scan_is_a_real_nii_gz_that_opens_with_nibabel(tmp_path):
    scan = convert_dicom_series([make_dicom_slice(z) for z in (0, 2)])
    data = scan.stream.getvalue()
    assert data[:2] == b"\x1f\x8b"          # gzip magic number

    path = tmp_path / "scan.nii.gz"          # what a doctor does with a download
    path.write_bytes(data)
    assert nib.load(path).shape == (COLUMNS, ROWS, 2)
