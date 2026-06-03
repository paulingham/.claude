"""Deterministic no-diff control tests for the vlm-critic pixel-diff pipeline.

Exercises both logical branches of the visual_diff.js ratio computation using
synthesized 1×1 RGBA PNGs — no PNG binaries checked in.

2am breadcrumbs:
- If `test_identical_pair_yields_ratio_zero` fails with a Node inflate error,
  check the filter-byte prefix in `synthesize_minimal_png` — each row must
  begin with `0x00` (None filter type). Row data = `bytes([0x00, r, g, b, a])`
  pre-compression. See `test_design_qc_visual_regression_e2e.py:251-279` for
  the expected IDAT format.
- If `test_differing_pair_yields_ratio_greater_than_zero` fails with ratio 0.0,
  check `DEFAULT_COLOR_DELTA_THRESHOLD` in `hooks/_lib/visual_diff.js` — pixel
  delta must exceed the anti-aliasing threshold; use maximum-contrast pairs
  (0,0,0 vs 255,255,255).
"""

import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
VISUAL_DIFF_JS = ROOT / "hooks" / "_lib" / "visual_diff.js"


def synthesize_minimal_png(r, g, b, a):
    """Return bytes of a valid 1×1 RGBA PNG synthesized entirely in Python.

    PNG structure (per RFC 2083):
      - 8-byte PNG signature
      - IHDR chunk: width=1, height=1, bit_depth=8, color_type=6 (RGBA),
        compression=0, filter=0, interlace=0
      - IDAT chunk: zlib.compress(bytes([0x00, r, g, b, a]))
        The 0x00 is the filter-type byte (None) for row 0.
      - IEND chunk
    Chunk encoding: struct.pack('>I', len(data)) + type_bytes + data
                    + struct.pack('>I', zlib.crc32(type_bytes + data) & 0xFFFFFFFF)
    """
    def _chunk(type_bytes, data):
        crc = zlib.crc32(type_bytes + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + type_bytes + data + struct.pack('>I', crc)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)
    ihdr = _chunk(b'IHDR', ihdr_data)
    idat_data = zlib.compress(bytes([0x00, r, g, b, a]), level=9)
    idat = _chunk(b'IDAT', idat_data)
    iend = _chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


def _compute_ratio(baseline_path, current_path, tmpdir):
    """Decode both PNGs and compute pixel-diff ratio via visual_diff.js.

    Copies the decode_and_diff.js string literal verbatim from
    test_design_qc_visual_regression_e2e.py:247-279 and runs it via Node.
    """
    # Source: test_design_qc_visual_regression_e2e.py:247-279
    decoder = Path(tmpdir) / "decode_and_diff.js"
    decoder.write_text(
        "'use strict';\n"
        "const vd = require(process.env.VD_PATH);\n"
        "const fs = require('fs'); const zlib = require('zlib');\n"
        "function decode(p){\n"
        "  const buf=fs.readFileSync(p);\n"
        "  let i=8, chunks=[], w=0, h=0;\n"
        "  while(i<buf.length){\n"
        "    const len=buf.readUInt32BE(i);\n"
        "    const type=buf.slice(i+4,i+8).toString('ascii');\n"
        "    const data=buf.slice(i+8,i+8+len);\n"
        "    if(type==='IHDR'){w=data.readUInt32BE(0);h=data.readUInt32BE(4);}\n"
        "    if(type==='IDAT'){chunks.push(data);}\n"
        "    i+=12+len;\n"
        "  }\n"
        "  const raw=zlib.inflateSync(Buffer.concat(chunks));\n"
        "  const out=Buffer.alloc(w*h*4); let s=0, d=0;\n"
        "  for(let y=0;y<h;y++){ s++;\n"
        "    for(let x=0;x<w;x++){\n"
        "      out[d++]=raw[s++]; out[d++]=raw[s++];\n"
        "      out[d++]=raw[s++]; out[d++]=raw[s++];\n"
        "    }\n"
        "  }\n"
        "  return {buf:out,w,h};\n"
        "}\n"
        "const a = decode(process.argv[2]);\n"
        "const b = decode(process.argv[3]);\n"
        "if (a.w !== b.w || a.h !== b.h) { console.log(1.0); process.exit(0); }\n"
        "const ratio = vd.computePixelDiffRatio(\n"
        "  a.buf, b.buf, 0.02, {width:a.w, height:a.h},\n"
        ");\n"
        "console.log(ratio);\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["VD_PATH"] = str(VISUAL_DIFF_JS)
    result = subprocess.run(
        ["node", str(decoder), str(baseline_path), str(current_path)],
        capture_output=True, text=True, env=env, timeout=30, check=False,
    )
    return float(result.stdout.strip())


class NoDiffControlDeterministic(unittest.TestCase):
    """AC5-AC6 — deterministic pixel-diff ratio assertions via synthesized PNG pairs."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("node") is None:
            raise unittest.SkipTest("node not on PATH; skipping pixel-diff assertion")

    def setUp(self):
        self._tmpdir = Path(tempfile.mkdtemp(prefix="vlm-no-diff-"))

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_identical_pair_yields_ratio_zero(self):
        """AC5 — identical 1×1 PNG pair → inline-Node ratio == 0.0."""
        png_bytes = synthesize_minimal_png(128, 64, 32, 255)
        baseline = self._tmpdir / "baseline.png"
        current = self._tmpdir / "current.png"
        baseline.write_bytes(png_bytes)
        current.write_bytes(png_bytes)
        ratio = _compute_ratio(baseline, current, self._tmpdir)
        self.assertEqual(ratio, 0.0)

    def test_differing_pair_yields_ratio_greater_than_zero(self):
        """AC6 — black vs white 1×1 PNG pair → inline-Node ratio > 0.0."""
        baseline = self._tmpdir / "baseline_black.png"
        current = self._tmpdir / "current_white.png"
        baseline.write_bytes(synthesize_minimal_png(0, 0, 0, 255))
        current.write_bytes(synthesize_minimal_png(255, 255, 255, 255))
        ratio = _compute_ratio(baseline, current, self._tmpdir)
        self.assertGreater(ratio, 0.0)


if __name__ == "__main__":
    unittest.main()
