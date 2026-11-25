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


def make_dicom_slice(z: int, value: int) -> UploadedFile:
    """A minimal CT slice at height `z` whose pixels all equal `value`."""
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    meta.MediaStorageSOPInstanceUID = generate_uid()

    ds = Dataset()
    ds.file_meta = meta
    ds.is_little_endian, ds.is_implicit_VR = True, False
    ds.Rows, ds.Columns = ROWS, COLUMNS
    ds.BitsAllocated = ds.BitsStored = 16
    ds.HighBit, ds.PixelRepresentation, ds.SamplesPerPixel = 15, 0, 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelSpacing, ds.SliceThickness = [0.8, 0.8], 2.5
    ds.ImagePositionPatient = [0, 0, z]
    ds.PixelData = np.full((ROWS, COLUMNS), value, dtype=np.uint16).tobytes()

    buffer = BytesIO()
    ds.save_as(buffer, write_like_original=False)
    return UploadedFile(f"slice{z}.dcm", buffer.getvalue())


def test_single_dicom_file_becomes_one_slice():
    scan = convert_dicom_series([make_dicom_slice(z=0, value=7)])
    volume = read_nifti(scan.stream).get_fdata()
    assert volume.shape == (ROWS, COLUMNS, 1)   # slices on the last axis


def test_multiple_files_are_sorted_by_position():
    files = [make_dicom_slice(z=z, value=z) for z in (3, 1, 2)]
    scan = convert_dicom_series(files)
    volume = read_nifti(scan.stream).get_fdata()
    assert volume.shape == (ROWS, COLUMNS, 3)
    assert volume[0, 0, :].tolist() == [1, 2, 3]
    assert scan.filename.endswith("_3slices.nii.gz")


def test_rejects_upload_without_dcm_files():
    with pytest.raises(DicomConversionError, match="No valid DICOM files"):
        convert_dicom_series([UploadedFile("photo.png")])


def test_rejects_corrupt_dcm_file():
    with pytest.raises(DicomConversionError, match="DICOM conversion failed"):
        convert_dicom_series([UploadedFile("scan.dcm", b"not a dicom file")])
