/**
 * Minimal NIfTI-1 reader for the files this app produces (scan and mask, `.nii.gz`).
 *
 * Only what the viewer needs is read from the 348-byte header: the dimensions, the voxel
 * spacing, the data type, where the voxels start and the intensity scaling.
 * Spec: https://nifti.nimh.nih.gov/pub/dist/src/niftilib/nifti1.h
 *
 * Voxels are stored with x varying fastest, then y, then z, so voxel (x, y, z) is at
 * index x + nx * (y + ny * z). The backend writes x = DICOM column, y = DICOM row and
 * z = slice, so drawing x horizontally and y vertically reproduces the DICOM view.
 */

const HEADER_SIZE = 348;

// NIfTI datatype code -> typed array that reads it.
const DATA_TYPES = {
  2: Uint8Array,
  4: Int16Array,
  8: Int32Array,
  16: Float32Array,
  64: Float64Array,
  256: Int8Array,
  512: Uint16Array,
  768: Uint32Array,
};

export function isGzipped(bytes) {
  return bytes[0] === 0x1f && bytes[1] === 0x8b;
}

/** Decompresses gzip data with the browser's built-in DecompressionStream. */
export async function gunzip(buffer) {
  const stream = new Blob([buffer]).stream().pipeThrough(new DecompressionStream('gzip'));
  return new Response(stream).arrayBuffer();
}

/** Parses an uncompressed NIfTI-1 file. Throws on anything the viewer cannot display. */
export function parseNifti(buffer) {
  if (buffer.byteLength < HEADER_SIZE) {
    throw new Error('File is too small to be a NIfTI image');
  }
  const view = new DataView(buffer);
  const littleEndian = view.getInt32(0, true) === HEADER_SIZE;
  if (!littleEndian) {
    // Big-endian files would need every voxel byte-swapped; the backend never writes them.
    throw new Error(
      view.getInt32(0, false) === HEADER_SIZE
        ? 'Big-endian NIfTI files are not supported'
        : 'Not a NIfTI-1 file'
    );
  }

  const ndim = view.getInt16(40, true);
  const [nx, ny, nz] = [1, 2, 3].map(i => (i <= ndim ? view.getInt16(40 + 2 * i, true) : 1));
  const [sx, sy, sz] = [1, 2, 3].map(i => Math.abs(view.getFloat32(76 + 4 * i, true)) || 1);
  const datatype = view.getInt16(70, true);
  const voxOffset = view.getFloat32(108, true);
  const slope = view.getFloat32(112, true);
  const intercept = view.getFloat32(116, true);

  const ArrayType = DATA_TYPES[datatype];
  if (!ArrayType) throw new Error(`Unsupported NIfTI data type ${datatype}`);

  const count = nx * ny * nz;
  const start = Math.max(voxOffset, HEADER_SIZE);
  const end = start + count * ArrayType.BYTES_PER_ELEMENT;
  if (end > buffer.byteLength) throw new Error('NIfTI file is truncated');

  // slice() copies the voxels into a new buffer, which is always correctly aligned for
  // the typed array (the header offset need not be a multiple of 8).
  const data = new ArrayType(buffer.slice(start, end));

  return {
    dims: [nx, ny, nz],
    spacing: [sx, sy, sz],
    data,
    // A slope of 0 means "no scaling" in the NIfTI spec.
    slope: slope && Number.isFinite(slope) ? slope : 1,
    intercept: Number.isFinite(intercept) ? intercept : 0,
  };
}

/** Reads a `.nii` or `.nii.gz` file from an ArrayBuffer. */
export async function readNifti(buffer) {
  const bytes = new Uint8Array(buffer, 0, Math.min(2, buffer.byteLength));
  return parseNifti(isGzipped(bytes) ? await gunzip(buffer) : buffer);
}
