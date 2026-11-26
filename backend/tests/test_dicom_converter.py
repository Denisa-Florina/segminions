from io import BytesIO

import numpy as np
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.ml.dicom_converter import DicomConversionError, convert_dicom_series
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


def test_single_dicom_file_becomes_one_slice():
    _, volume, zooms = convert([make_dicom_slice(0, thickness=3.0)])
    assert volume.shape == (COLUMNS, ROWS, 1)
    assert zooms[2] == pytest.approx(3.0)                     # thickness when no neighbour


def test_multiple_files_are_sorted_by_position():
    files = [make_dicom_slice(z, np.full((ROWS, COLUMNS), z, dtype=np.uint16)) for z in (3, 1, 2)]
    scan, volume, _ = convert(files)
    assert volume.shape == (COLUMNS, ROWS, 3)
    assert volume[0, 0, :].tolist() == [1, 2, 3]
    assert scan.filename.endswith("_3slices.nii.gz")


def test_rejects_upload_without_dcm_files():
    with pytest.raises(DicomConversionError, match="No valid DICOM files"):
        convert_dicom_series([UploadedFile("photo.png")])


def test_rejects_corrupt_dcm_file():
    with pytest.raises(DicomConversionError, match="DICOM conversion failed"):
        convert_dicom_series([UploadedFile("scan.dcm", b"not a dicom file")])
