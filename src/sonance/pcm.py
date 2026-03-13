"""Pure Python replacements for the audioop C extension module.

All functions operate on ``bytes`` fragments containing raw PCM audio
samples.  Supported sample widths: 1 (8-bit unsigned), 2 (16-bit signed
little-endian), 3 (24-bit signed little-endian), 4 (32-bit signed
little-endian).

When *numpy* is available the vectorised fast-paths are used
automatically for ~10-100× throughput improvement on large buffers.
"""

from __future__ import annotations

import math
import struct
from typing import Any, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Numpy acceleration (auto-detected)
# ---------------------------------------------------------------------------

try:
    import numpy as np  # type: ignore[import-untyped]

    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    _HAS_NUMPY = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Per-width limits and struct format codes.
# Width 1: unsigned 8-bit (bias 128 → signed range -128..127)
# Width 2: signed 16-bit LE
# Width 3: signed 24-bit LE (packed manually)
# Width 4: signed 32-bit LE
_MAXVALS: dict[int, int] = {1: 0x7F, 2: 0x7FFF, 3: 0x7FFFFF, 4: 0x7FFFFFFF}
_MINVALS: dict[int, int] = {1: -0x80, 2: -0x8000, 3: -0x800000, 4: -0x80000000}

_STRUCT_FMT: dict[int, str] = {1: "B", 2: "<h", 4: "<i"}


def _check_width(width: int) -> None:
    if width not in (1, 2, 3, 4):
        raise ValueError(f"Unsupported sample width: {width}")


def _check_frag(frag: bytes, width: int) -> None:
    if len(frag) % width != 0:
        raise ValueError("Fragment length not a multiple of sample width")


def _clamp(value: int, width: int) -> int:
    mn = _MINVALS[width]
    mx = _MAXVALS[width]
    if value < mn:
        return mn
    if value > mx:
        return mx
    return value


def _read_sample(frag: bytes, offset: int, width: int) -> int:
    """Read one signed sample from *frag* at byte *offset*."""
    if width == 1:
        return frag[offset] - 128  # unsigned → signed
    if width == 2:
        return struct.unpack_from("<h", frag, offset)[0]
    if width == 3:
        b0, b1, b2 = frag[offset], frag[offset + 1], frag[offset + 2]
        val = b0 | (b1 << 8) | (b2 << 16)
        if val >= 0x800000:
            val -= 0x1000000
        return val
    # width == 4
    return struct.unpack_from("<i", frag, offset)[0]


