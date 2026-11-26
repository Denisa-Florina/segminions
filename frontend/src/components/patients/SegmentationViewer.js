import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { ChevronLeft, ChevronRight, Eye, EyeOff } from 'lucide-react';
import patientService from '../../services/patientService';
import { readNifti } from '../../lib/nifti';
import { WINDOWS, bestSlice, maskVoxelsPerSlice, renderSlice } from '../../lib/sliceRendering';
import Spinner from '../common/Spinner';

/**
 * Axial slice viewer: the CT scan with the segmentation mask overlaid in red.
 * Both volumes are downloaded once and every slice is drawn in the browser, so moving
 * through slices needs no further requests.
 */
function SegmentationViewer({ patientId }) {
  const [volumes, setVolumes] = useState(null); // { scan, mask }
  const [error, setError] = useState('');
  const [slice, setSlice] = useState(0);
  const [windowKey, setWindowKey] = useState('bone');
  const [showMask, setShowMask] = useState(true);
  const [opacity, setOpacity] = useState(0.5);
  const canvasRef = useRef(null);

  // Load both volumes; leaving the page cancels the downloads.
  useEffect(() => {
    const controller = new AbortController();
    setVolumes(null);
    setError('');

    (async () => {
      try {
        const [scanBytes, maskBytes] = await Promise.all([
          patientService.getVolume(patientId, 'scan', controller.signal),
          patientService.getVolume(patientId, 'mask', controller.signal),
        ]);
        const [scan, mask] = await Promise.all([readNifti(scanBytes), readNifti(maskBytes)]);
        if (scan.dims.join() !== mask.dims.join()) {
          throw new Error('The scan and the mask have different dimensions');
        }
        if (controller.signal.aborted) return;
        setVolumes({ scan, mask });
      } catch (err) {
        if (!axios.isCancel(err) && !controller.signal.aborted) setError(err.message);
      }
    })();

    return () => controller.abort();
  }, [patientId]);

  const maskCounts = useMemo(() => (volumes ? maskVoxelsPerSlice(volumes.mask) : []), [volumes]);
  const slicesWithMask = useMemo(
    () => maskCounts.flatMap((count, z) => (count > 0 ? [z] : [])),
    [maskCounts]
  );

  // Open on the slice where most of the segmentation is.
  useEffect(() => {
    if (volumes) setSlice(bestSlice(maskCounts));
  }, [volumes, maskCounts]);

  // Redraw whenever the slice or a display setting changes.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!volumes || !canvas) return;
    const [nx, ny] = volumes.scan.dims;
    const context = canvas.getContext('2d');
    const image = context.createImageData(nx, ny);
    renderSlice(image.data, volumes.scan, volumes.mask, slice, WINDOWS[windowKey],
      showMask ? opacity : 0);
    context.putImageData(image, 0, 0);
  }, [volumes, slice, windowKey, showMask, opacity]);

  // Mouse wheel scrolls through slices. React registers wheel listeners as passive, so
  // preventDefault (to keep the page from scrolling) needs a native listener.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!volumes || !canvas) return undefined;
    const lastSlice = volumes.scan.dims[2] - 1;
    const onWheel = (event) => {
      event.preventDefault();
      const step = event.deltaY > 0 ? 1 : -1;
      setSlice(current => Math.min(lastSlice, Math.max(0, current + step)));
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, [volumes]);

  if (error) {
    return (
      <div className="bg-red-600/20 border border-red-500 rounded-lg p-4 text-sm text-red-300">
        Could not load the images: {error}
      </div>
    );
  }

  if (!volumes) {
    return (
      <div className="aspect-square max-w-[32rem] w-full mx-auto bg-gray-900 rounded-lg flex flex-col items-center justify-center gap-3">
        <Spinner className="w-8 h-8 border-4 border-blue-500" />
        <p className="text-sm text-gray-400">Loading scan and segmentation…</p>
      </div>
    );
  }

  const [nx, ny, nz] = volumes.scan.dims;
  const [sx, sy] = volumes.scan.spacing;
  const jumpToMask = (direction) => {
    const next = direction > 0
      ? slicesWithMask.find(z => z > slice)
      : [...slicesWithMask].reverse().find(z => z < slice);
    if (next !== undefined) setSlice(next);
  };

  return (
    <div className="space-y-4">
      <div className="bg-black rounded-lg overflow-hidden flex justify-center">
        <canvas
          ref={canvasRef}
          width={nx}
          height={ny}
          role="img"
          aria-label={`Axial slice ${slice + 1} of ${nz}`}
          // Physical aspect ratio, so non-square pixels are not stretched.
          style={{ aspectRatio: `${nx * sx} / ${ny * sy}` }}
          className="w-full max-w-[32rem] h-auto"
        />
      </div>

      <div>
        <div className="flex items-center justify-between text-sm mb-1">
          <label htmlFor="slice-slider" className="text-gray-400">
            Slice <span className="text-white font-medium">{slice + 1}</span> / {nz}
          </label>
          <span className="text-gray-400">
            {maskCounts[slice] > 0
              ? <span className="text-red-400">{maskCounts[slice]} voxels segmented</span>
              : 'No segmentation on this slice'}
          </span>
        </div>
        <input
          id="slice-slider"
          type="range"
          min={0}
          max={nz - 1}
          value={slice}
          onChange={(e) => setSlice(Number(e.target.value))}
          className="w-full accent-blue-500"
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <div className="inline-flex rounded-lg border border-gray-600 overflow-hidden" role="group" aria-label="CT window">
          {Object.entries(WINDOWS).map(([key, { label }]) => (
            <button
              key={key}
              type="button"
              aria-pressed={windowKey === key}
              onClick={() => setWindowKey(key)}
              className={`px-3 py-1.5 ${windowKey === key ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
            >
              {label}
            </button>
          ))}
        </div>

        <button
          type="button"
          aria-pressed={showMask}
          onClick={() => setShowMask(v => !v)}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-700 text-gray-300 hover:bg-gray-600"
        >
          {showMask ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          {showMask ? 'Hide mask' : 'Show mask'}
        </button>

        <label className="inline-flex items-center gap-2 text-gray-400">
          Opacity
          <input
            type="range"
            min={0.1}
            max={1}
            step={0.1}
            value={opacity}
            disabled={!showMask}
            onChange={(e) => setOpacity(Number(e.target.value))}
            className="w-24 accent-red-500"
          />
        </label>

        {slicesWithMask.length > 0 && (
          <div className="inline-flex items-center gap-1 ml-auto text-gray-400">
            <button
              type="button"
              aria-label="Previous slice with segmentation"
              onClick={() => jumpToMask(-1)}
              className="p-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-1">Segmentation on {slicesWithMask.length} slices</span>
            <button
              type="button"
              aria-label="Next slice with segmentation"
              onClick={() => jumpToMask(1)}
              className="p-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
      <p className="text-xs text-gray-500">Tip: scroll over the image to move through slices.</p>
    </div>
  );
}

export default SegmentationViewer;
