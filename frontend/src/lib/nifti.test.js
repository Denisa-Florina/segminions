import { isGzipped, parseNifti } from './nifti';

/** Builds a minimal little-endian NIfTI-1 file with the given voxels (x fastest). */
function makeNifti({ dims, data, datatype = 16, spacing = [1, 1, 1], slope = NaN, intercept = 0 }) {
  const ArrayType = { 2: Uint8Array, 4: Int16Array, 16: Float32Array }[datatype];
  const voxOffset = 352;
  const buffer = new ArrayBuffer(voxOffset + data.length * ArrayType.BYTES_PER_ELEMENT);
  const view = new DataView(buffer);
  view.setInt32(0, 348, true);
  view.setInt16(40, 3, true);
  dims.forEach((d, i) => view.setInt16(42 + 2 * i, d, true));
  view.setInt16(70, datatype, true);
  spacing.forEach((s, i) => view.setFloat32(80 + 4 * i, s, true));
  view.setFloat32(108, voxOffset, true);
  view.setFloat32(112, slope, true);
  view.setFloat32(116, intercept, true);
  new ArrayType(buffer, voxOffset).set(data);
  return buffer;
}

describe('parseNifti', () => {
  it('reads dimensions, spacing and voxels', () => {
    const data = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    const image = parseNifti(makeNifti({ dims: [3, 2, 2], data, spacing: [0.5, 0.5, 2] }));

    expect(image.dims).toEqual([3, 2, 2]);
    expect(image.spacing).toEqual([0.5, 0.5, 2]);
    expect(Array.from(image.data)).toEqual(data);
    // Voxel (x=2, y=1, z=1) is at x + nx * (y + ny * z).
    expect(image.data[2 + 3 * (1 + 2 * 1)]).toBe(11);
  });

  it('treats a NaN or zero slope as no scaling', () => {
    expect(parseNifti(makeNifti({ dims: [1, 1, 1], data: [5] })).slope).toBe(1);
    expect(parseNifti(makeNifti({ dims: [1, 1, 1], data: [5], slope: 0 })).slope).toBe(1);
    const scaled = parseNifti(makeNifti({ dims: [1, 1, 1], data: [5], slope: 2, intercept: -1024 }));
    expect([scaled.slope, scaled.intercept]).toEqual([2, -1024]);
  });

  it('reads integer masks', () => {
    const image = parseNifti(makeNifti({ dims: [2, 1, 1], data: [0, 1], datatype: 4 }));
    expect(image.data).toBeInstanceOf(Int16Array);
    expect(Array.from(image.data)).toEqual([0, 1]);
  });

  it('rejects files that are not NIfTI or are truncated', () => {
    expect(() => parseNifti(new ArrayBuffer(10))).toThrow('too small');
    expect(() => parseNifti(new ArrayBuffer(400))).toThrow('Not a NIfTI-1 file');
    const full = makeNifti({ dims: [4, 4, 4], data: new Array(64).fill(0) });
    expect(() => parseNifti(full.slice(0, 400))).toThrow('truncated');
  });
});

describe('isGzipped', () => {
  it('recognises the gzip magic bytes', () => {
    expect(isGzipped(new Uint8Array([0x1f, 0x8b, 8]))).toBe(true);
    expect(isGzipped(new Uint8Array([0x5c, 0x01]))).toBe(false);
  });
});
