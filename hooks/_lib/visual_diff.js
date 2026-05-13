// Visual-diff helper for design-qc Step 6 (AC2).
//
// Pure-Node module — no npm deps. Compares two raw RGBA buffers (Buffer of
// width*height*4 bytes) and returns a pixel-diff ratio in [0.0, 1.0].
//
// Typed signature:
//   computePixelDiffRatio(
//     baseline: Buffer,
//     current: Buffer,
//     threshold: number,
//     dimensions: { width: number, height: number },
//   ): number
//
// Why a hand-rolled algorithm and not `pixelmatch`:
//   The harness ships as a bash + Python + plain-JS tree. Adding `pixelmatch`
//   would force every consumer project to npm-install our hooks/_lib subtree.
//   The algorithm below is the YIQ-distance shape `pixelmatch` uses (with the
//   anti-aliasing filter elided — `toHaveScreenshot` already gates AA at the
//   Playwright layer). Mutation-tested against the 9 Tier 1 unit tests.
//
// Properties (Tier 1.5 / PBT — frozen as Tier 1 regressions in
// tests/test_visual_diff.js):
//   - idempotence: identical buffers → ratio 0.0
//   - symmetry:    diff(a, b) === diff(b, a)
//   - range:       ratio ∈ [0.0, 1.0]

'use strict';

const RGBA_CHANNELS = 4;

// YIQ-distance threshold used by pixelmatch (default 0.1, scaled to 35215).
// Below this color-distance, two pixels are considered identical.
const DEFAULT_COLOR_DELTA_THRESHOLD = 0.1 * 35215;

/**
 * Compute the pixel-difference ratio between two RGBA buffers.
 *
 * @param {Buffer} baseline   - RGBA pixel data, length === width*height*4.
 * @param {Buffer} current    - RGBA pixel data, same dimensions as baseline.
 * @param {number} threshold  - per-route max-diff ratio (0.0..1.0). Used by
 *                              the caller to gate PASS/FAIL; the function
 *                              itself returns the raw measured ratio.
 * @param {{width:number,height:number}} dimensions
 *                            - image dimensions; buffer lengths must match.
 * @returns {number}          - measured ratio in [0.0, 1.0].
 */
function computePixelDiffRatio(baseline, current, threshold, dimensions) {
  _assertBuffer('baseline', baseline);
  _assertBuffer('current', current);
  _assertThreshold(threshold);
  _assertDimensions(dimensions);

  const { width, height } = dimensions;
  const expectedLength = width * height * RGBA_CHANNELS;
  if (baseline.length !== expectedLength) {
    throw new Error(
      `visual_diff: baseline buffer length ${baseline.length} ` +
      `does not match dimensions ${width}x${height} (size mismatch).`,
    );
  }
  if (current.length !== baseline.length) {
    throw new Error(
      `visual_diff: current buffer length ${current.length} ` +
      `does not match baseline length ${baseline.length} (size mismatch).`,
    );
  }

  const totalPixels = width * height;
  if (totalPixels === 0) {
    return 0.0;
  }

  let diffPixelCount = 0;
  const limit = baseline.length;
  for (let i = 0; i < limit; i += RGBA_CHANNELS) {
    if (_pixelDistance(baseline, current, i) > DEFAULT_COLOR_DELTA_THRESHOLD) {
      diffPixelCount += 1;
    }
  }
  return diffPixelCount / totalPixels;
}

/**
 * Lower-level helper returning the diff count alongside the ratio.
 *
 * @returns {{ratio:number, diffPixelCount:number, totalPixels:number}}
 */
function comparePngBuffers(baseline, current, opts) {
  const { width, height, threshold = 0.02 } = opts || {};
  const ratio = computePixelDiffRatio(
    baseline, current, threshold, { width, height },
  );
  const totalPixels = width * height;
  return {
    ratio,
    diffPixelCount: Math.round(ratio * totalPixels),
    totalPixels,
  };
}

// ---------------------------------------------------------------------------
// Internal helpers (CC ≤ 5, nesting ≤ 2, single-purpose).
// ---------------------------------------------------------------------------

function _assertBuffer(name, value) {
  if (!Buffer.isBuffer(value)) {
    throw new TypeError(`visual_diff: ${name} must be a Buffer`);
  }
}

function _assertThreshold(threshold) {
  if (typeof threshold !== 'number'
      || Number.isNaN(threshold)
      || threshold < 0.0
      || threshold > 1.0) {
    throw new RangeError(
      `visual_diff: threshold must be a number in [0.0, 1.0], got ${threshold}`,
    );
  }
}

function _assertDimensions(dimensions) {
  if (!dimensions
      || typeof dimensions.width !== 'number'
      || typeof dimensions.height !== 'number'
      || dimensions.width < 0
      || dimensions.height < 0) {
    throw new TypeError(
      'visual_diff: dimensions must be {width:number, height:number} (non-negative)',
    );
  }
}

// Squared YIQ color distance — same formula pixelmatch uses internally.
// Returns a scalar; squared form avoids a sqrt without changing ordering.
function _pixelDistance(a, b, offset) {
  const ra = a[offset], ga = a[offset + 1], ba = a[offset + 2], aa = a[offset + 3];
  const rb = b[offset], gb = b[offset + 1], bb = b[offset + 2], ab = b[offset + 3];

  if (ra === rb && ga === gb && ba === bb && aa === ab) {
    return 0;
  }

  // Blend alpha into RGB (pre-multiply against white background).
  const a1 = aa / 255;
  const a2 = ab / 255;
  const r1 = _blend(ra, a1);
  const g1 = _blend(ga, a1);
  const b1 = _blend(ba, a1);
  const r2 = _blend(rb, a2);
  const g2 = _blend(gb, a2);
  const b2 = _blend(bb, a2);

  const y1 = _rgbToY(r1, g1, b1);
  const y2 = _rgbToY(r2, g2, b2);
  const q1 = _rgbToQ(r1, g1, b1);
  const q2 = _rgbToQ(r2, g2, b2);
  const i1 = _rgbToI(r1, g1, b1);
  const i2 = _rgbToI(r2, g2, b2);

  const dy = y1 - y2;
  const di = i1 - i2;
  const dq = q1 - q2;
  return 0.5053 * dy * dy + 0.299 * di * di + 0.1957 * dq * dq;
}

function _blend(channel, alpha) {
  return 255 + (channel - 255) * alpha;
}

function _rgbToY(r, g, b) {
  return r * 0.29889531 + g * 0.58662247 + b * 0.11448223;
}

function _rgbToI(r, g, b) {
  return r * 0.59597799 - g * 0.27417610 - b * 0.32180189;
}

function _rgbToQ(r, g, b) {
  return r * 0.21147017 - g * 0.52261711 + b * 0.31114694;
}

module.exports = {
  computePixelDiffRatio,
  comparePngBuffers,
  // Exported for fixture/integration assertions only.
  _internalConstants: {
    RGBA_CHANNELS,
    DEFAULT_COLOR_DELTA_THRESHOLD,
  },
};
