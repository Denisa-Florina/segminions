import { MASK_COLOR, bestSlice, maskVoxelsPerSlice, renderSlice } from './sliceRendering';

// 2 x 1 pixels per slice, 3 slices.
const scan = { dims: [2, 1, 3], data: Float32Array.from([-1000, 1000, 0, 0, 40, 40]), slope: 1, intercept: 0 };
const mask = { dims: [2, 1, 3], data: Int16Array.from([0, 0, 1, 0, 1, 1]) };
const ctWindow = { level: 0, width: 2000 }; // -1000 HU -> black, +1000 HU -> white

describe('maskVoxelsPerSlice / bestSlice', () => {
  it('counts mask voxels on each slice and picks the fullest one', () => {
    const counts = maskVoxelsPerSlice(mask);
    expect(counts).toEqual([0, 1, 2]);
    expect(bestSlice(counts)).toBe(2);
  });

  it('falls back to the middle slice when the mask is empty', () => {
    expect(bestSlice([0, 0, 0, 0, 0])).toBe(2);
  });
});

describe('renderSlice', () => {
  it('maps Hounsfield units through the window to grey levels', () => {
    const pixels = new Uint8ClampedArray(2 * 4);
    renderSlice(pixels, scan, mask, 0, ctWindow, 0.5);
    expect(Array.from(pixels)).toEqual([0, 0, 0, 255, 255, 255, 255, 255]);
  });

  it('blends mask voxels with the mask colour', () => {
    const pixels = new Uint8ClampedArray(2 * 4);
    renderSlice(pixels, scan, mask, 1, ctWindow, 1);
    // Fully opaque mask: first pixel is the mask colour, second stays grey (0 HU = 127.5).
    expect(Array.from(pixels.slice(0, 3))).toEqual(MASK_COLOR);
    expect(pixels[4]).toBe(128);
  });

  it('draws no mask when the opacity is 0', () => {
    const pixels = new Uint8ClampedArray(2 * 4);
    renderSlice(pixels, scan, mask, 1, ctWindow, 0);
    expect(pixels[0]).toBe(pixels[1]);
  });

  it('applies the scan intensity scaling', () => {
    const scaled = { ...scan, data: Float32Array.from([0, 2000, 0, 0, 0, 0]), slope: 1, intercept: -1000 };
    const pixels = new Uint8ClampedArray(2 * 4);
    renderSlice(pixels, scaled, null, 0, ctWindow, 0);
    expect([pixels[0], pixels[4]]).toEqual([0, 255]);
  });
});