def _write_sample(value: int, width: int) -> bytes:
    """Pack one signed sample into *width* bytes."""
    if width == 1:
        return bytes([(value + 128) & 0xFF])
    if width == 2:
        return struct.pack("<h", value)
    if width == 3:
        if value < 0:
            value += 0x1000000
        return bytes([value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF])
    return struct.pack("<i", value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def mul(frag: bytes, width: int, factor: float) -> bytes:
    """Multiply all samples in *frag* by *factor*, clamping to range."""
    _check_width(width)
    _check_frag(frag, width)

    if _HAS_NUMPY and width != 3:
        return _np_mul(frag, width, factor)

    out = bytearray()
    for i in range(0, len(frag), width):
        s = _read_sample(frag, i, width)
        s = _clamp(int(s * factor), width)
        out.extend(_write_sample(s, width))
    return bytes(out)


def add(frag1: bytes, frag2: bytes, width: int) -> bytes:
    """Add corresponding samples from *frag1* and *frag2*, clamping."""
    _check_width(width)
    _check_frag(frag1, width)
    _check_frag(frag2, width)
    if len(frag1) != len(frag2):
        raise ValueError("Fragments must have the same length")

    if _HAS_NUMPY and width != 3:
        return _np_add(frag1, frag2, width)

    out = bytearray()
    for i in range(0, len(frag1), width):
        s1 = _read_sample(frag1, i, width)
        s2 = _read_sample(frag2, i, width)
        out.extend(_write_sample(_clamp(s1 + s2, width), width))
    return bytes(out)


def bias(frag: bytes, width: int, bias_val: int) -> bytes:
    """Add a constant *bias_val* to all samples.

    For 8-bit audio, uses modular (wrapping) arithmetic to match
    audioop C behavior. For wider formats, clamps to range.
    """
    _check_width(width)
    _check_frag(frag, width)

    if width == 1:
        # 8-bit: audioop uses unsigned modular arithmetic (wrapping)
        if _HAS_NUMPY:
            arr = np.frombuffer(frag, dtype=np.uint8).astype(np.int32)
            arr = (arr + bias_val) & 0xFF
            return arr.astype(np.uint8).tobytes()
        out = bytearray()
        for b in frag:
            out.append((b + bias_val) & 0xFF)
        return bytes(out)

    if _HAS_NUMPY and width != 3:
        return _np_bias(frag, width, bias_val)

    out = bytearray()
    for i in range(0, len(frag), width):
        s = _read_sample(frag, i, width)
        out.extend(_write_sample(_clamp(s + bias_val, width), width))
    return bytes(out)


def lin2lin(frag: bytes, width: int, newwidth: int) -> bytes:
    """Convert samples from *width* to *newwidth* bytes per sample."""
    _check_width(width)
    _check_width(newwidth)
    _check_frag(frag, width)

    if width == newwidth:
        return frag

    out = bytearray()
    for i in range(0, len(frag), width):
        s = _read_sample(frag, i, width)
        # Scale the sample value between bit depths.
        if newwidth > width:
            s = s << (8 * (newwidth - width))
        else:
            s = s >> (8 * (width - newwidth))
        s = _clamp(s, newwidth)
        out.extend(_write_sample(s, newwidth))
    return bytes(out)


def tomono(
    frag: bytes, width: int, lfactor: float, rfactor: float
) -> bytes:
    """Convert stereo *frag* to mono using channel weights."""
    _check_width(width)
    frame_width = width * 2
    _check_frag(frag, frame_width)

    out = bytearray()
    for i in range(0, len(frag), frame_width):
        left = _read_sample(frag, i, width)
        right = _read_sample(frag, i + width, width)
        s = _clamp(int(left * lfactor + right * rfactor), width)
        out.extend(_write_sample(s, width))
    return bytes(out)


def tostereo(
    frag: bytes, width: int, lfactor: float, rfactor: float
) -> bytes:
    """Convert mono *frag* to stereo using channel factors."""
    _check_width(width)
    _check_frag(frag, width)

    out = bytearray()
    for i in range(0, len(frag), width):
        s = _read_sample(frag, i, width)
        left = _clamp(int(s * lfactor), width)
        right = _clamp(int(s * rfactor), width)
        out.extend(_write_sample(left, width))
        out.extend(_write_sample(right, width))
    return bytes(out)


def rms(frag: bytes, width: int) -> int:
    """Return the root-mean-square of all samples."""
    _check_width(width)
    _check_frag(frag, width)

    n = len(frag) // width
    if n == 0:
        return 0

    if _HAS_NUMPY and width != 3:
        return _np_rms(frag, width)

    sum_sq = 0
    for i in range(0, len(frag), width):
        s = _read_sample(frag, i, width)
        sum_sq += s * s
    return int(math.sqrt(sum_sq / n))


def max(frag: bytes, width: int) -> int:
    """Return the maximum absolute sample value."""
    _check_width(width)
    _check_frag(frag, width)

    n = len(frag) // width
    if n == 0:
        return 0

    peak = 0
    for i in range(0, len(frag), width):
        s = abs(_read_sample(frag, i, width))
        if s > peak:
            peak = s
    return peak


def maxpp(frag: bytes, width: int) -> int:
    """Return the maximum peak-to-peak amplitude."""
    _check_width(width)
    _check_frag(frag, width)

    n = len(frag) // width
    if n < 2:
        return 0

    max_pp = 0
    prev = _read_sample(frag, 0, width)
    prev_extreme = prev
    going_up: Optional[bool] = None

    for i in range(width, len(frag), width):
        cur = _read_sample(frag, i, width)
        if going_up is None:
            if cur > prev:
                going_up = True
            elif cur < prev:
                going_up = False
        elif going_up:
            if cur < prev:
                # Was going up, now going down → prev was a local max.
                diff = prev - prev_extreme
                if diff > max_pp:
                    max_pp = diff
                prev_extreme = prev
                going_up = False
        else:
            if cur > prev:
                # Was going down, now going up → prev was a local min.
                diff = prev_extreme - prev
                if diff > max_pp:
                    max_pp = diff
                prev_extreme = prev
                going_up = True
        prev = cur

    # Check the last sample.
    if going_up:
        diff = prev - prev_extreme
    elif going_up is not None:
        diff = prev_extreme - prev
    else:
        diff = 0
    if diff > max_pp:
        max_pp = diff

    return max_pp


def ratecv(
    frag: bytes,
    width: int,
    nchannels: int,
    inrate: int,
    outrate: int,
    state: Any,
    weightA: int = 1,
    weightB: int = 0,
) -> Tuple[bytes, Any]:
    """Convert sample rate using linear interpolation.

    Returns ``(converted_fragment, new_state)`` for streaming usage.
    """
    _check_width(width)
    _check_frag(frag, width)

    if nchannels < 1:
        raise ValueError("nchannels must be >= 1")
    if inrate <= 0 or outrate <= 0:
        raise ValueError("inrate and outrate must be > 0")

    # Simplify the ratio.
    d = math.gcd(inrate, outrate)
    inrate //= d
    outrate //= d
    # Also factor in weightA+weightB.
    d = math.gcd(outrate, weightA + weightB)

    frame_width = width * nchannels
    n_frames = len(frag) // frame_width

    if state is None:
        # Fresh state: previous samples per channel + fractional position.
        prev_samples: list[int] = [0] * nchannels
        d_pos = -outrate  # force reading first input frame
    else:
        prev_samples, d_pos = state

    cur_samples = list(prev_samples)
    out = bytearray()

    input_idx = 0

    while True:
        while d_pos < 0:
            # Need next input frame.
            if input_idx >= n_frames:
                # Return state for next call.
                return bytes(out), (list(prev_samples), d_pos)
            offset = input_idx * frame_width
            prev_samples = list(cur_samples)
            for ch in range(nchannels):
                cur_samples[ch] = _read_sample(frag, offset + ch * width, width)
            input_idx += 1
            d_pos += outrate

        # Interpolate.
        for ch in range(nchannels):
            cur = cur_samples[ch]
            prev = prev_samples[ch]
            output_sample = (prev * d_pos + cur * (outrate - d_pos)) // outrate
            # Apply weighted average filter.
            output_sample = (
                output_sample * weightA + prev * weightB
            ) // (weightA + weightB)
            output_sample = _clamp(output_sample, width)
            out.extend(_write_sample(output_sample, width))

        d_pos -= inrate

    # Unreachable but satisfies type checker.
    return bytes(out), (prev_samples, d_pos)  # pragma: no cover


def reverse(frag: bytes, width: int) -> bytes:
    """Reverse the order of frames in *frag*."""
    _check_width(width)
    _check_frag(frag, width)

    n = len(frag) // width
    out = bytearray(len(frag))
    for i in range(n):
        src = i * width
        dst = (n - 1 - i) * width
        out[dst : dst + width] = frag[src : src + width]
    return bytes(out)


# ---------------------------------------------------------------------------
# Numpy fast-paths
# ---------------------------------------------------------------------------

_NP_DTYPES: dict[int, str] = {1: "u1", 2: "<i2", 4: "<i4"}


def _frag_to_array(frag: bytes, width: int) -> Any:
    """Convert fragment to numpy array of signed samples."""
    arr = np.frombuffer(frag, dtype=np.dtype(_NP_DTYPES[width]))
    if width == 1:
        return arr.astype(np.int16) - 128
    return arr


def _array_to_frag(arr: Any, width: int) -> bytes:
    """Convert numpy array back to fragment bytes."""
    mn, mx = _MINVALS[width], _MAXVALS[width]
    arr = np.clip(arr, mn, mx)
    if width == 1:
        return (arr + 128).astype(np.uint8).tobytes()
    return arr.astype(np.dtype(_NP_DTYPES[width])).tobytes()


def _np_mul(frag: bytes, width: int, factor: float) -> bytes:
    arr = _frag_to_array(frag, width).astype(np.float64)
    arr *= factor
    return _array_to_frag(np.trunc(arr).astype(np.int64), width)


def _np_add(frag1: bytes, frag2: bytes, width: int) -> bytes:
    a1 = _frag_to_array(frag1, width).astype(np.int64)
    a2 = _frag_to_array(frag2, width).astype(np.int64)
    return _array_to_frag(a1 + a2, width)


def _np_bias(frag: bytes, width: int, bias_val: int) -> bytes:
    arr = _frag_to_array(frag, width).astype(np.int64)
    arr += bias_val
    return _array_to_frag(arr, width)


def _np_rms(frag: bytes, width: int) -> int:
    arr = _frag_to_array(frag, width).astype(np.float64)
    if len(arr) == 0:
        return 0
    return int(np.sqrt(np.mean(arr * arr)))
