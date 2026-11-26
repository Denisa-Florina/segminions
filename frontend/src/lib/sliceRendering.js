/**
 * Turns one axial slice of a CT volume (and optionally its mask) into RGBA pixels.
 * Kept free of React and the DOM so it can be unit-tested.
 */

// CT windows in Hounsfield units: `level` is the centre grey, `width` the range shown.
export const WINDOWS = {
  bone: { label: 'Bone', level: 400, width: 1800 },
  softTissue: { label: 'Soft tissue', level: 40, width: 400 },
};

export const MASK_COLOR = [239, 68, 68]; // red-500

/** Number of mask voxels on each slice (z), used to jump to where the segmentation is. */
export function maskVoxelsPerSlice(mask) {
  const [nx, ny, nz] = mask.dims;
  const perSlice = nx * ny;
  const counts = new Array(nz).fill(0);
  for (let z = 0; z < nz; z++) {
    const offset = z * perSlice;
    let count = 0;
    for (let i = 0; i < perSlice; i++) {
      if (mask.data[offset + i] > 0) count++;
    }
    counts[z] = count;
  }
  return counts;
}

/** The slice with the most mask voxels, or the middle slice when the mask is empty. */
export function bestSlice(counts) {
  let best = -1;
  let bestCount = 0;
  counts.forEach((count, z) => {
    if (count > bestCount) {
      best = z;
      bestCount = count;
    }
  });
  return best >= 0 ? best : Math.floor(counts.length / 2);
}

/**
 * Fills `pixels` (RGBA, length nx * ny * 4) with slice `z`: the scan through the CT
 * window, with mask voxels blended in MASK_COLOR at `maskOpacity` (0 hides the mask).
 */
export function renderSlice(pixels, scan, mask, z, ctWindow, maskOpacity) {
  const [nx, ny] = scan.dims;
  const perSlice = nx * ny;
  const offset = z * perSlice;
  const low = ctWindow.level - ctWindow.width / 2;
  const { slope, intercept } = scan;
  const [r, g, b] = MASK_COLOR;

  for (let i = 0; i < perSlice; i++) {
    const hu = scan.data[offset + i] * slope + intercept;
    let grey = ((hu - low) / ctWindow.width) * 255;
    grey = grey < 0 ? 0 : grey > 255 ? 255 : grey;

    const p = i * 4;
    if (mask && maskOpacity > 0 && mask.data[offset + i] > 0) {
      pixels[p] = grey + (r - grey) * maskOpacity;
      pixels[p + 1] = grey + (g - grey) * maskOpacity;
      pixels[p + 2] = grey + (b - grey) * maskOpacity;
    } else {
      pixels[p] = grey;
      pixels[p + 1] = grey;
      pixels[p + 2] = grey;
    }
    pixels[p + 3] = 255;
  }
}
