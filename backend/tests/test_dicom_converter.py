from io import BytesIO

import pytest

from app.ml.dicom_converter import DicomConversionError, convert_dicom_series


class UploadedFile(BytesIO):
    def __init__(self, filename: str, content: bytes = b""):
        super().__init__(content)
        self.filename = filename


def test_rejects_upload_without_dcm_files():
    with pytest.raises(DicomConversionError, match="No valid DICOM files"):
        convert_dicom_series([UploadedFile("photo.png")])


def test_rejects_corrupt_dcm_file():
    with pytest.raises(DicomConversionError, match="DICOM conversion failed"):
        convert_dicom_series([UploadedFile("scan.dcm", b"not a dicom file")])
